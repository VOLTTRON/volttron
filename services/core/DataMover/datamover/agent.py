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
import threading
import gevent

from volttron.platform.vip.agent import Agent, Core, compat
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.agent.base_historian import BaseHistorian, add_timing_data_to_header
from volttron.platform.agent import utils
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.messaging.health import STATUS_BAD, Status

DATAMOVER_TIMEOUT_KEY = 'DATAMOVER_TIMEOUT_KEY'
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


def historian(config_path, **kwargs):
    config = utils.load_config(config_path)
    services_topic_list = config.get('services_topic_list', [
        topics.DRIVER_TOPIC_BASE,
        topics.LOGGER_BASE,
        topics.ACTUATOR,
        topics.ANALYSIS_TOPIC_BASE
    ])
    custom_topic_list = config.get('custom_topic_list', [])
    topic_replace_list = config.get('topic_replace_list', [])
    destination_vip = config.get('destination-vip')
    destination_historian_identity = config.get('destination-historian-identity',
                                                'platform.historian')
    backup_storage_limit_gb = config.get('backup_storage_limit_gb', None)

    gather_timing_data = config.get('gather_timing_data', False)

    hosts = KnownHostsStore()
    destination_serverkey = hosts.serverkey(destination_vip)
    if destination_serverkey is None:
        _log.info("Destination serverkey not found in known hosts file, using config")
        destination_serverkey = config['destination-serverkey']

    return DataMover(services_topic_list,
                     custom_topic_list,
                     topic_replace_list,
                     destination_vip,
                     destination_serverkey,
                     destination_historian_identity,
                     gather_timing_data,
                     backup_storage_limit_gb=backup_storage_limit_gb,
                     **kwargs)


class DataMover(BaseHistorian):
    """This historian forwards data to another platform.
    """

    def __init__(self,
                 services_topic_list,
                 custom_topic_list,
                 topic_replace_list,
                 destination_vip,
                 destination_serverkey,
                 destination_historian_identity,
                 gather_timing_data,
                 **kwargs):

        self.services_topic_list = services_topic_list
        self.custom_topic_list = custom_topic_list
        self.topic_replace_list = topic_replace_list
        self.destination_vip = destination_vip
        self.destination_serverkey = destination_serverkey
        self.destination_historian_identity = destination_historian_identity
        self.gather_timing_data = gather_timing_data

        # will be available in both threads.
        self._topic_replace_map = {}
        self._last_timeout = 0
        super(DataMover, self).__init__(**kwargs)

    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Subscribes to the platform message bus on the actuator, record,
        datalogger, and device topics to capture data.
        """
        _log.debug("Starting DataMover")

        for topic in self.services_topic_list + self.custom_topic_list:
            _log.debug("subscribing to {}".format(topic))
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self.capture_data)
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
                data = compat.unpack_legacy_message(headers, message)
                _log.debug("data in capture_data {}".format(data))
            if isinstance(data, dict):
                data = data
            elif isinstance(data, int) or \
                    isinstance(data, float) or \
                    isinstance(data, long):
                data = data
        except ValueError as e:
            log_message = "message for {topic} bad message string:" \
                          "{message_string}"
            _log.error(log_message.format(topic=topic,
                                          message_string=message[0]))
            raise

        if self.topic_replace_list:
            if topic in self._topic_replace_map.keys():
                topic = self._topic_replace_map[topic]
            else:
                self._topic_replace_map[topic] = topic
                temptopics = {}
                for x in self.topic_replace_list:
                    if x['from'] in topic:
                        new_topic = temptopics.get(topic, topic)
                        temptopics[topic] = new_topic.replace(
                            x['from'], x['to'])

                for k, v in temptopics.items():
                    self._topic_replace_map[k] = v
                topic = self._topic_replace_map[topic]

        if self._gather_timing_data:
            add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "collected")

        payload = {'headers': headers, 'message': data}

        self._event_queue.put({'source': "forwarded",
                               'topic': topic,
                               'readings': [(timestamp_string, payload)]})

    def publish_to_historian(self, to_publish_list):
        _log.debug("publish_to_historian number of items: {}"
                   .format(len(to_publish_list)))
        current_time = self.timestamp()
        last_time = self._last_timeout
        _log.debug('Last timeout: {} current time: {}'.format(last_time,
                                                              current_time))
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

        to_send = []
        for x in to_publish_list:
            topic = x['topic']
            headers = x['value']['headers']
            message = x['value']['message']

            if self._gather_timing_data:
                add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "forwarded")

            to_send.append({'topic': topic,
                            'headers': headers,
                            'message': message})

        try:
            self._target_platform.vip.rpc.call(self.destination_historian_identity,
                                               'insert', to_send).get(timeout=10)
            self.report_all_handled()
        except gevent.Timeout:
            self._last_timeout = self.timestamp()
            self._target_platform.core.stop()
            self._target_platform = None
            self.vip.health.set_status(
                STATUS_BAD, "Timeout occurred")

    def historian_setup(self):
        _log.debug("Setting up to forward to {}".format(self.destination_vip))
        try:
            agent = build_agent(address=self.destination_vip,
                                serverkey=self.destination_serverkey,
                                publickey=self.core.publickey,
                                secretkey=self.core.secretkey,
                                enable_store=False)
        except gevent.Timeout:
            self.vip.health.set_status(
                STATUS_BAD, "Timeout in setup of agent")
            status = Status.from_json(self.vip.health.get_status())
            self.vip.health.send_alert(DATAMOVER_TIMEOUT_KEY,
                                       status)
        else:
            self._target_platform = agent


def main(argv=sys.argv):
    utils.vip_main(historian)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
