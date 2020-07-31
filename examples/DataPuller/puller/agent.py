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


import datetime
import logging
import sys
import time
from urllib.parse import urlparse

import gevent

from volttron.platform.vip.agent import Agent, Core, compat
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD, Status)
from volttron.platform.keystore import KeyStore

FORWARD_TIMEOUT_KEY = 'FORWARD_TIMEOUT_KEY'
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.5'


def historian(config_path, **kwargs):
    config = utils.load_config(config_path)
    services_topic_list = config.get('services_topic_list', ['all'])
    custom_topic_list = config.get('custom_topic_list', [])
    topic_replace_list = config.get('topic_replace_list', [])
    source_vip = config.get('source-vip')
    hosts = KnownHostsStore()
    source_serverkey = hosts.serverkey(source_vip)
    if source_serverkey is None:
        _log.info("Source serverkey not found in known hosts file, using config")
        source_serverkey = config['source-serverkey']
    identity = config.get('identity', kwargs.pop('identity', None))
    include_destination_in_header = config.get('include_destination_in_header',
                                               False)

    origin = config.get('origin', None)
    overwrite_origin = config.get('overwrite_origin', False)
    include_origin_in_header = config.get('include_origin_in_header', False)
    if 'all' in services_topic_list:
        services_topic_list = [topics.DRIVER_TOPIC_BASE, topics.LOGGER_BASE,
                               topics.ACTUATOR, topics.ANALYSIS_TOPIC_BASE]

    class DataPuller(Agent):
        '''This historian pulls data from another platform.
        '''

        def __init__(self, **kwargs):
            # will be available in both threads.
            self._topic_replace_map = {}
            self._num_failures = 0
            self._last_timeout = 0
            self._target_platform = None
            super(DataPuller, self).__init__(**kwargs)

        @Core.receiver("onstart")
        def starting_base(self, sender, **kwargs):
            self.puller_setup()
            '''
            Subscribes to the platform message bus on the actuator, record,
            datalogger, and device topics to capture data.
            '''

            def subscriber(subscription, callback_method):
                _log.debug("subscribing to {}".format(subscription))
                self._target_platform.vip.pubsub.subscribe(peer='pubsub',
                                                           prefix=subscription,
                                                           callback=callback_method)

            _log.debug("Starting DataPuller")
            for topic_subscriptions in services_topic_list:
                subscriber(topic_subscriptions, self.on_message)

            for custom_topic in custom_topic_list:
                subscriber(custom_topic, self.on_message)

            self._started = True

        def timestamp(self):
            return time.mktime(datetime.datetime.now().timetuple())

        def on_message(self, peer, sender, bus, topic, headers, message):

            # Grab the timestamp string from the message (we use this as the
            # value in our readings at the end of this method)
            _log.debug("In capture data")
            timestamp_string = headers.get(headers_mod.DATE, None)

            data = message
            try:
                # 2.0 agents compatability layer makes sender = pubsub.compat
                # so we can do the proper thing when it is here
                _log.debug("message in capture_data {}".format(message))
                if sender == 'pubsub.compat':
                    # data = jsonapi.loads(message[0])
                    data = compat.unpack_legacy_message(headers, message)
                    _log.debug("data in capture_data {}".format(data))
                if isinstance(data, dict):
                    data = data
                elif isinstance(data, (int,float)):
                    data = data
                    # else:
                    #     data = data[0]
            except ValueError as e:
                log_message = "message for {topic} bad message string:" \
                              "{message_string}"
                _log.error(log_message.format(topic=topic,
                                              message_string=message[0]))
                raise

            if topic_replace_list:
                if topic in self._topic_replace_map.keys():
                    topic = self._topic_replace_map[topic]
                else:
                    self._topic_replace_map[topic] = topic
                    temptopics = {}
                    for x in topic_replace_list:
                        if x['from'] in topic:
                            new_topic = temptopics.get(topic, topic)
                            temptopics[topic] = new_topic.replace(
                                x['from'], x['to'])

                    for k, v in temptopics.items():
                        self._topic_replace_map[k] = v
                    topic = self._topic_replace_map[topic]

            payload = {'headers': headers, 'topic': topic, 'message': data}
            self.publish_to_self(topic, payload)

        #             self._event_queue.put({'source': "forwarded",
        #                                    'topic': topic,
        #                                    'readings': [(timestamp_string, payload)]})


        def publish_to_self(self, topic, payload):
            handled_records = []

            parsed = urlparse(self.core.address)
            next_dest = urlparse(source_vip)
            current_time = self.timestamp()
            last_time = self._last_timeout
            _log.debug('Lasttime: {} currenttime: {}'.format(last_time, current_time))
            timeout_occurred = False
            if self._last_timeout:
                # if we failed we need to wait 60 seconds before we go on.
                if self.timestamp() < self._last_timeout + 60:
                    _log.debug('Not allowing send < 60 seconds from failure')
                    return
            if not self._target_platform:
                self.puller_setup()
            if not self._target_platform:
                _log.debug('Could not connect to target')
                return

            headers = payload['headers']
            headers['X-Forwarded'] = True
            try:
                del headers['Origin']
            except KeyError:
                pass
            try:
                del headers['Destination']
            except KeyError:
                pass

            print("should publish", topic, payload)

            self.vip.pubsub.publish(
                peer='pubsub',
                topic=topic,
                headers=headers,
                message=payload['message']).get(30)

        def puller_setup(self):
            _log.debug("Setting up to forward to {}".format(source_vip))
            try:
                agent = build_agent(address=source_vip,
                                    serverkey=source_serverkey,
                                    publickey=self.core.publickey,
                                    secretkey=self.core.secretkey,
                                    enable_store=False)
            except gevent.Timeout:
                self.vip.health.set_status(
                    STATUS_BAD, "Timeout in setup of agent")
                status = Status.from_json(self.vip.health.get_status_json())
                self.vip.health.send_alert(FORWARD_TIMEOUT_KEY,
                                           status)
            else:
                self._target_platform = agent

    DataPuller.__name__ = 'DataPuller'
    return DataPuller(identity=identity,
                      **kwargs)


def main(argv=sys.argv):
    '''Main method called by the aip.'''
    try:
        utils.vip_main(historian)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
