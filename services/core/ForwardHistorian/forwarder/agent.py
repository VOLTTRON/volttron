# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import datetime
import logging
import sys
import time
import traceback
from urllib.parse import urlparse
import threading

import gevent
from gevent.lock import RLock

from volttron.platform.vip.agent import Agent, compat, Unreachable
from volttron.platform.agent.base_historian import BaseHistorian, add_timing_data_to_header
from volttron.platform.agent import utils
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD, Status)
from volttron.utils.docs import doc_inherit
from zmq.green import ZMQError, ENOTSOCK

FORWARD_TIMEOUT_KEY = 'FORWARD_TIMEOUT_KEY'
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '5.1'


def historian(config_path, **kwargs):
    config = utils.load_config(config_path)
    custom_topic_list = config.pop('custom_topic_list', [])
    topic_replace_list = config.pop('topic_replace_list', [])
    destination_vip = config.pop('destination-vip', None)
    service_topic_list = config.pop('service_topic_list', None)
    destination_serverkey = None
    try:
        destination_address = config.pop('destination-address')
    except KeyError:
        destination_address = None
    if service_topic_list is not None:
        w = "Deprecated service_topic_list.  Use capture_device_data " \
            "capture_log_data, capture_analysis_data or capture_record_data " \
            "instead!"
        _log.warning(w)

        # Populate the new values for the kwargs based upon the old data.
        kwargs['capture_device_data'] = True if ("device" in service_topic_list  or "all" in service_topic_list) else False
        kwargs['capture_log_data'] = True if ("datalogger" in service_topic_list or "all" in service_topic_list) else False
        kwargs['capture_record_data'] = True if ("record" in service_topic_list or "all" in service_topic_list) else False
        kwargs['capture_analysis_data'] = True if ("analysis" in service_topic_list or "all" in service_topic_list) else False

    if destination_vip:
        hosts = KnownHostsStore()
        destination_serverkey = hosts.serverkey(destination_vip)
        if destination_serverkey is None:
            _log.info("Destination serverkey not found in known hosts file, using config")
            destination_serverkey = config.pop('destination-serverkey')
        else:
            config.pop('destination-serverkey', None)

        destination_messagebus = 'zmq'

    required_target_agents = config.pop('required_target_agents', [])
    cache_only = config.pop('cache_only', False)

    utils.update_kwargs_with_config(kwargs, config)

    return ForwardHistorian(destination_vip, destination_serverkey,
                            custom_topic_list=custom_topic_list,
                            topic_replace_list=topic_replace_list,
                            required_target_agents=required_target_agents,
                            cache_only=cache_only,
                            destination_address=destination_address,
                            **kwargs)


class ForwardHistorian(BaseHistorian):
    """
    This historian forwards data to another instance as if it was published
    originally to the second instance.
    """
    
    # Connection states
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    DISCONNECTING = 'disconnecting'

    def __init__(self, destination_vip, destination_serverkey,
                 custom_topic_list=[],
                 topic_replace_list=[],
                 required_target_agents=[],
                 cache_only=False,
                 destination_address=None,
                 **kwargs):
        kwargs["process_loop_in_greenlet"] = True
        super(ForwardHistorian, self).__init__(**kwargs)

        # will be available in both threads.
        self._topic_replace_map = {}
        self.topic_replace_list = topic_replace_list
        self._num_failures = 0
        self._last_timeout = 0
        self._target_platform = None
        self._current_custom_topics = set()
        self.destination_vip = destination_vip
        self.destination_serverkey = destination_serverkey
        self.required_target_agents = required_target_agents
        self.cache_only = cache_only
        self.destination_address = destination_address
        
        # Synchronization and connection state management
        self._connection_lock = RLock()
        self._connection_state = self.DISCONNECTED
        self._connection_task = None
        self._connection_retry_count = 0
        self._max_connection_retries = 5
        self._connection_retry_delay = 30  # Initial delay in seconds, will be increased exponentially
        
        config = {
            "custom_topic_list": custom_topic_list,
            "topic_replace_list": self.topic_replace_list,
            "required_target_agents": self.required_target_agents,
            "destination_vip": self.destination_vip,
            "destination_serverkey": self.destination_serverkey,
            "cache_only": self.cache_only,
            "destination_address": self.destination_address
        }

        self.update_default_config(config)

        # We do not support the insert RPC call.
        self.no_insert = True
        # We do not support the query RPC call.
        self.no_query = True

    def configure(self, configuration):
        with self._connection_lock:
            # First tear down any existing connection if connection details changed
            old_destination_vip = self.destination_vip
            old_destination_serverkey = self.destination_serverkey
            old_destination_address = self.destination_address
            
            self.destination_vip = str(configuration.get('destination_vip', ""))
            self.destination_serverkey = str(configuration.get('destination_serverkey', ""))
            self.required_target_agents = configuration.get('required_target_agents', [])
            self.topic_replace_list = configuration.get('topic_replace_list', [])
            self.cache_only = configuration.get('cache_only', False)
            self.destination_address = configuration.get('destination_address', None)
            
            # If connection details changed, teardown existing connection
            connection_changed = (
                old_destination_vip != self.destination_vip or
                old_destination_serverkey != self.destination_serverkey or
                old_destination_address != self.destination_address
            )
            
            if connection_changed and self._connection_state != self.DISCONNECTED:
                _log.info("Connection configuration changed. Tearing down current connection.")
                self._connection_state = self.DISCONNECTING
                if self._target_platform is not None:
                    self.historian_teardown()
                self._connection_state = self.DISCONNECTED
                self._connection_retry_count = 0

        # Reset the replace map - safe to do as it's only modified in capture_data
        # which is called by pubsub callbacks
        self._topic_replace_map = {}

        # Update subscriptions
        custom_topic_set = set(configuration.get('custom_topic_list', []))
        # Topics to add.
        new_topics = custom_topic_set - self._current_custom_topics
        # Topics to remove
        old_topics = self._current_custom_topics - custom_topic_set

        for prefix in new_topics:
            _log.info("Subscribing to {}".format(prefix))
            try:
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=prefix,
                                          callback=self.capture_data).get(timeout=5.0)
                self._current_custom_topics.add(prefix)
            except (gevent.Timeout, Exception) as e:
                _log.error("Failed to subscribe to {}: {}".format(prefix, repr(e)))

        for prefix in old_topics:
            _log.info("unsubscribing from {}".format(prefix))
            try:
                self.vip.pubsub.unsubscribe(peer='pubsub',
                                            prefix=prefix,
                                            callback=self.capture_data).get(timeout=5.0)
                self._current_custom_topics.remove(prefix)
            except (gevent.Timeout, Exception) as e:
                _log.error("Failed to unsubscribe from {}: {}".format(prefix, repr(e)))

    # Stop the BaseHistorian from setting the health status
    def _update_status(self, *args, **kwargs):
        pass

    def _send_alert(self, *args, **kwargs):
        pass

    # Redirect the normal capture functions to capture_data.
    def _capture_device_data(self, peer, sender, bus, topic, headers, message):
        parts = topic.split('/')
        device = '/'.join(parts[1:-1])
        # msg = [{data},{meta}] format
        msg = [{}, {}]
        try:
            # If the filter is empty pass all data.
            if self._device_data_filter:
                for _filter, point_list in self._device_data_filter.items():
                    # If filter is not empty only topics that contain the key
                    # will be kept.
                    if _filter in device:
                        for point in point_list:
                            # devices all publish
                            if isinstance(message, list):
                                # Only points in the point list will be added to the message payload
                                if point in message[0]:
                                    msg[0][point] = message[0][point]
                                    msg[1][point] = message[1][point]
                            else:
                                # other devices publish (devices/campus/building/device/point)
                                msg = None
                                if point in device:
                                    msg = message
                                    # if the point in in the parsed topic then exit for loop
                                    break
                if (isinstance(msg, list) and not msg[0]) or \
                        (isinstance(msg, (float, int, str)) and msg is None):
                    _log.debug("Topic: {} - is not in configured to be forwarded".format(topic))
                    return
            else:
                msg = message
        except Exception as e:
            _log.debug("Error handling device_data_filter. {}".format(e))
            msg = message
        self.capture_data(peer, sender, bus, topic, headers, msg)

    def _capture_log_data(self, peer, sender, bus, topic, headers, message):
        self.capture_data(peer, sender, bus, topic, headers, message)

    def _capture_analysis_data(self, peer, sender, bus, topic, headers, message):
        self.capture_data(peer, sender, bus, topic, headers, message)

    def _capture_record_data(self, peer, sender, bus, topic, headers, message):
        self.capture_data(peer, sender, bus, topic, headers, message)

    def timestamp(self):
        return time.mktime(datetime.datetime.now().timetuple())

    def capture_data(self, peer, sender, bus, topic, headers, message):

        # Grab the timestamp string from the message (we use this as the
        # value in our readings at the end of this method)
        timestamp_string = headers.get(headers_mod.DATE, None)

        data = message
        try:
            # 2.0 agents compatability layer makes sender = pubsub.compat
            # so we can do the proper thing when it is here
            # _log.debug("message in capture_data {}".format(message))
            if sender == 'pubsub.compat':
                # data = jsonapi.loads(message[0])
                data = compat.unpack_legacy_message(headers, message)
                #_log.debug("data in capture_data {}".format(data))
            if isinstance(data, dict):
                data = data
            elif isinstance(data, (int, float)):
                data = data
                # else:
                #     data = data[0]
        except ValueError as e:
            log_message = "message for {topic} bad message string:" \
                          "{message_string}"
            _log.error(log_message.format(topic=topic,
                                          message_string=message[0]))
            raise

        if self.topic_replace_list:
            original_topic = topic
            if topic in self._topic_replace_map.keys():
                topic = self._topic_replace_map[original_topic]
            else:
                self._topic_replace_map[topic] = original_topic
                temptopics = {}
                for x in self.topic_replace_list:
                    if x['from'] in topic:
                        new_topic = temptopics.get(topic, topic)
                        temptopics[topic] = new_topic.replace(
                            x['from'], x['to'])

                for k, v in temptopics.items():
                    self._topic_replace_map[k] = v
                topic = self._topic_replace_map[topic]

            # if the topic wasn't changed then we don't forward anything for
            # it.
            if topic == original_topic:
                _log.warning(
                    "Topic {} not published because not anonymized.".format(original_topic))
                return

        if self.gather_timing_data:
            add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "collected")

        payload = {'headers': headers, 'message': data}

        self._event_queue.put({'source': "forwarded",
                               'topic': topic,
                               'readings': [(timestamp_string, payload)]})

    @doc_inherit
    def publish_to_historian(self, to_publish_list):
        if self.cache_only:
            _log.warning("cache_only enabled")
            return

        handled_records = []

        _log.debug("publish_to_historian number of items: {}"
                   .format(len(to_publish_list)))
        current_time = self.timestamp()
        last_time = self._last_timeout
        
        # Check if we're in a backoff period after a failure
        if self._last_timeout:
            # Calculate backoff time based on number of failures (exponential backoff)
            backoff_time = min(60 * (2 ** min(self._connection_retry_count, 10)), 3600)  # Max 1 hour backoff
            
            if current_time < self._last_timeout + backoff_time:
                _log.debug(f'In backoff period: {backoff_time}s from last failure. Skipping publish.')
                return
        
        # Attempt to establish connection if needed
        with self._connection_lock:
            if self._connection_state == self.DISCONNECTED:
                _log.debug("No active connection. Attempting to establish connection.")
                self._connection_state = self.CONNECTING
                try:
                    # Start the connection process
                    self.historian_setup()
                    if not self._target_platform:
                        _log.error('Could not connect to targeted historian dest_vip {} dest_address {}'.format(
                            self.destination_vip, self.destination_address))
                        self._connection_state = self.DISCONNECTED
                        self._connection_retry_count += 1
                        self._last_timeout = self.timestamp()
                        return
                    
                    self._connection_state = self.CONNECTED
                    self._connection_retry_count = 0
                except Exception as e:
                    _log.error(f"Failed to establish connection: {e}")
                    self._connection_state = self.DISCONNECTED
                    self._connection_retry_count += 1
                    self._last_timeout = self.timestamp()
                    self.vip.health.set_status(STATUS_BAD, f"Connection failed: {e}")
                    return
            
            if self._connection_state != self.CONNECTED:
                _log.debug(f"Cannot publish in current connection state: {self._connection_state}")
                return
            
            # Check if target platform is actually there
            if not self._target_platform:
                _log.error("Target platform reference is None despite connection state CONNECTED")
                self._connection_state = self.DISCONNECTED
                self._connection_retry_count += 1
                self._last_timeout = self.timestamp()
                return
            
            # Verify required target agents are available
            for vip_id in self.required_target_agents:
                try:
                    self._target_platform.vip.ping(vip_id).get(timeout=5)
                except Unreachable:
                    skip = "Skipping publish: Target platform not running " \
                           "required agent {}".format(vip_id)
                    _log.warning(skip)
                    self.vip.health.set_status(STATUS_BAD, skip)
                    return
                except gevent.Timeout:
                    skip = f"Skipping publish: Timeout checking required agent {vip_id}"
                    _log.warning(skip)
                    self.vip.health.set_status(STATUS_BAD, skip)
                    return
                except Exception as e:
                    err = f"Unhandled error checking required agent {vip_id}: {e}"
                    _log.error(err)
                    _log.error(traceback.format_exc())
                    self.vip.health.set_status(STATUS_BAD, err)
                    return
            
            # Process records to publish
            publish_tasks = []
            timeout_occurred = False
            
            for x in to_publish_list:
                if timeout_occurred:
                    _log.error('A timeout has occurred so breaking out of publishing')
                    break
                    
                topic = x['topic']
                value = x['value']
                payload = value
                headers = payload['headers']
                headers['X-Forwarded'] = True
                if 'X-Forwarded-From' in headers:
                    if not isinstance(headers['X-Forwarded-From'], list):
                        headers['X-Forwarded-From'] = [headers['X-Forwarded-From']]
                    headers['X-Forwarded-From'].append(self.instance_name)
                else:
                    headers['X-Forwarded-From'] = self.instance_name

                try:
                    del headers['Origin']
                except KeyError:
                    pass
                try:
                    del headers['Destination']
                except KeyError:
                    pass

                if self.gather_timing_data:
                    add_timing_data_to_header(headers,
                                            self.core.agent_uuid or self.core.identity,
                                            "forwarded")

                # Create individual publish tasks
                try:
                    publish_task = gevent.spawn(self._publish_item, topic, headers, payload['message'], x)
                    publish_tasks.append(publish_task)
                except Exception as e:
                    _log.error(f"Error spawning publish task: {e}")
            
            # Wait for all publish tasks with a global timeout
            try:
                gevent.joinall(publish_tasks, timeout=30, raise_error=True)
                
                # Collect results
                for task in publish_tasks:
                    if task.successful():
                        result = task.value
                        if result['success']:
                            handled_records.append(result['record'])
                        elif result['timeout']:
                            timeout_occurred = True
                            
            except gevent.Timeout:
                # Global timeout
                _log.error("Global timeout waiting for publish tasks")
                timeout_occurred = True
            
            # Cancel any remaining tasks
            for task in publish_tasks:
                if not task.ready():
                    task.kill(block=False)
            
            # Report handled records
            if handled_records:
                _log.debug(f"Successfully handled {len(handled_records)} records")
                self.report_handled(handled_records)
                
            # Handle timeout if occurred
            if timeout_occurred:
                _log.warning('Connection timeout. Will attempt to reconnect.')
                with self._connection_lock:
                    self._last_timeout = self.timestamp()
                    self._connection_retry_count += 1
                    self._connection_state = self.DISCONNECTING
                    self.historian_teardown()
                    self._connection_state = self.DISCONNECTED
                
                _log.debug('Sending alert from the ForwardHistorian')
                status = Status.from_json(self.vip.health.get_status_json())
                self.vip.health.send_alert(FORWARD_TIMEOUT_KEY, status)
                self.vip.health.set_status(STATUS_BAD, "Connection timeout")
            else:
                self.vip.health.set_status(
                    STATUS_GOOD, f"Published {len(handled_records)} items")
    
    def _publish_item(self, topic, headers, message, record):
        """
        Helper method to publish a single item with its own timeout handling
        Returns: dict with status of the publish operation
        """
        result = {'success': False, 'timeout': False, 'record': record}
        
        try:
            with gevent.Timeout(10):  # Individual publish timeout
                self._target_platform.vip.pubsub.publish(
                    peer='pubsub',
                    topic=topic,
                    headers=headers,
                    message=message).get()
                result['success'] = True
        except gevent.Timeout:
            _log.debug(f"Timeout publishing to {topic}")
            result['timeout'] = True
        except Unreachable:
            _log.error(f"Target not reachable for {topic}")
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.error(f"ZMQ socket error for {topic}")
        except Exception as e:
            _log.error(f"Error publishing to {topic}: {e}")
            
        return result

    @doc_inherit
    def historian_setup(self):
        """
        Establish connection to the target platform with proper synchronization
        """
        with self._connection_lock:
            if self._connection_state != self.CONNECTING:
                _log.warning(f"Historian setup called while in {self._connection_state} state")
                return
                
            _log.debug("Setting up to forward to {}".format(self.destination_vip))
            
            # Clean up any previous connection
            if self._target_platform is not None:
                try:
                    _log.debug("Cleaning up previous connection before establishing new one")
                    self._target_platform.core.stop()
                except Exception as e:
                    _log.warning(f"Error stopping previous connection: {e}")
                finally:
                    self._target_platform = None

            try:
                if self.destination_address:
                    address = self.destination_address
                elif self.destination_vip:
                    address = self.destination_vip
                else:
                    _log.error("No destination address configured")
                    self._connection_state = self.DISCONNECTED
                    return

                # Use a timeout for the connection attempt
                with gevent.Timeout(30):
                    value = self.core.connect_remote_platform(address, serverkey=self.destination_serverkey)

                    if isinstance(value, Agent):
                        self._target_platform = value
                        self._connection_state = self.CONNECTED
                        self._connection_retry_count = 0
                        self.vip.health.set_status(
                            STATUS_GOOD, f"Connected to address ({address})")
                        _log.info(f"Successfully connected to target at {address}")
                    else:
                        _log.error(f"Couldn't connect to address. Got Return value that is not Agent: ({address})")
                        self.vip.health.set_status(STATUS_BAD, "Invalid agent detected.")
                        self._connection_state = self.DISCONNECTED
                        self._connection_retry_count += 1

            except gevent.Timeout:
                _log.error(f"Timeout connecting to address: ({address})")
                self.vip.health.set_status(STATUS_BAD, "Timeout in setup of agent")
                self._connection_state = self.DISCONNECTED
                self._connection_retry_count += 1
            except Exception as ex:
                _log.error(f"Error connecting to {address}: {ex}")
                _log.error(traceback.format_exc())
                self.vip.health.set_status(STATUS_BAD, f"Connection error: {ex}")
                self._connection_state = self.DISCONNECTED
                self._connection_retry_count += 1

    @doc_inherit
    def historian_teardown(self):
        """
        Safely disconnect from target platform with proper synchronization
        """
        with self._connection_lock:
            # Only teardown if we're in a state that allows it
            if self._connection_state not in (self.CONNECTED, self.DISCONNECTING):
                _log.warning(f"Historian teardown called while in {self._connection_state} state")
                return
                
            _log.debug("Tearing down forwarding connection")
            self._connection_state = self.DISCONNECTING
            
            # Cancel any pending connection tasks
            if self._connection_task is not None and not self._connection_task.ready():
                self._connection_task.kill(block=False)
                self._connection_task = None
                
            # Kill the forwarding agent if it is currently running.
            if self._target_platform is not None:
                try:
                    # Use a timeout to ensure we don't hang on shutdown
                    with gevent.Timeout(5):
                        self._target_platform.core.stop()
                except gevent.Timeout:
                    _log.warning("Timeout while stopping target platform")
                except Exception as e:
                    _log.warning(f"Error stopping target platform: {e}")
                finally:
                    self._target_platform = None
                    
            self._connection_state = self.DISCONNECTED
            _log.debug("Connection teardown complete")
            
    def stop_process_thread(self):
        """
        Override the BaseHistorian's stop_process_thread to ensure we cleanly disconnect
        """
        # First tear down any connection to remote platform
        self.historian_teardown()
        
        # Then call parent implementation to stop the processing thread
        super().stop_process_thread()


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(historian, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
