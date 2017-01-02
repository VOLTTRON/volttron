# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
from __future__ import absolute_import, print_function

import datetime
import logging
import sys
import time
import traceback
from urlparse import urlparse

import gevent

from volttron.platform.vip.agent import Agent, Core, compat, Unreachable
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD, Status)

FORWARD_TIMEOUT_KEY = 'FORWARD_TIMEOUT_KEY'
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.7'


def historian(config_path, **kwargs):
    config = utils.load_config(config_path)
    services_topic_list = config.get('services_topic_list', ['all'])
    custom_topic_list = config.get('custom_topic_list', [])
    topic_replace_list = config.get('topic_replace_list', [])
    destination_vip = config.get('destination-vip')

    hosts = KnownHostsStore()
    destination_serverkey = hosts.serverkey(destination_vip)
    if destination_serverkey is None:
        _log.info("Destination serverkey not found in known hosts file, using config")
        destination_serverkey = config['destination-serverkey']

    required_target_agents = config.get('required_target_agents', [])
    backup_storage_limit_gb = config.get('backup_storage_limit_gb', None)
    if 'all' in services_topic_list:
        services_topic_list = [topics.DRIVER_TOPIC_BASE, topics.LOGGER_BASE,
                               topics.ACTUATOR, topics.ANALYSIS_TOPIC_BASE]

    class ForwardHistorian(BaseHistorian):
        """
        This historian forwards data to another platform.
        """

        def __init__(self, **kwargs):
            # will be available in both threads.
            self._topic_replace_map = {}
            self._num_failures = 0
            self._last_timeout = 0
            super(ForwardHistorian, self).__init__(**kwargs)

        @Core.receiver("onstart")
        def starting_base(self, sender, **kwargs):
            """
            Subscribes to the platform message bus on the actuator, record,
            datalogger, and device topics to capture data.
            """

            def subscriber(subscription, callback_method):
                _log.debug("subscribing to {}".format(subscription))
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=subscription,
                                          callback=callback_method)

            _log.debug("Starting Forward historian")
            for topic_subscriptions in services_topic_list:
                subscriber(topic_subscriptions, self.capture_data)

            for custom_topic in custom_topic_list:
                subscriber(custom_topic, self.capture_data)

            self._started = True

        def timestamp(self):
            return time.mktime(datetime.datetime.now().timetuple())

        def capture_data(self, peer, sender, bus, topic, headers, message):

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
                elif isinstance(data, int) or \
                        isinstance(data, float) or \
                        isinstance(data, long):
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

            payload = {'headers': headers, 'message': data}

            self._event_queue.put({'source': "forwarded",
                                   'topic': topic,
                                   'readings': [(timestamp_string, payload)]})

        def publish_to_historian(self, to_publish_list):
            handled_records = []

            _log.debug("publish_to_historian number of items: {}"
                       .format(len(to_publish_list)))
            parsed = urlparse(self.core.address)
            next_dest = urlparse(destination_vip)
            current_time = self.timestamp()
            last_time = self._last_timeout
            _log.debug('Lasttime: {} currenttime: {}'.format(last_time,
                                                             current_time))
            timeout_occurred = False
            if self._last_timeout:
                # if we failed we need to wait 60 seconds before we go on.
                if self.timestamp() < self._last_timeout + 60:
                    _log.debug('Not allowing send < 60 seconds from failure')
                    return
            if not self._target_platform:
                self.historian_setup()
            if not self._target_platform:
                _log.debug('Could not connect to target')
                return

            for vip_id in required_target_agents:
                try:
                    self._target_platform.vip.ping(vip_id).get()
                except Unreachable:
                    skip = "Skipping publish: Target platform not running " \
                           "required agent {}".format(vip_id)
                    _log.warn(skip)
                    self.vip.health.set_status(
                        STATUS_BAD, skip)
                    return
                except Exception as e:
                    err = "Unhandled error publishing to target platfom."
                    _log.error(err)
                    _log.error(traceback.format_exc())
                    self.vip.health.set_status(
                        STATUS_BAD, err)
                    return

            for x in to_publish_list:
                topic = x['topic']
                value = x['value']
                # payload = jsonapi.loads(value)
                payload = value
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

                if timeout_occurred:
                    _log.error(
                        'A timeout has occured so breaking out of publishing')
                    break
                with gevent.Timeout(30):
                    try:
                        _log.debug('debugger: {} {} {}'.format(topic,
                                                               headers,
                                                               payload))
                        self._target_platform.vip.pubsub.publish(
                            peer='pubsub',
                            topic=topic,
                            headers=headers,
                            message=payload['message']).get()
                    except gevent.Timeout:
                        _log.debug("Timeout occurred email should send!")
                        timeout_occurred = True
                        self._last_timeout = self.timestamp()
                        self._num_failures += 1
                        # Stop the current platform from attempting to
                        # connect
                        self._target_platform.core.stop()
                        self._target_platform = None
                        self.vip.health.set_status(
                            STATUS_BAD, "Timeout occured")
                    except Exception as e:
                        err = "Unhandled error publishing to target platfom."
                        _log.error(err)
                        _log.error(traceback.format_exc())
                        self.vip.health.set_status(
                            STATUS_BAD, err)
                        # Before returning lets mark any that weren't errors
                        # as sent.
                        self.report_handled(handled_records)
                        return
                    else:
                        handled_records.append(x)

            _log.debug("handled: {} number of items".format(
                len(to_publish_list)))
            self.report_handled(handled_records)

            if timeout_occurred:
                _log.debug('Sending alert from the ForwardHistorian')
                status = Status.from_json(self.vip.health.get_status())
                self.vip.health.send_alert(FORWARD_TIMEOUT_KEY,
                                           status)
            else:
                self.vip.health.set_status(
                    STATUS_GOOD,"published {} items".format(
                        len(to_publish_list)))

        def historian_setup(self):
            _log.debug("Setting up to forward to {}".format(destination_vip))
            try:
                agent = build_agent(address=destination_vip,
                                    serverkey=destination_serverkey,
                                    publickey=self.core.publickey,
                                    secretkey=self.core.secretkey,
                                    enable_store=False)

            except gevent.Timeout:
                self.vip.health.set_status(
                    STATUS_BAD, "Timeout in setup of agent")
                status = Status.from_json(self.vip.health.get_status())
                self.vip.health.send_alert(FORWARD_TIMEOUT_KEY,
                                           status)
            else:
                self._target_platform = agent


    return ForwardHistorian(backup_storage_limit_gb=backup_storage_limit_gb,
                            **kwargs)


def main(argv=sys.argv):
    """Main method called by the aip."""
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
