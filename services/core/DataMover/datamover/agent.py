# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
from volttron.platform.agent.known_identities import PLATFORM_HISTORIAN

DATAMOVER_TIMEOUT_KEY = 'DATAMOVER_TIMEOUT_KEY'
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


def historian(config_path, **kwargs):
    config = utils.load_config(config_path)
    destination_vip = config.get('destination-vip', None)
    assert destination_vip is not None

    hosts = KnownHostsStore()
    serverkey = hosts.serverkey(destination_vip)
    if serverkey is not None:
        config['destination-serverkey'] = serverkey
    else:
        assert config.get('destination-serverkey') is not None
        _log.info("Destination serverkey not found in known hosts file, "
                  "using config")

    utils.update_kwargs_with_config(kwargs, config)
    return DataMover(**kwargs)


class DataMover(BaseHistorian):
    """This historian forwards data to another platform.
    """

    def __init__(self, destination_vip, destination_serverkey,
                 destination_historian_identity=PLATFORM_HISTORIAN,
                 remote_identity=None,
                 **kwargs):
        """
        
        :param destination_vip: vip address of the destination volttron 
        instance
        :param destination_serverkey: public key of the destination server
        :param services_topic_list: subset of topics that are inherently 
        supported by base historian. Default is device, analysis, logger, 
        and record topics
        :param custom_topic_list: any additional topics this historian 
        should subscribe to.
        :param destination_historian_identity: vip identity of the 
        destination historian. default is 'platform.historian'
        :param kwargs: additional arguments to be passed along to parent class
        """
        kwargs["process_loop_in_greenlet"] = True
        super(DataMover, self).__init__(**kwargs)
        self.destination_vip = destination_vip
        self.destination_serverkey = destination_serverkey
        self.destination_historian_identity = destination_historian_identity
        self.remote_identity = remote_identity
        self._target_platform = None
        
        config = {"destination_vip":self.destination_vip,
                  "destination_serverkey": self.destination_serverkey,
                  "destination_historian_identity": self.destination_historian_identity,
                  "remote_identity": self.remote_identity}

        self.update_default_config(config)

        # will be available in both threads.
        self._last_timeout = 0

    def configure(self, configuration):
        self.destination_vip = str(configuration.get('destination_vip', ""))
        self.destination_serverkey = str(configuration.get('destination_serverkey', ""))
        self.destination_historian_identity = str(configuration.get('destination_historian_identity', PLATFORM_HISTORIAN))
        self.remote_identity = configuration.get("remote_identity")

    #Redirect the normal capture functions to capture_data.
    def _capture_device_data(self, peer, sender, bus, topic, headers, message):
        self.capture_data(peer, sender, bus, topic, headers, message)

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
        _log.debug("In capture data")
        timestamp_string = headers.get(headers_mod.DATE, None)

        data = message
        try:
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

        topic = self.get_renamed_topic(topic)

        if self.gather_timing_data:
            add_timing_data_to_header(
                headers,
                self.core.agent_uuid or self.core.identity,
                "collected")

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

            if self.gather_timing_data:
                add_timing_data_to_header(
                    headers,
                    self.core.agent_uuid or self.core.identity,
                    "forwarded")

            to_send.append({'topic': topic,
                            'headers': headers,
                            'message': message})

        with gevent.Timeout(30):
            try:
                _log.debug("Sending to destination historian.")
                self._target_platform.vip.rpc.call(
                    self.destination_historian_identity, 'insert',
                    to_send).get(timeout=10)
                self.report_all_handled()
            except gevent.Timeout:
                self._last_timeout = self.timestamp()
                self._target_platform.core.stop()
                self._target_platform = None
                _log.error("Timeout when attempting to publish to target.")
                self.vip.health.set_status(
                    STATUS_BAD, "Timeout occurred")

    def historian_setup(self):
        _log.debug("Setting up to forward to {}".format(self.destination_vip))
        try:
            agent = build_agent(address=self.destination_vip,
                                identity=self.remote_identity,
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

    def historian_teardown(self):
        # Kill the forwarding agent if it is currently running.
        if self._target_platform is not None:
            self._target_platform.core.stop()
            self._target_platform = None


def main(argv=sys.argv):
    utils.vip_main(historian)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
