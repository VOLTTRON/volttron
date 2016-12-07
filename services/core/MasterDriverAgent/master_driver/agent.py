# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import logging
import sys
import os
import gevent
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils
from volttron.platform.agent import math_utils
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from driver import DriverAgent
import resource
from datetime import datetime, timedelta
import bisect
import fnmatch

from driver_locks import configure_socket_lock, configure_publish_lock

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '2.0'

class OverrideError(StandardError):
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

    #TODO: update the default after scalability testing.
    max_concurrent_publishes = get_config('max_concurrent_publishes', 10000)

    driver_config_list = get_config('driver_config_list')
    
    scalability_test = get_config('scalability_test', False)
    scalability_test_iterations = get_config('scalability_test_iterations', 3)

    driver_scrape_interval = get_config('driver_scrape_interval', 0.02)

    if config.get("driver_config_list") is not None:
        _log.warning("Master driver configured with old setting. This is no longer supported.")
        _log.warning('Use the script "scripts/update_master_driver_config.py" to convert the configuration.')

    publish_depth_first_all = bool(get_config("publish_depth_first_all", True))
    publish_breadth_first_all = bool(get_config("publish_breadth_first_all", True))
    publish_depth_first = bool(get_config("publish_depth_first", True))
    publish_breadth_first = bool(get_config("publish_breadth_first", True))

    return MasterDriverAgent(driver_config_list, scalability_test,
                             scalability_test_iterations,
                             driver_scrape_interval,
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
                 scalability_test_iterations = 3,
                 driver_scrape_interval = 0.02,
                 max_open_sockets = None,
                 max_concurrent_publishes = 10000,
                 system_socket_limit = None,
                 publish_depth_first_all=True,
                 publish_breadth_first_all=True,
                 publish_depth_first=True,
                 publish_breadth_first=True,
                 **kwargs):
        super(MasterDriverAgent, self).__init__(**kwargs)
        self.instances = {}
        self.scalability_test = scalability_test
        self.scalability_test_iterations = scalability_test_iterations
        try:
            self.driver_scrape_interval = float(driver_scrape_interval)
        except ValueError:
            self.driver_scrape_interval = 0.05
        self.system_socket_limit = system_socket_limit
        self.freed_time_slots = []
        self._name_map = {}

        self.publish_depth_first_all = publish_depth_first_all
        self.publish_breadth_first_all = publish_breadth_first_all
        self.publish_depth_first = publish_depth_first
        self.publish_breadth_first = publish_breadth_first
        self._override_devices = set()
        self._override_patterns = set()
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
                               "driver_scrape_interval": driver_scrape_interval,
                               "publish_depth_first_all": publish_depth_first_all,
                               "publish_breadth_first_all": publish_breadth_first_all,
                               "publish_depth_first": publish_depth_first,
                               "publish_breadth_first": publish_breadth_first}

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
                    _log.warn("No limit set on the maximum number of concurrently open sockets. "
                              "Consider setting max_open_sockets if you plan to work with 800+ modbus devices.")

                self.max_concurrent_publishes = config['max_concurrent_publishes']
                max_concurrent_publishes = int(self.max_concurrent_publishes)
                if max_concurrent_publishes < 1:
                    _log.warn("No limit set on the maximum number of concurrent driver publishes. "
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
                _log.info("The master driver must be restarted for changes to the max_open_sockets setting to take effect")

            if self.max_concurrent_publishes != config["max_concurrent_publishes"]:
                _log.info("The master driver must be restarted for changes to the max_concurrent_publishes setting to take effect")

            if self.scalability_test != bool(config["scalability_test"]):
                if not self.scalability_test:
                    _log.info(
                        "The master driver must be restarted with scalability_test set to true in order to run a test.")
                if self.scalability_test:
                    _log.info(
                        "A scalability test may not be interrupted. Restarting the driver is required to stop the test.")
            try:
                if self.scalability_test_iterations != int(config["scalability_test_iterations"]) and self.scalability_test:
                    _log.info(
                "A scalability test must be restarted for the scalability_test_iterations setting to take effect.")
            except ValueError:
                pass

        try:
            driver_scrape_interval = float(config["driver_scrape_interval"])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            _log.error("Master driver scrape interval settings unchanged")
            # TODO: set a health status for the agent

        if self.scalability_test and action == "UPDATE":
            _log.info("Running scalability test. Settings may not be changed without restart.")
            return

        if self.driver_scrape_interval != driver_scrape_interval:
            self.driver_scrape_interval = driver_scrape_interval

            _log.info("Setting time delta between driver device scrapes to  " + str(driver_scrape_interval))

            #Reset all scrape schedules
            self.freed_time_slots = []
            time_slot = 0
            for driver in self.instances.itervalues():
                driver.update_scrape_schedule(time_slot, self.driver_scrape_interval)
                time_slot+=1

        self.publish_depth_first_all = bool(config["publish_depth_first_all"])
        self.publish_breadth_first_all = bool(config["publish_breadth_first_all"])
        self.publish_depth_first = bool(config["publish_depth_first"])
        self.publish_breadth_first = bool(config["publish_breadth_first"])

        #Update the publish settings on running devices.
        for driver in self.instances.itervalues():
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
        except StandardError as e:
            _log.error("Failure during {} driver shutdown: {}".format(real_name, e))

        bisect.insort(self.freed_time_slots, driver.time_slot)


    def update_driver(self, config_name, action, contents):
        topic = self.derive_device_topic(config_name)
        self.stop_driver(topic)

        slot = len(self.instances)

        if self.freed_time_slots:
            slot = self.freed_time_slots.pop(0)

        _log.info("Starting driver: {}".format(topic))
        driver = DriverAgent(self, contents, slot, self.driver_scrape_interval, topic,
                             self.publish_depth_first_all,
                             self.publish_breadth_first_all,
                             self.publish_depth_first,
                             self.publish_breadth_first)
        gevent.spawn(driver.core.run)
        self.instances[topic] = driver
        self._name_map[topic.lower()] = topic


    def remove_driver(self, config_name, action, contents):
        topic = self.derive_device_topic(config_name)
        self.stop_driver(topic)
               
    
    # def device_startup_callback(self, topic, driver):
    #     _log.debug("Driver hooked up for "+topic)
    #     topic = topic.strip('/')
    #     self.instances[topic] = driver
        
    def scrape_starting(self, topic):
        if not self.scalability_test:
            return
        
        if not self.waiting_to_finish:
            #Start a new measurement
            self.current_test_start = datetime.now()
            self.waiting_to_finish = set(self.instances.iterkeys())
            
        if topic not in self.waiting_to_finish:
            _log.warning(topic + " started twice before test finished, increase the length of scrape interval and rerun test")
            
    
    def scrape_ending(self, topic):
        if not self.scalability_test:
            return
        
        try:
            self.waiting_to_finish.remove(topic)
        except KeyError:
            _log.warning(topic + " published twice before test finished, increase the length of scrape interval and rerun test")
            
        if not self.waiting_to_finish:
            end = datetime.now()
            delta = end - self.current_test_start
            delta = delta.total_seconds()
            self.test_results.append(delta)
            
            self.test_iterations += 1
            
            _log.info("publish {} took {} seconds".format(self.test_iterations, delta))
            
            if self.test_iterations >= self.scalability_test_iterations:
                #Test is now over. Button it up and shutdown.
                mean = math_utils.mean(self.test_results) 
                stdev = math_utils.stdev(self.test_results) 
                _log.info("Mean total publish time: "+str(mean))
                _log.info("Std dev publish time: "+str(stdev))
                sys.exit(0)
        
    @RPC.export
    def get_point(self, path, point_name, **kwargs):
        return self.instances[path].get_point(point_name, **kwargs)

    @RPC.export
    def set_point(self, path, point_name, value, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot set point on device {} since global override is set".format(path))
        else:
            return self.instances[path].set_point(point_name, value, **kwargs)

    @RPC.export
    def set_multiple_points(self, path, point_names_values, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot set point on device {} since global override is set".format(path))
        else:
            return self.instances[path].set_multiple_points(point_names_values, **kwargs)
    
    @RPC.export
    def heart_beat(self):
        _log.debug("sending heartbeat")
        for device in self.instances.values():
            device.heart_beat()
            
    @RPC.export
    def revert_point(self, path, point_name, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot revert point on device {} since global override is set".format(path))
        else:
            self.instances[path].revert_point(point_name, **kwargs)

    @RPC.export
    def revert_device(self, path, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot revert device {} since global override is set".format(path))
        else:
            self.instances[path].revert_all(**kwargs)

    # Turn on override condition on all the devices matching the pattern.
    @RPC.export
    def set_override_on(self, pattern, duration=1.0, failsafe_revert=True, staggered_revert=False):
        self._set_override_on(pattern, duration, failsafe_revert, staggered_revert)

    def _set_override_on(self, pattern, duration=1.0, failsafe_revert=True, staggered_revert=False):
        revert_greenlets = []
        stagger_interval = 0.05 #sec
        pattern = pattern.lower()

        #Add to patterns set
        self._override_patterns.add(pattern)
        device_topic_actual = self.instances.keys()
        i = 0

        for name in device_topic_actual:
            name = name.lower()
            i += 1
            if fnmatch.fnmatch(name, pattern):
                #If revert to default state is needed
                if failsafe_revert:
                    if staggered_revert:
                        revert_greenlets.append(gevent.spawn_later(i*stagger_interval, self.instances[name].revert_all()))
                    else:
                        revert_greenlets.append(gevent.spawn(self.instances[name].revert_all()))
                # Set override
                self._override_devices.add(name)
        # Set timer for interval of override condition
        self._update_override_interval(duration, pattern)

    # Turn off override condition on all the entities matching the pattern.
    @RPC.export
    def set_override_off(self, pattern):
        return self._set_override_off(pattern)

    # Get a list of all the devices with override condition.
    @RPC.export
    def get_override_devices(self):
        devices = []
        devices.extend(self._override_devices)
        return devices

    # Clear all overrides
    @RPC.export
    def clear_overrides(self):
        # Cancel all pending override timer events
        for evt in self._override_interval_events.items():
            if evt is not None:
                evt.cancel()
        self._override_interval_events.clear()
        self._override_devices.clear()
        self._override_patterns.clear()

    # Get a list of all the devices with override condition.
    @RPC.export
    def get_override_patterns(self):
        patterns = []
        patterns.extend(self._override_patterns)
        return patterns

    def _set_override_off(self, pattern):
        pattern = pattern.lower()
        # If pattern exactly matches
        if pattern in self._override_patterns:
            self._override_patterns.discard(pattern)
        else:
            _log.debug("Pattern did not match!")

        self._override_devices.clear()
        #Cancel any pending override events
        self._cancel_override_events(pattern)
        #Build override devices list again
        for pat in self._override_patterns:
            for device in self.instances.keys():
                device = device.lower()
                if fnmatch.fnmatch(device, pat):
                    self._override_devices.add(device)

    def _update_override_interval(self, interval, topic):
        override_start = utils.get_aware_utc_now()
        override_end = override_start + timedelta(seconds=interval)
        try:
            self._override_interval_events[topic].cancel()
        except KeyError:
            _log.debug("MASTER DRIVER override interval event key error {}".format(topic))
            pass
        self._override_interval_events[topic] = self.core.schedule(override_end, self._cancel_override, topic)

    def _cancel_override_events(self, pattern):
        if pattern in self._override_interval_events:
            # Cancel the override cancellation timer event
            evt = self._override_interval_events.pop(pattern, None)
            if evt is not None:
                evt.cancel()

    def _cancel_override(self, topic):
        self._set_override_off(topic)

def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(master_driver_agent, identity=PLATFORM_DRIVER)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
