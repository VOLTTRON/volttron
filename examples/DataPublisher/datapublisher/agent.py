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
import csv
import datetime
import logging
import re
import sys

from volttron.platform.vip.agent import *
from volttron.platform.agent import utils
from volttron.platform.messaging.utils import normtopic
from volttron.platform.messaging import headers as headers_mod
import gevent

from collections import defaultdict

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '4.0.0'

HEADER_NAME_DATE = headers_mod.DATE
HEADER_NAME_TIMESTAMP = headers_mod.TIMESTAMP
HEADER_NAME_CONTENT_TYPE = headers_mod.CONTENT_TYPE
SCHEDULE_RESPONSE_SUCCESS = 'SUCCESS'
SCHEDULE_RESPONSE_FAILURE = 'FAILURE'
SCHEDULE_ACTION_NEW = 'NEW_SCHEDULE'
SCHEDULE_ACTION_CANCEL = 'CANCEL_SCHEDULE'

LINE_MARKER_CONFIG = "line_marker"

__authors__ = ['Robert Lutes <robert.lutes@pnnl.gov>',
               'Kyle Monson <kyle.monson@pnnl.gov>',
               'Craig Allwardt <craig.allwardt@pnnl.gov>']
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'Apache 2.0'


def DataPub(config_path, **kwargs):
    '''Emulate device driver to publish data and Actuatoragent for testing.

    The first column in the data file must be the timestamp and it is not
    published to the bus unless the config option:
    'use_timestamp' - True will use timestamp in input file.
    timestamps. False will use the current now time and publish using it.
    '''

    conf = utils.load_config(config_path)
    _log.debug(str(conf))
    use_timestamp = conf.get('use_timestamp', True)
    remember_playback = conf.get('remember_playback', False)
    reset_playback = conf.get('reset_playback', False)

    publish_interval = float(conf.get('publish_interval', 5))

    base_path = conf.get('basepath', "")

    input_data = conf.get('input_data', [])

    # unittype_map maps the point name to the proper units.
    unittype_map = conf.get('unittype_map', {})
    
    # should we keep playing the file over and over again.
    replay_data = conf.get('replay_data', False)

    max_data_frequency = conf.get("max_data_frequency")

    topic_separator = conf.get("topic_separator", "/")

    return Publisher(use_timestamp=use_timestamp,
                     publish_interval=publish_interval,
                     base_path=base_path,
                     input_data=input_data,
                     unittype_map=unittype_map,
                     max_data_frequency=max_data_frequency,
                     replay_data=replay_data,
                     remember_playback=remember_playback,
                     reset_playback=reset_playback,
                     topic_separator=topic_separator,
                     **kwargs)


class Publisher(Agent):
    '''Simulate real device.  Publish csv data to message bus.

    Configuration consists of csv file and publish topic
    '''
    def __init__(self, use_timestamp=False,
                 publish_interval=5.0, base_path="", input_data=[], unittype_map={},
                 max_data_frequency=None, replay_data=False, remember_playback=False,
                 reset_playback=False, topic_separator="/",
                 **kwargs):
        '''Initialize data publisher class attributes.'''
        super(Publisher, self).__init__(**kwargs)

        self._meta_data = {}  # maps from device topic to meta data map.
        self._name_map = {}  # maps from column name to (device topic, point name)
        self._data = []  # incoming data
        self._publish_interval = publish_interval
        self._use_timestamp = use_timestamp
        self._loop_greenlet = None
        self._next_allowed_publish = None
        self._max_data_frequency = None
        self._replay_data = False
        self._remember_playback = bool(remember_playback)
        self._reset_playback = bool(reset_playback)
        self._input_data = None
        self._line_marker = 0
        self._topic_separator = topic_separator

        self.default_config = {"use_timestamp": use_timestamp,
                               "publish_interval": publish_interval,
                               "base_path": base_path,
                               "input_data": input_data,
                               "unittype_map": unittype_map,
                               "replay_data": replay_data,
                               "max_data_frequency": max_data_frequency,
                               "remember_playback": self._remember_playback,
                               "reset_playback": self._reset_playback,
                               "topic_separator": self._topic_separator}

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW"], pattern="config")
        self.vip.config.subscribe(self.config_error, actions=["UPDATE"], pattern="config")

    def config_error(self, config_name, action, contents):
        _log.error("Currently the data publisher must be restarted for changes to take effect.")

    def configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

        if self._loop_greenlet is not None:
            self._loop_greenlet.kill()

        _log.info('Config Data: {}'.format(config))

        base_path = config.get("base_path", "")
        unittype_map = config.get("unittype_map", {})

        self._input_data = config.get("input_data", [])

        self._publish_interval = config.get("publish_interval", 5.0)
        self._use_timestamp = config.get("use_timestamp", False)

        self._max_data_frequency = config.get("max_data_frequency", None)

        if self._max_data_frequency is not None:
            self._max_data_frequency = datetime.timedelta(seconds=self._max_data_frequency)

        self._replay_data = bool(config.get("replay_data", False))
        # If this is false we have to wait until the publish loop to reset
        # the position in the config store.
        self._remember_playback = bool(config.get("remember_playback", False))
        # Reset anyway, even if remember_playback is true.
        self._reset_playback = bool(config.get("reset_playback", False))
        self._topic_separator = config.get("topic_separator", "/")
        try:
            self._line_marker = int(self.vip.config.get(LINE_MARKER_CONFIG))
        except (KeyError, ValueError, TypeError, IndexError) as e:
            self._line_marker = 0

        names = []
        if isinstance(self._input_data, list):
            if self._input_data:
                item = self._input_data[0]
                names = list(item.keys())
            self._data = self._input_data
        else:
            handle = open(self._input_data)
            self._data = csv.DictReader(handle)
            names = self._data.fieldnames[:]

        self._name_map = self.build_maps(names, base_path)
        self._meta_data = self.build_metadata(self._name_map, unittype_map)

        self._loop_greenlet = self.core.spawn(self.publish_loop)

    @staticmethod
    def build_metadata(name_map, unittype_map):
        results = defaultdict(dict)
        for topic, point in name_map.values():
            unit_type = Publisher._get_unit(point, unittype_map)
            results[topic][point] = {"unit": unit_type}
        return results

    def build_maps(self, fieldnames, base_path):
        """
        Creates name an topic tree based upon the passed fieldnames.

        Topics are generated based upon the topic separator and the field name passed.  All topics
        will be separated by the / after they are created.  The topic can then be used to determine
        the points associated with that topic.
        """
        results = {}
        for name in fieldnames:
            if name == "Timestamp":
                continue
            name_parts = name.split(self._topic_separator)
            point = name_parts[-1]
            topic = normtopic(base_path + '/' + '/'.join(name_parts[:-1]))

            results[name] = (topic, point)

        return results

    @staticmethod
    def _get_unit(point, unittype_map):
        ''' Get a unit type based upon the regular expression in the config file.

            if NOT found returns percent as a default unit.
        '''
        for k, v in unittype_map.items():
            if re.match(k, point):
                return v
        return {'type': 'float'}

    def _publish_point_all(self, topic, data, meta_data, headers):
        # makesure topic+point gives a true value.
        all_topic = topic + "/all"

        message = [data, meta_data]

        self.vip.pubsub.publish(peer='pubsub',
                                topic=all_topic,
                                message=message,  # [data, {'source': 'publisher3'}],
                                headers=headers).get(timeout=2)

    def build_publish_with_meta(self, row):
        results = defaultdict(dict)
        meta_results = defaultdict(dict)
        for name, value in row.items():
            topic, point = self._name_map[name]

            try:
                parsed_value = float(value)
                results[topic][point] = parsed_value
                meta_results[topic][point] = self._meta_data[topic][point]
            except ValueError:
                _log.error(f"Missing parseable float value for topic {topic}/{point}")
            
        return results, meta_results

    def check_frequency(self, now):
        """Check to see if the passed in timestamp exceeds the configured
        max_data_frequency."""
        if self._max_data_frequency is None:
            return True

        now = utils.parse_timestamp_string(now)

        if self._next_allowed_publish is None:
            midnight = now.date()
            midnight = datetime.datetime.combine(midnight, datetime.time.min)
            self._next_allowed_publish = midnight
            while now > self._next_allowed_publish:
                self._next_allowed_publish += self._max_data_frequency

        if now < self._next_allowed_publish:
            return False

        while now >= self._next_allowed_publish:
            self._next_allowed_publish += self._max_data_frequency

        return True

    def publish_loop(self):
        """Publish data from file to message bus."""
        # We cannot reset the value in the config until we are in a separate greenlet.
        # We cannot call set in a config handler.

        if self._reset_playback:
            self._line_marker = 0
            if self._remember_playback:
                self.vip.config.set(LINE_MARKER_CONFIG, str(0), send_update=False)

        while True:
            current_line = -1
            for row in self._data:
                current_line += 1

                if current_line < self._line_marker:
                    continue

                self._line_marker += 1
                
                if self._use_timestamp and "Timestamp" in row:
                    now = row['Timestamp']
                    if not self.check_frequency(now):
                        continue
                else:
                    now = utils.format_timestamp(datetime.datetime.now())

                headers = {HEADER_NAME_DATE: now, HEADER_NAME_TIMESTAMP: now}
                row.pop('Timestamp', None)

                publish_values, publish_meta = self.build_publish_with_meta(row)

                for topic, message in publish_values.items():
                    self._publish_point_all(topic, message, publish_meta[topic], headers)

                if self._remember_playback:
                    self.vip.config.set(LINE_MARKER_CONFIG, str(self._line_marker), send_update=False)

                gevent.sleep(self._publish_interval)

            # Reset line marker.
            self._line_marker = 0
            if self._remember_playback:
                self.vip.config.set(LINE_MARKER_CONFIG, str(self._line_marker), send_update=False)
            if not self._replay_data:
                sys.exit(0)

            # Reset the csv reader if we are reading from a file.
            _log.debug("Restarting playback.")
            # Reset data frequency counter.
            self._next_allowed_publish = None
            if not isinstance(self._input_data, list):
                handle = open(self._input_data, 'r')
                self._data = csv.DictReader(handle)

    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        requester_id = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        _log.info("Set point: {} {} {}".format(requester_id, topic, value))
        return None

    @RPC.export
    def set_multiple_points(self, requester_id, topics_values, **kwargs):
        devices = defaultdict(list)
        for topic, value in topics_values:
            topic = topic.strip('/')
            self.set_point(requester_id, topic, value)

        results = {}

        return results

    @RPC.export
    def request_new_schedule(self, requester_id, task_id, priority, requests):
        requester_id = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        _log.info("Schedule requested: {} {} {} {}".format(requester_id, task_id, priority, requests))
        results = {'result': 'SUCCESS',
                   'data': {},
                   'info': ""}

        return results

    @RPC.export
    def request_cancel_schedule(self, requester_id, task_id):
        requester_id = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        _log.info("Schedule canceled: {} {}".format(requester_id, task_id))
        results = {'result': 'SUCCESS',
                   'data': {},
                   'info': ""}

        return results


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(DataPub, version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
