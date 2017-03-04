# -*- coding: utf-8 -*- {{{

import logging
import sys
import re
from collections import defaultdict

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent import Core
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.utils import process_timestamp, \
    get_aware_utc_now
from volttron.platform.vip.agent import compat

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.0.1'
ALL_REX = re.compile('.*/all$')


class PrometheusScrapeAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(PrometheusScrapeAgent, self).__init__(enable_web=True, **kwargs)
        self._cache = defaultdict(dict)

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
        if len(self._cache) > 0:
            result = ""
            for device, device_topics in self._cache.iteritems():
                for topic, value in device_topics.iteritems():
                    metric_props = re.split("\s+|:|_|/", topic)
                    metric_tag_str = ""
                    for i, prop in enumerate(metric_props):
                        metric_tag_str += "tag{}=\"{}\",".format(i, prop)
                    result += ("# TYPE volttron_data gauge\n"
                               "{}{{{}topic=\"{}\"}} {}\n").format(
                        device.replace("-", "_"), metric_tag_str,
                        topic.replace(" ", "_"), value)
        else:
            result = "#No Data to Scrape"

        return {'text': result}

    def _capture_log_data(self, peer, sender, bus, topic, headers, message):
        """Capture log data and submit it to be published by a historian."""

        # Anon the topic if necessary.
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

            self._add_to_cache(topic, point, readings[1])

    def _capture_device_data(self, peer, sender, bus, topic, headers,
                             message):
        """Capture device data and submit it to be published by a historian.

        Filter out only the */all topics for publishing to the historian.
        """

        if not ALL_REX.match(topic):
            return

        # Because of the above if we know that all is in the topic so
        # we strip it off to get the base device
        parts = topic.split('/')
        device = '/'.join(parts[1:-1])
        self._capture_data(peer, sender, bus, topic, headers, message, device)

    def _capture_data(self, peer, sender, bus, topic, headers, message,
                      device):
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

        if topic.startswith('analysis'):
            source = 'analysis'
        else:
            source = 'scrape'
        _log.debug(
            "Queuing {topic} from {source} for publish".format(topic=topic,
                                                               source=source))

        for key, value in values.iteritems():
            self._add_to_cache(device, topic, value)

    def _add_to_cache(self, device, topic, value):
        try:
            self._cache[device][topic] = float(value)
        except:
            _log.debug(
                "Topic \"{}\" on device \"{}\" contained value that was not "
                "castable as float".format(topic, device))


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
