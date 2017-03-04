# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

import logging
import sys
import re

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent import PubSub
from volttron.platform.vip.agent import Core
from volttron.platform.messaging import topics, headers as headers_mod

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.0.1'
ALL_REX = re.compile('.*/all$')


class PrometheusScrapeAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(PrometheusScrapeAgent, self).__init__(enable_web=True,**kwargs)
        self._cache = {}

    @Core.receiver("onstart")
    def _starting(self, sender, **kwargs):
        self.vip.web.register_endpoint('/promscrape', self.scrape)
        self.vip.pubsub.subscribe(peer='pubsub',
                                    prefix=topics.DRIVER_TOPIC_BASE,
                                    callback=self._capture_device_data)



    @Core.receiver("onstop")
    def _stopping(self, sender, **kwargs):
        pass

    def scrape(self, env, data):
        _log.debug("made it to scrape")
        if len(self._cache) > 0:
            result = ""
            for key, value in self._cache.iteritems():
                result += """
    # TYPE volttron_data guage
    {} {}
                """.format(key, value)
        else:
            result = "#No Data to Scrape"

        return {'text': result}


    def _capture_log_data(self, peer, sender, bus, topic, headers, message):
        """Capture log data and submit it to be published by a historian."""

        # Anon the topic if necessary.
        topic = self._get_topic(topic)
        try:
            # 2.0 agents compatability layer makes sender == pubsub.compat so
            # we can do the proper thing when it is here
            if sender == 'pubsub.compat':
                data = compat.unpack_legacy_message(headers, message)
            else:
                data = message
        except ValueError as e:
            _log.error("message for {topic} bad message string: "
                       "{message_string}".format(topic=topic,
                                                 message_string=message[0]))
            return
        except IndexError as e:
            _log.error("message for {topic} missing message string".format(
                topic=topic))
            return

        for point, item in data.iteritems():
            if 'Readings' not in item or 'Units' not in item:
                _log.error("logging request for {topic} missing Readings "
                           "or Units".format(topic=topic))
                continue
            units = item['Units']
            dtype = item.get('data_type', 'float')
            tz = item.get('tz', None)
            if dtype == 'double':
                dtype = 'float'

            meta = {'units': units, 'type': dtype}

            readings = item['Readings']

            if not isinstance(readings, list):
                readings = [(get_aware_utc_now(), readings)]
            elif isinstance(readings[0], str):
                my_ts, my_tz = process_timestamp(readings[0], topic)
                readings = [(my_ts, readings[1])]
                if tz:
                    meta['tz'] = tz
                elif my_tz:
                    meta['tz'] = my_tz

            self._add_to_cache(topic + '/' + point, reading[1])


    def _capture_device_data(self, peer, sender, bus, topic, headers,
                             message):
        """Capture device data and submit it to be published by a historian.

        Filter out only the */all topics for publishing to the historian.
        """

        if not ALL_REX.match(topic):
            return

        # Anon the topic if necessary.
        topic = self._get_topic(topic)

        # Because of the above if we know that all is in the topic so
        # we strip it off to get the base device
        parts = topic.split('/')
        device = '/'.join(parts[1:-1])
        self._capture_data(peer, sender, bus, topic, headers, message, device)


    def _capture_data(self, peer, sender, bus, topic, headers, message,
                      device):
        # Anon the topic if necessary.
        topic = self._get_topic(topic)
        timestamp_string = headers.get(headers_mod.DATE, None)
        timestamp = get_aware_utc_now()
        if timestamp_string is not None:
            timestamp, my_tz = process_timestamp(timestamp_string, topic)
        try:
            # 2.0 agents compatability layer makes sender == pubsub.compat so
            # we can do the proper thing when it is here
            if sender == 'pubsub.compat':
                message = compat.unpack_legacy_message(headers, message)

            if isinstance(message, dict):
                values = message
            else:
                values = message[0]

        except ValueError as e:
            _log.error("message for {topic} bad message string: "
                       "{message_string}".format(topic=topic,
                                                 message_string=message[0]))
            return
        except IndexError as e:
            _log.error("message for {topic} missing message string".format(
                topic=topic))
            return
        except Exception as e:
            _log.exception(e)
            return

        meta = {}
        if not isinstance(message, dict):
            meta = message[1]

        if topic.startswith('analysis'):
            source = 'analysis'
        else:
            source = 'scrape'
        _log.debug(
            "Queuing {topic} from {source} for publish".format(topic=topic,
                                                               source=source))

        for key, value in values.iteritems():
            point_topic = device + '/' + key
            self._add_to_cache(point_topic, value)


    def _add_to_cache(topic, value):
        try:
            self._cache[topic] = float(value)
        except:
            _log.debug("Topic \"{}\" contained value that was not castable as float".format(topic))


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""

    try:
        utils.vip_main(PrometheusScrapeAgent, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
