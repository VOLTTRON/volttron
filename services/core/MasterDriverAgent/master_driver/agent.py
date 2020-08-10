# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import logging
import sys
import gevent
from collections import defaultdict
from volttron.platform.vip.agent import Agent, RPC
from volttron.platform.agent import utils
from volttron.platform.agent import math_utils
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from .driver import DriverAgent
import resource
from datetime import datetime, timedelta
import bisect
import fnmatch
from volttron.platform import jsonapi
from .interfaces import DriverInterfaceError
from .driver_locks import configure_socket_lock, configure_publish_lock

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '4.0'


class OverrideError(DriverInterfaceError):
    """Error raised when the user tries to set/revert point when global override is set."""
    pass


def master_driver_agent(config_path, **kwargs):

    config = utils.load_config(config_path)

    def get_config(name, default=None):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, default)

    # Increase open files resource limit to max or 8192 if unlimited
    system_socket_limit = None
    
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    except OSError:
        _log.exception('error getting open file limits')
    else:
        if soft != hard and soft != resource.RLIM_INFINITY:
            try:
                system_socket_limit = 8192 if hard == resource.RLIM_INFINITY else hard
                resource.setrlimit(resource.RLIMIT_NOFILE, (system_socket_limit, hard))
            except OSError:
                _log.exception('error setting open file limits')
            else:
                _log.debug('open file resource limit increased from %d to %d',
                           soft, system_socket_limit)
        if soft == hard:
            system_socket_limit = soft

    max_open_sockets = get_config('max_open_sockets', None)

    # TODO: update the default after scalability testing.
    max_concurrent_publishes = get_config('max_concurrent_publishes', 10000)

    driver_config_list = get_config('driver_config_list')
    
    scalability_test = get_config('scalability_test', False)
    scalability_test_iterations = get_config('scalability_test_iterations', 3)

    driver_scrape_interval = get_config('driver_scrape_interval', 0.02)

    if config.get("driver_config_list") is not None:
        _log.warning("Master driver configured with old setting. This is no longer supported.")
        _log.warning('Use the script "scripts/update_master_driver_config.py" to convert the configuration.')

    publish_depth_first_all = bool(get_config("publish_depth_first_all", True))
    publish_breadth_first_all = bool(get_config("publish_breadth_first_all", False))
    publish_depth_first = bool(get_config("publish_depth_first", False))
    publish_breadth_first = bool(get_config("publish_breadth_first", False))

    group_offset_interval = get_config("group_offset_interval", 0.0)

    return MasterDriverAgent(driver_config_list, scalability_test,
                             scalability_test_iterations,
                             driver_scrape_interval,
                             group_offset_interval,
                             max_open_sockets,
                             max_concurrent_publishes,
                             system_socket_limit,
                             publish_depth_first_all,
                             publish_breadth_first_all,
                             publish_depth_first,
                             publish_breadth_first,
                             heartbeat_autostart=True, **kwargs)


class MasterDriverAgent(Agent):
    def __init__(self, driver_config_list, scalability_test = False,
                 scalability_test_iterations=3,
                 driver_scrape_interval=0.02,
                 group_offset_interval=0.0,
                 max_open_sockets=None,
                 max_concurrent_publishes=10000,
                 system_socket_limit=None,
                 publish_depth_first_all=True,
                 publish_breadth_first_all=False,
                 publish_depth_first=False,
                 publish_breadth_first=False,
                 **kwargs):
        super(MasterDriverAgent, self).__init__(**kwargs)
        self.instances = {}
        self.scalability_test = scalability_test
        self.scalability_test_iterations = scalability_test_iterations
        try:
            self.driver_scrape_interval = float(driver_scrape_interval)
        except ValueError:
            _log.warning("Invalid driver_scrape_interval, setting to default value.")
            self.driver_scrape_interval = 0.02

        try:
            self.group_offset_interval = float(group_offset_interval)
        except ValueError:
            _log.warning("Invalid group_offset_interval, setting to default value.")
            self.group_offset_interval = 0.0

        self.system_socket_limit = system_socket_limit
        self.freed_time_slots = defaultdict(list)
        self.group_counts = defaultdict(int)
        self._name_map = {}

        self.publish_depth_first_all = bool(publish_depth_first_all)
        self.publish_breadth_first_all = bool(publish_breadth_first_all)
        self.publish_depth_first = bool(publish_depth_first)
        self.publish_breadth_first = bool(publish_breadth_first)
        self._override_devices = set()
        self._override_patterns = None
        self._override_interval_events = {}

        if scalability_test:
            self.waiting_to_finish = set()
            self.test_iterations = 0
            self.test_results = []
            self.current_test_start = None

        self.default_config = {"scalability_test": scalability_test,
                               "scalability_test_iterations": scalability_test_iterations,
                               "max_open_sockets": max_open_sockets,
                               "max_concurrent_publishes": max_concurrent_publishes,
                               "driver_scrape_interval": self.driver_scrape_interval,
                               "group_offset_interval": self.group_offset_interval,
                               "publish_depth_first_all": self.publish_depth_first_all,
                               "publish_breadth_first_all": self.publish_breadth_first_all,
                               "publish_depth_first": self.publish_depth_first,
                               "publish_breadth_first": self.publish_breadth_first}

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")
        self.vip.config.subscribe(self.update_driver, actions=["NEW", "UPDATE"], pattern="devices/*")
        self.vip.config.subscribe(self.remove_driver, actions="DELETE", pattern="devices/*")
        
    def configure_main(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

        if action == "NEW":
            try:
                self.max_open_sockets = config["max_open_sockets"]
                if self.max_open_sockets is not None:
                    max_open_sockets = int(self.max_open_sockets)
                    configure_socket_lock(max_open_sockets)
                    _log.info("maximum concurrently open sockets limited to " + str(max_open_sockets))
                elif self.system_socket_limit is not None:
                    max_open_sockets = int(self.system_socket_limit * 0.8)
                    _log.info("maximum concurrently open sockets limited to " + str(max_open_sockets) +
                              " (derived from system limits)")
                    configure_socket_lock(max_open_sockets)
                else:
                    configure_socket_lock()
                    _log.warning("No limit set on the maximum number of concurrently open sockets. "
                                 "Consider setting max_open_sockets if you plan to work with 800+ modbus devices.")

                self.max_concurrent_publishes = config['max_concurrent_publishes']
                max_concurrent_publishes = int(self.max_concurrent_publishes)
                if max_concurrent_publishes < 1:
                    _log.warning("No limit set on the maximum number of concurrent driver publishes. "
                                 "Consider setting max_concurrent_publishes if you plan to work with many devices.")
                else:
                    _log.info("maximum concurrent driver publishes limited to " + str(max_concurrent_publishes))
                configure_publish_lock(max_concurrent_publishes)

                self.scalability_test = bool(config["scalability_test"])
                self.scalability_test_iterations = int(config["scalability_test_iterations"])

                if self.scalability_test:
                    self.waiting_to_finish = set()
                    self.test_iterations = 0
                    self.test_results = []
                    self.current_test_start = None

            except ValueError as e:
                _log.error("ERROR PROCESSING STARTUP CRITICAL CONFIGURATION SETTINGS: {}".format(e))
                _log.error("MASTER DRIVER SHUTTING DOWN")
                sys.exit(1)

        else:
            if self.max_open_sockets != config["max_open_sockets"]:
                _log.info("The master driver must be restarted for changes to the max_open_sockets setting to take "
                          "effect")

            if self.max_concurrent_publishes != config["max_concurrent_publishes"]:
                _log.info("The master driver must be restarted for changes to the max_concurrent_publishes setting to "
                          "take effect")

            if self.scalability_test != bool(config["scalability_test"]):
                if not self.scalability_test:
                    _log.info(
                        "The master driver must be restarted with scalability_test set to true in order to run a test.")
                if self.scalability_test:
                    _log.info("A scalability test may not be interrupted. Restarting the driver is required to stop "
                              "the test.")
            try:
                if self.scalability_test_iterations != int(config["scalability_test_iterations"]) and \
                        self.scalability_test:
                    _log.info("A scalability test must be restarted for the scalability_test_iterations setting to "
                              "take effect.")
            except ValueError:
                pass

        # update override patterns
        if self._override_patterns is None:
            try:
                values = self.vip.config.get("override_patterns")
                values = jsonapi.loads(values)

                if isinstance(values, dict):
                    self._override_patterns = set()
                    for pattern, end_time in values.items():
                        # check the end_time
                        now = utils.get_aware_utc_now()
                        # If end time is indefinite, set override with indefinite duration
                        if end_time == "0.0":
                            self._set_override_on(pattern, 0.0, from_config_store=True)
                        else:
                            end_time = utils.parse_timestamp_string(end_time)
                            # If end time > current time, set override with new duration
                            if end_time > now:
                                delta = end_time - now
                                self._set_override_on(pattern, delta.total_seconds(), from_config_store=True)
                else:
                    self._override_patterns = set()
            except KeyError:
                self._override_patterns = set()
            except ValueError:
                _log.error("Override patterns is not set correctly in config store")
                self._override_patterns = set()
        try:
            driver_scrape_interval = float(config["driver_scrape_interval"])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            _log.error("Master driver scrape interval settings unchanged")
            # TODO: set a health status for the agent

        try:
            group_offset_interval = float(config["group_offset_interval"])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            _log.error("Master driver group interval settings unchanged")
            # TODO: set a health status for the agent

        if self.scalability_test and action == "UPDATE":
            _log.info("Running scalability test. Settings may not be changed without restart.")
            return

        if (self.driver_scrape_interval != driver_scrape_interval or
                self.group_offset_interval != group_offset_interval):
            self.driver_scrape_interval = driver_scrape_interval
            self.group_offset_interval = group_offset_interval

            _log.info("Setting time delta between driver device scrapes to  " + str(driver_scrape_interval))

            # Reset all scrape schedules
            self.freed_time_slots.clear()
            self.group_counts.clear()
            for driver in self.instances.values():
                time_slot = self.group_counts[driver.group]
                driver.update_scrape_schedule(time_slot, self.driver_scrape_interval,
                                              driver.group, self.group_offset_interval)
                self.group_counts[driver.group] += 1

        self.publish_depth_first_all = bool(config["publish_depth_first_all"])
        self.publish_breadth_first_all = bool(config["publish_breadth_first_all"])
        self.publish_depth_first = bool(config["publish_depth_first"])
        self.publish_breadth_first = bool(config["publish_breadth_first"])

        # Update the publish settings on running devices.
        for driver in self.instances.values():
            driver.update_publish_types(self.publish_depth_first_all,
                                        self.publish_breadth_first_all,
                                        self.publish_depth_first,
                                        self.publish_breadth_first)

    def derive_device_topic(self, config_name):
        _, topic = config_name.split('/', 1)
        return topic

    def stop_driver(self, device_topic):
        real_name = self._name_map.pop(device_topic.lower(), device_topic)

        driver = self.instances.pop(real_name, None)

        if driver is None:
            return

        _log.info("Stopping driver: {}".format(real_name))

        try:
            driver.core.stop(timeout=5.0)
        except Exception as e:
            _log.error("Failure during {} driver shutdown: {}".format(real_name, e))

        bisect.insort(self.freed_time_slots[driver.group], driver.time_slot)
        self.group_counts[driver.group] -= 1

    def update_driver(self, config_name, action, contents):
        _log.info("In update_driver")
        topic = self.derive_device_topic(config_name)
        self.stop_driver(topic)

        group = int(contents.get("group", 0))

        slot = self.group_counts[group]

        if self.freed_time_slots[group]:
            slot = self.freed_time_slots[group].pop(0)

        _log.info("Starting driver: {}".format(topic))
        driver = DriverAgent(self, contents, slot, self.driver_scrape_interval, topic,
                             group, self.group_offset_interval,
                             self.publish_depth_first_all,
                             self.publish_breadth_first_all,
                             self.publish_depth_first,
                             self.publish_breadth_first)
        gevent.spawn(driver.core.run)
        self.instances[topic] = driver
        self.group_counts[group] += 1
        self._name_map[topic.lower()] = topic
        self._update_override_state(topic, 'add')

    def remove_driver(self, config_name, action, contents):
        topic = self.derive_device_topic(config_name)
        self.stop_driver(topic)
        self._update_override_state(topic, 'remove')

    # def device_startup_callback(self, topic, driver):
    #     _log.debug("Driver hooked up for "+topic)
    #     topic = topic.strip('/')
    #     self.instances[topic] = driver
        
    def scrape_starting(self, topic):
        if not self.scalability_test:
            return
        
        if not self.waiting_to_finish:
            # Start a new measurement
            self.current_test_start = datetime.now()
            self.waiting_to_finish = set(self.instances.keys())
            
        if topic not in self.waiting_to_finish:
            _log.warning(
                f"{topic} started twice before test finished, increase the length of scrape interval and rerun test")

    def scrape_ending(self, topic):
        if not self.scalability_test:
            return
        
        try:
            self.waiting_to_finish.remove(topic)
        except KeyError:
            _log.warning(
                f"{topic} published twice before test finished, increase the length of scrape interval and rerun test")

        if not self.waiting_to_finish:
            end = datetime.now()
            delta = end - self.current_test_start
            delta = delta.total_seconds()
            self.test_results.append(delta)
            
            self.test_iterations += 1
            
            _log.info("publish {} took {} seconds".format(self.test_iterations, delta))
            
            if self.test_iterations >= self.scalability_test_iterations:
                # Test is now over. Button it up and shutdown.
                mean = math_utils.mean(self.test_results) 
                stdev = math_utils.stdev(self.test_results) 
                _log.info("Mean total publish time: "+str(mean))
                _log.info("Std dev publish time: "+str(stdev))
                sys.exit(0)

    @RPC.export
    def get_point(self, path, point_name, **kwargs):
        """RPC method

        Return value of specified device set point
        :param path: device path
        :type path: str
        :param point_name: set point
        :type point_name: str
        :param kwargs: additional arguments for the device
        :type kwargs: arguments pointer
        """
        return self.instances[path].get_point(point_name, **kwargs)

    @RPC.export
    def set_point(self, path, point_name, value, **kwargs):
        """RPC method

        Set value on specified device set point. If global override is condition is set, raise OverrideError exception.
        :param path: device path
        :type path: str
        :param point_name: set point
        :type point_name: str
        :param value: value to set
        :type value: int/float/bool
        :param kwargs: additional arguments for the device
        :type kwargs: arguments pointer
        """
        if path in self._override_devices:
            raise OverrideError(
                "Cannot set point on device {} since global override is set".format(path))
        else:
            return self.instances[path].set_point(point_name, value, **kwargs)

    @RPC.export
    def scrape_all(self, path):
        return self.instances[path].scrape_all()

    @RPC.export
    def get_multiple_points(self, path, point_names, **kwargs):
        return self.instances[path].get_multiple_points(point_names, **kwargs)

    @RPC.export
    def set_multiple_points(self, path, point_names_values, **kwargs):
        """RPC method

        Set values on multiple set points at once. If global override is condition is set,raise OverrideError exception.
        :param path: device path
        :type path: str
        :param point_names_values: list of points and corresponding values
        :type point_names_values: list of tuples
        :param kwargs: additional arguments for the device
        :type kwargs: arguments pointer
        """
        if path in self._override_devices:
            raise OverrideError(
                "Cannot set point on device {} since global override is set".format(path))
        else:
            return self.instances[path].set_multiple_points(point_names_values, **kwargs)
    
    @RPC.export
    def heart_beat(self):
        """RPC method

        Sends heartbeat to all devices
        """
        _log.debug("sending heartbeat")
        for device in self.instances.values():
            device.heart_beat()
            
    @RPC.export
    def revert_point(self, path, point_name, **kwargs):
        """RPC method

        Revert the set point to default state/value. If global override is condition is set, raise OverrideError
        exception.
        :param path: device path
        :type path: str
        :param point_name: set point to revert
        :type point_name: str
        :param kwargs: additional arguments for the device
        :type kwargs: arguments pointer
        """
        if path in self._override_devices:
            raise OverrideError(
                "Cannot revert point on device {} since global override is set".format(path))
        else:
            self.instances[path].revert_point(point_name, **kwargs)

    @RPC.export
    def revert_device(self, path, **kwargs):
        """RPC method

        Revert all the set point values of the device to default state/values. If global override is condition is set,
        raise OverrideError exception.
        :param path: device path
        :type path: str
        :param kwargs: additional arguments for the device
        :type kwargs: arguments pointer
        """
        if path in self._override_devices:
            raise OverrideError(
                "Cannot revert device {} since global override is set".format(path))
        else:
            self.instances[path].revert_all(**kwargs)

    @RPC.export
    def set_override_on(self, pattern, duration=0.0, failsafe_revert=True, staggered_revert=False):
        """RPC method

        Turn on override condition on all the devices matching the pattern.
        :param pattern: Override pattern to be applied. For example,
            If pattern is campus/building1/* - Override condition is applied for all the devices under
            campus/building1/.
            If pattern is campus/building1/ahu1 - Override condition is applied for only campus/building1/ahu1
            The pattern matching is based on bash style filename matching semantics.
        :type pattern: str
        :param duration: Time duration for the override in seconds. If duration <= 0.0, it implies as indefinite
        duration.
        :type duration: float
        :param failsafe_revert: Flag to indicate if all the devices falling under the override condition has to be set
         to its default state/value immediately.
        :type failsafe_revert: boolean
        :param staggered_revert: If this flag is set, reverting of devices will be staggered.
        :type staggered_revert: boolean
        """
        self._set_override_on(pattern, duration, failsafe_revert, staggered_revert)

    def _set_override_on(self, pattern, duration=0.0, failsafe_revert=True, staggered_revert=False,
                         from_config_store=False):
        """Turn on override condition on all devices matching the pattern. It schedules an event to keep track of
        the duration over which override has to be applied. New override patterns and corresponding end times are
        stored in config store.
        :param pattern: Override pattern to be applied. For example,
        :type pattern: str
        :param duration: Time duration for the override in seconds. If duration <= 0.0, it implies as indefinite
        duration.
        :type duration: float
        :param failsafe_revert: Flag to indicate if revert is required
        :type failsafe_revert: boolean
        :param staggered_revert: Flag to indicate if staggering of reverts is needed.
        :type staggered_revert: boolean
        :param from_config_store: Flag to indicate if this function is called from config store callback
        :type from_config_store: boolean
        """
        stagger_interval = 0.05  # sec
        # Add to override patterns set
        self._override_patterns.add(pattern)
        i = 0
        for name in self.instances.keys():
            i += 1
            if fnmatch.fnmatch(name, pattern):
                # If revert to default state is needed
                if failsafe_revert:
                    if staggered_revert:
                        self.core.spawn_later(i*stagger_interval, self.instances[name].revert_all())
                    else:
                        self.core.spawn(self.instances[name].revert_all())
                # Set override
                self._override_devices.add(name)
        # Set timer for interval of override condition
        config_update = self._update_override_interval(duration, pattern)
        if config_update and not from_config_store:
            # Update config store
            patterns = dict()
            for pat in self._override_patterns:
                if self._override_interval_events[pat] is None:
                    patterns[pat] = str(0.0)
                else:
                    evt, end_time = self._override_interval_events[pat]
                    patterns[pat] = utils.format_timestamp(end_time)

            self.vip.config.set("override_patterns", jsonapi.dumps(patterns))

    @RPC.export
    def set_override_off(self, pattern):
        """RPC method

        Turn off override condition on all the devices matching the pattern. The pattern matching is based on bash style
        filename matching semantics.
        :param pattern: Pattern on which override condition has to be removed.
        :type pattern: str
        """
        return self._set_override_off(pattern)

    # Get a list of all the devices with override condition.
    @RPC.export
    def get_override_devices(self):
        """RPC method

        Get a list of all the devices with override condition.
        """
        return list(self._override_devices)

    @RPC.export
    def clear_overrides(self):
        """RPC method

        Clear all overrides.
        """
        # Cancel all pending override timer events
        for pattern, evt in self._override_interval_events.items():
            if evt is not None:
                evt[0].cancel()
        self._override_interval_events.clear()
        self._override_devices.clear()
        self._override_patterns.clear()
        self.vip.config.set("override_patterns", {})

    @RPC.export
    def get_override_patterns(self):
        """RPC method

        Get a list of all the override patterns.
        """
        return list(self._override_patterns)

    def _set_override_off(self, pattern):
        """Turn off override condition on all devices matching the pattern. It removes the pattern from the override
        patterns set, clears the list of overridden devices  and reevaluates the state of devices. It then cancels the
        pending override event and removes pattern from the config store.
        :param pattern: Override pattern to be removed.
        :type pattern: str
        """
        # If pattern exactly matches
        if pattern in self._override_patterns:
            self._override_patterns.discard(pattern)
            # Cancel any pending override events
            self._cancel_override_events(pattern)
            self._override_devices.clear()
            patterns = dict()
            # Build override devices list again
            for pat in self._override_patterns:
                for device in self.instances:
                    if fnmatch.fnmatch(device, pat):
                        self._override_devices.add(device)

                if self._override_interval_events[pat] is None:
                    patterns[pat] = str(0.0)
                else:
                    evt, end_time = self._override_interval_events[pat]
                    patterns[pat] = utils.format_timestamp(end_time)

            self.vip.config.set("override_patterns", jsonapi.dumps(patterns))
        else:
            _log.error("Override Pattern did not match!")
            raise OverrideError(
                "Pattern {} does not exist in list of override patterns".format(pattern))

    def _update_override_interval(self, interval, pattern):
        """Schedules a new override event for the specified interval and pattern. If the pattern already exists and new
        end time is greater than old one, the event is cancelled and new event is scheduled.

        :param interval override duration. If interval is <= 0.0, implies indefinite duration
        :type pattern: float
        :param pattern: Override pattern.
        :type pattern: str
        :return Flag to indicate if update is done or not.
        """
        if interval <= 0.0:  # indicative of indefinite duration
            if pattern in self._override_interval_events:
                # If override duration is indefinite, do nothing
                if self._override_interval_events[pattern] is None:
                    return False
                else:
                    # Cancel the old event
                    evt = self._override_interval_events.pop(pattern)
                    evt[0].cancel()
            self._override_interval_events[pattern] = None
            return True
        else:
            override_start = utils.get_aware_utc_now()
            override_end = override_start + timedelta(seconds=interval)
            if pattern in self._override_interval_events:
                evt = self._override_interval_events[pattern]
                # If event is indefinite or greater than new end time, do nothing
                if evt is None or override_end < evt[1]:
                    return False
                else:
                    evt = self._override_interval_events.pop(pattern)
                    evt[0].cancel()
            # Schedule new override event
            event = self.core.schedule(override_end, self._cancel_override, pattern)
            self._override_interval_events[pattern] = (event, override_end)
            return True

    def _cancel_override_events(self, pattern):
        """
        Cancel override event matching the pattern
        :param pattern: override pattern
        :type pattern: str
        """
        if pattern in self._override_interval_events:
            # Cancel the override cancellation timer event
            evt = self._override_interval_events.pop(pattern, None)
            if evt is not None:
                evt[0].cancel()

    def _cancel_override(self, pattern):
        """
        Cancel the override
        :param pattern: override pattern
        :type: pattern: str
        """
        self._set_override_off(pattern)

    def _update_override_state(self, device, state):
        """
        If a new device is added, it is checked to see if the device is part of the list of overridden patterns. If so,
        it is added to the list of overridden devices. Similarly, if a device is being removed, it is also removed
        from list of overridden devices (if exists).
        :param device: device to be removed
        :type device: str
        :param state: 'add' or 'remove'
        :type state: str
        """
        device = device.lower()

        if state == 'add':
            # If device falls under the existing overridden patterns, then add it to list of overridden devices.
            for pattern in self._override_patterns:
                if fnmatch.fnmatch(device, pattern):
                    self._override_devices.add(device)
                    return
        else:
            # If device is in list of overridden devices, remove it.
            if device in self._override_devices:
                self._override_devices.remove(device)

    @RPC.export
    def forward_bacnet_cov_value(self, source_address, point_name, point_values):
        """
        Called by the BACnet Proxy to pass the COV value to the driver agent
        for publishing
        :param source_address: path of the device used for publish topic
        :param point_name: name of the point in the COV notification
        :param point_values: dictionary of updated values sent by the device
        """
        for driver in self.instances.values():
            if driver.device_path == source_address:
                driver.publish_cov_value(point_name, point_values)


def main(argv=sys.argv):
    """Main method called to start the agent."""
    utils.vip_main(master_driver_agent, identity=PLATFORM_DRIVER,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
