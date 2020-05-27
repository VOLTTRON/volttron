# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

import logging
import sys
import re
import zlib
import base64
from collections import defaultdict

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent import Core
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.utils import process_timestamp, \
    get_aware_utc_now, get_utc_seconds_from_epoch
from volttron.platform.vip.agent import compat

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.0.1'
ALL_REX = re.compile('.*/all$')


class PrometheusScrapeAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(PrometheusScrapeAgent, self).__init__(enable_web=True, **kwargs)
        if isinstance(config_path, dict):
            self._config_dict = config_path
        else:
            self._config_dict = utils.load_config(config_path)
        self._cache = defaultdict(dict)
        self._cache_time = self._config_dict.get('cache_timeout', 660)
        self._tag_delimiter_re = self._config_dict.get('tag_delimiter_re',
                                                       "\s+|:|_|\.|/")

    @Core.receiver("onstart")
    def _starting(self, sender, **kwargs):
        self.vip.web.register_endpoint('/promscrape', self.scrape, "raw")
        self.vip.web.register_endpoint('/promscrapetest', self.web_test)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topics.DRIVER_TOPIC_BASE,
                                  callback=self._capture_device_data)

    @Core.receiver("onstop")
    def _stopping(self, sender, **kwargs):
        pass

    def web_test(self, env, data):
        return {"data": "another test and stuff", "otherdata": "more testing yo"}

    def scrape(self, env, data):
        scrape_time = get_utc_seconds_from_epoch()
        keys_to_delete = defaultdict(list)
        if len(self._cache) > 0:
            result = "# TYPE volttron_data gauge\n"
            for device, device_topics in self._cache.items():
                device_tags = device.replace("-", "_").split('/')
                for topic, value in device_topics.items():
                    if value[1] + self._cache_time > scrape_time:
                        metric_props = re.split(self._tag_delimiter_re,
                                                topic.lower())
                        metric_tag_str = (
                            "campus=\"{}\",building=\"{}\","
                            "device=\"{}\",").format(*device_tags)
                        for i, prop in enumerate(metric_props):
                            metric_tag_str += "tag{}=\"{}\",".format(i, prop)
                        result += "{}{{{}topic=\"{}\"}} {}\n".format(
                            re.sub(" |/|-", "_", device), metric_tag_str,
                            topic.replace(" ", "_"), value[0])
                    else:
                        try:
                            keys_to_delete[device].append(topic)
                        except Exception as e:
                            _log.error("Could not delete stale topic")
                            _log.exception(e)
                        continue
        else:
            result = "#No Data to Scrape"
        for device, delete_topics in keys_to_delete.items():
            for topic in delete_topics:
                del self._cache[device][topic]
        gzip_compress = zlib.compressobj(9, zlib.DEFLATED,
                                         zlib.MAX_WBITS | 16)
        data = gzip_compress.compress(result) + gzip_compress.flush()

        return "200 OK", base64.b64encode(data).decode('ascii'), [
            ('Content-Type', 'text/plain'),
            ('Content-Encoding', 'gzip')]

    def _clean_compat(self, sender, topic, headers, message):
        try:
            # 2.0 agents compatability layer makes sender == pubsub.compat so
            # we can do the proper thing when it is here
            if sender == 'pubsub.compat':
                data = compat.unpack_legacy_message(headers, message)
            else:
                data = message
            return data
        except ValueError as e:
            _log.error("message for {topic} bad message string: "
                       "{message_string}".format(topic=topic,
                                                 message_string=message[0]))
            raise e

        except IndexError as e:
            _log.error("message for {topic} missing message string".format(
                topic=topic))
            raise e

    def _capture_log_data(self, peer, sender, bus, topic, headers, message):
        """Capture log data and submit it to be published by a historian."""
        try:
            data = self._clean_compat(sender, topic, headers, message)
        except:
            return

        for point, item in data.items():
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
            message = self._clean_compat(sender, topic, headers, message)
        except Exception as e:
            _log.exception(e)
            return
        try:
            if isinstance(message, dict):
                values = message
            else:
                values = message[0]
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

        for key, value in values.items():
            self._add_to_cache(device, key, value)

    def _add_to_cache(self, device, topic, value):
        cached_time = get_utc_seconds_from_epoch()
        try:
            self._cache[device][topic] = (float(value), cached_time)
        except:
            _log.error(
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
