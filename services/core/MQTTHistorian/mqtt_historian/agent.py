# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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
import gevent

from volttron.platform.agent.base_historian import BaseHistorian, add_timing_data_to_header
from volttron.platform.agent import utils

from paho.mqtt.client import MQTTv311, MQTTv31
import paho.mqtt.publish as publish


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class MQTTHistorian(BaseHistorian):
    """This historian publishes data to MQTT.
    """

    def __init__(self, config_path, **kwargs):
        config = utils.load_config(config_path)


        # We pass every optional parameter to the MQTT library functions so they
        # default to the same values that paho uses as defaults.
        self.mqtt_qos = config.get('mqtt_qos', 0)
        self.mqtt_retain = config.get('mqtt_retain', False)

        self.mqtt_hostname = config.get('mqtt_hostname', 'localhost')
        self.mqtt_port = config.get('mqtt_port', 1883)
        self.mqtt_client_id = config.get('mqtt_client_id', '')
        self.mqtt_keepalive = config.get('mqtt_keepalive', 60)
        self.mqtt_will = config.get('mqtt_will', None)
        self.mqtt_auth = config.get('mqtt_auth', None)
        self.mqtt_tls = config.get('mqtt_tls', None)

        protocol = config.get('mqtt_protocol', MQTTv311)
        if protocol == "MQTTv311":
            protocol = MQTTv311
        elif protocol == "MQTTv31":
            protocol = MQTTv31

        if protocol not in (MQTTv311, MQTTv31):
            raise ValueError("Unknown MQTT protocol: {}".format(protocol))

        self.mqtt_protocol = protocol

        # will be available in both threads.
        self._last_error = 0

        super(MQTTHistorian, self).__init__(**kwargs)

    def timestamp(self):
        return time.mktime(datetime.datetime.now().timetuple())

    def publish_to_historian(self, to_publish_list):
        _log.debug("publish_to_historian number of items: {}"
                   .format(len(to_publish_list)))
        current_time = self.timestamp()

        if self._last_error:
            # if we failed we need to wait 60 seconds before we go on.
            if self.timestamp() < self._last_error + 60:
                _log.debug('Not allowing send < 60 seconds from failure')
                return

        to_send = []
        for x in to_publish_list:
            topic = x['topic']

            # Construct payload from data in the publish item.
            # Available fields: 'value', 'headers', and 'meta'
            payload = x['value']

            to_send.append({'topic': topic,
                            'payload': payload,
                            'qos': self.mqtt_qos,
                            'retain': self.mqtt_retain})

        try:
            publish.multiple(to_send,
                             hostname=self.mqtt_hostname,
                             port=self.mqtt_port,
                             client_id=self.mqtt_client_id,
                             keepalive=self.mqtt_keepalive,
                             will=self.mqtt_will,
                             auth=self.mqtt_auth,
                             tls=self.mqtt_tls,
                             protocol=self.mqtt_protocol)
            self.report_all_handled()
        except Exception as e:
            _log.warning("Exception ({}) raised by publish: {}".format(
                e.__class__.__name__,
                e.message))
            self._last_error = self.timestamp()


def main(argv=sys.argv):
    utils.vip_main(MQTTHistorian)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
