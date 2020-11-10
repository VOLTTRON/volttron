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

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.scheduling import periodic
import grequests
import gevent
import xml.etree.ElementTree as ET
import datetime
from collections import defaultdict
from volttron.platform.messaging import headers as headers_mod

TOPIC_DELIM = '/'

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "1.0"


def obix_history(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of the agent created using that configuration.
    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: ObixHistory
    :rtype: ObixHistory
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    url = config.get('url')
    username = config.get('username')
    password = config.get('password')

    path_prefix = config.get("path_prefix", "devices/obix/history")

    try:
        check_interval = float(config.get('check_interval', 15))
    except ValueError:
        _log.warning("bad check interval, defaulting to 15")
        check_interval = 15

    register_config = config.get('register_config')
    historian_name = config.get('historian_name')
    default_last_read = config.get('default_last_read', 24)

    return ObixHistory(url,
                       username,
                       password,
                       check_interval,
                       path_prefix,
                       register_config,
                       historian_name,
                       default_last_read,
                       **kwargs)


class Register(object):

    def __init__(self, url, device_topic, point_name, obix_point, last_read):
        self.url = url
        self.point_name = point_name
        self.interface_point_name = point_name.replace(" ", "$20").replace("-", "$2d")
        self.obix_name = obix_point
        self.device_topic = device_topic
        self.last_read = last_read
        self.index = device_topic+TOPIC_DELIM+point_name
        self.units = None

    def get_value_async_result(self, username=None, password=None, start_time=None, end_time=None):
        if end_time is None:
            end_time = utils.get_aware_utc_now()

        url = self.url + self.interface_point_name + '/~historyQuery'

        if isinstance(start_time, str):
            start_time = utils.parse_timestamp_string(start_time)

        # becchp.com does not accept percent-encoded parameters
        # requests is not configurable to not encode (from lead dev: https://stackoverflow.com/a/23497903)
        # do it manually:
        payload = {'start': self.time_format(start_time),
                   'end': self.time_format(end_time)}
        payload_str = "&".join("%s=%s" % (k, v) for k, v in payload.items())

        return grequests.get(url, auth=(username, password), params=payload_str)

    def time_format(self, dt):
        """
        Format timestamp for becchp.com query
        """
        _log.debug("time_format dt: {}".format(dt))
        return "%s:%06.3f%s" % (
            dt.strftime('%Y-%m-%dT%H:%M'),
            float("%.3f" % (dt.second + dt.microsecond / 1e6)),
            dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
        )

    def parse_result(self, xml_tree):
        obix_types = {'int': int,
                      'bool': bool,
                      'real': float}
        obix_schema_spec = '{http://obix.org/ns/schema/1.0}'
        root = ET.fromstring(xml_tree)
        value_def = root.findall(".{0}obj[@href='#RecordDef']*[@name='value']".format(obix_schema_spec))

        if len(value_def) == 0:
            _log.debug("No values since last read on {}/{}".format(self.device_topic, self.point_name))
            return None
        elif len(value_def) > 1:
            _log.debug("xml does not match obix standard schema")
            return None
        else:
            value_def = value_def[0]

        value_tag = value_def.tag[len(obix_schema_spec):]
        units = value_def.attrib['unit'][11:]  # remove "obix:units/" from string
        if self.units != units:
            _log.debug("Changing units for register {} from {} to {}".format(self.index, self.units, units))
            self.units = units

        records = root.findall(".{0}list/".format(obix_schema_spec))

        # Times are rounded down to the nearest minute
        def parse_timestamp(timestamp):
            timestamp = utils.parse_timestamp_string(timestamp)
            timestamp = timestamp.replace(second=0, microsecond=0)
            timestamp = utils.format_timestamp(timestamp)
            return timestamp

        times = [parse_timestamp(record.find("./*[@name='timestamp']").attrib['val']) for record in records]

        values = [obix_types[value_tag](record.find("./*[@name='value']").attrib['val']) for record in records]

        result = {}
        for i, time in enumerate(times):
            result[time] = [values[i], self.units]

        return result


class ObixHistory(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, url=None,
                 username=None,
                 password=None,
                 check_interval=15,
                 path_prefix="devices/obix/history",
                 register_config=None,
                 historian_name=None,
                 default_last_read=24,
                 **kwargs):
        super(ObixHistory, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.url = url
        self.username = username
        self.password = password
        self.check_interval = check_interval
        self.path_prefix = path_prefix
        self.register_config = register_config
        self.last_read = None
        self.default_last_read = default_last_read

        self.topics = None
        self.historian_name = ""

        self.scheduled_update = None
        self.registers = list()

        self.default_config = {"url": url,
                               "password": password,
                               "username": username,
                               "check_interval": check_interval,
                               "path_prefix": path_prefix,
                               "register_config": register_config,
                               "historian_name": historian_name}

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. If a configuration exists at startup
        this will be called before onstart.
        Is called every time the configuration in the store changes.
        """
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")

        url = config["url"]
        if not url.endswith('/'):
            url += '/'
        username = config["username"]
        password = config["password"]
        path_prefix = config["path_prefix"]
        if not path_prefix.endswith('/'):
            path_prefix += '/'

        try:
            check_interval = float(config['check_interval'])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        register_config = config['register_config']

        historian_name = config.get('historian_name')

        self.url = url
        self.username = username
        self.password = password
        self.check_interval = check_interval
        self.path_prefix = path_prefix
        self.register_config = register_config
        self.historian_name = historian_name

        self.configure_registers(register_config)

        if self.last_read is None:
            self.set_last_read()

        self.restart_greenlet()

    def set_last_read(self):
        try:
            last_read = self.vip.config.get('last_read')
        except (Exception, gevent.Timeout) as e:
            _log.debug(e)
            last_read = None

        if last_read is not None:
            if type(last_read) is not dict:
                _log.error("ERROR PROCESSING CONFIGURATION: last_read file does not contain dictionary")
                last_read = None

        if last_read is None:
            last_read = {}

        backup_last_read = utils.format_timestamp(utils.get_aware_utc_now() + datetime.timedelta(
            hours=-1*self.default_last_read))

        for r in self.registers:
            new_last_read = last_read.get(r.index, backup_last_read)
            last_read[r.index] = r.last_read = new_last_read

        self.last_read = last_read

    def restart_greenlet(self):
        if self.scheduled_update is not None:
            self.scheduled_update.cancel()
            self.scheduled_update = None

        # Don't start (or restart) the greenlet if we haven't processed the registry config
        # or there are no registers processed.
        if self.registers:
            self.scheduled_update = self.core.schedule(periodic(self.check_interval*60), self.update)

    def configure_registers(self, register_config):
        if not register_config:
            _log.warning("No registers configured.")
            return

        self.topics = []  # used to index registers
        self.registers = []
        for register_line in register_config:
            if "Device Name" not in register_line or "Volttron Point Name" not in register_line or \
                    "Obix Name" not in register_line:
                _log.warning("Column missing from configuration file line: {}".format(register_line))
                continue
            device_topic = self.path_prefix + register_line['Device Name']
            point_name = register_line["Volttron Point Name"]
            obix_name = register_line["Obix Name"]
            _log.info("Adding register: {} {} {} {}".format(device_topic, point_name, obix_name, self.last_read))
            register = Register(self.url, device_topic, point_name, obix_name, self.last_read)
            self.registers.append(register)
            self.topics.append((device_topic, point_name))

    def collate_results(self, devices):
        # devices[device_topic][point_name][time]: [value, units] ->
        #   result[time][device_topic][{point_name: value}, {point_name: {'units': units}]
        result = defaultdict(lambda: defaultdict(lambda: [{}, {}]))
        for device_topic, points in devices.items():
            for point_name, times in points.items():
                for time, value in times.items():
                    result[time][device_topic][0][point_name] = value[0]
                    result[time][device_topic][1][point_name] = {'units': value[1]}
        return result

    def update(self):
        async_requests = [r.get_value_async_result(username=self.username,
                                                   password=self.password,
                                                   start_time=r.last_read) for r in self.registers]
        request_results = grequests.map(async_requests, size=10)
        print(request_results)

        temp_last_read = {}
        parsed_results = defaultdict(dict)
        for r, result in zip(self.registers, request_results):
            if result is None:
                _log.debug("request failed: {}".format(async_requests[request_results.index(result)]))
                continue
            parsed_result = r.parse_result(result.text)
            if parsed_result is not None:
                parsed_results[r.device_topic][r.point_name] = parsed_result
                temp_last_read[r.index] = utils.format_timestamp(
                    max(utils.parse_timestamp_string(time) for time in parsed_result.keys()))
        collated_results = self.collate_results(parsed_results)

        records = []
        for timestamp, record in collated_results.items():
            for topic in record.keys():
                records.append({'topic': topic,
                                'message': record[topic],
                                'headers': {headers_mod.DATE: timestamp}})

        self.publish_records(records)

        _log.debug("publish successful. Saving timestamps of latest data")
        last_read = self.last_read.copy()
        for r in self.registers:
            if r.index in temp_last_read:
                last_read[r.index] = temp_last_read[r.index]
                r.last_read = temp_last_read[r.index]
        self.last_read = last_read
        self.vip.config.set("last_read", last_read)

    def publish_records(self, records):
        publish = True
        if self.historian_name is not None:
            _log.debug("Attempting to insert records into historian {}".format(self.historian_name))
            try:  # TODO: test with historian agent
                self.vip.rpc.call(self.historian_name, 'insert', records).get(timeout=10)
            except (Exception, gevent.Timeout) as e:
                _log.debug("Something went wrong with historian {} insert.".format(self.historian_name))
                _log.debug(e)
            else:
                publish = False
        if publish:
            _log.debug("publishing {} messages to message bus.".format(len(records)))
            for r in records:
                self.publish(r['topic'], r['message'], r['headers'])

    def publish(self, topic_prefix, message, headers):
        if isinstance(message, list):
            # publish all
            _topic = "all"
            if topic_prefix != '':
                _topic = topic_prefix + TOPIC_DELIM + _topic
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=_topic,
                                    message=message,
                                    headers=headers).get(timeout=2)
            # publish each
            # for topic in message.keys():
            #     self.vip.pubsub.publish(peer='pubsub',
            #                             topic=topic_prefix + TOPIC_DELIM + topic,
            #                             message=message[topic],
            #                             headers=headers).get(timeout=2)
        else:
            headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.PLAIN_TEXT
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=topic_prefix,
                                    message=str(message),
                                    headers=headers).get(timeout=2)


def main():
    """Main method called to start the agent."""
    utils.vip_main(obix_history, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
