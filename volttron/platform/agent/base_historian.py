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

"""
=====================
Historian Development
=====================

Support for storing and retrieving historical device and analysis data
published to the message bus is handled with Historian Agents. If a new type
of data store or a new way of storing data is desired a new type of Historian
Agent should created.

Historian Agents are implemented by subclassing :py:class:`BaseHistorian`.

Agents that need short term storage of device data should subscribe to device
data and use internal data structures for storage. Agents which need long
term Historical data that predates the startup of the Agent should interact
with a Historian Agent in order to obtain that data as needed.

While it is possible to create an Agent from scratch which handles gathering
and storing device data it will miss out on the benefits of creating a proper
Historian Agent that subclassing :py:class:`BaseHistorian`.
The :py:class:`BaseHistorian` class provides the following features:

- A separate thread for all communication with a data store removing the need
  to use or implement special libraries to work with gevent.
- Automatically subscribe to and process device publishes.
- Automatically backup data retrieved off the message bus to a disk cache.
  Cached data will only be removed once it is successfully published to a data
  store.
- Existing Agents that publish analytical data for storage or query for
  historical data will be able to use the new Historian without any code
  changes.
- Data can be graphed in VOLTTRON Central.

Creating a New Historian
------------------------

To create a new Historian create a new Agent that subclasses
:py:class:`BaseHistorian`. :py:class:`BaseHistorian` inherits from
:py:class:`volttron.platform.vip.agent.Agent` so including it in the class
parents is not needed.

The new Agent must implement the following methods:

- :py:meth:`BaseHistorianAgent.publish_to_historian`
- :py:meth:`BaseQueryHistorianAgent.query_topic_list`
- :py:meth:`BaseQueryHistorianAgent.query_historian`
- :py:meth:`BaseQueryHistorianAgent.query_topics_metadata`

If this historian has a corresponding  AggregateHistorian
(see :py:class:`AggregateHistorian`) implement the following method in addition
to the above ones:
- :py:meth:`BaseQueryHistorianAgent.record_table_definitions`
- :py:meth:`BaseQueryHistorianAgent.query_aggregate_topics`

While not required this method may be overridden as needed:
- :py:meth:`BaseHistorianAgent.historian_setup`


Optionally a Historian Agent can inherit from :py:class:`BaseHistorianAgent`
instead of :py:class:`BaseHistorian` if support for querying data is not
needed for the data store. If this route is taken then VOLTTRON Central
will not be able to graph data from the store. It is possible to run more than
one Historian agent at a time to store data in more than one place. If needed
one can be used to allow querying while another is used to put data in the
desired store that does not allow querying.

Historian Execution Flow
------------------------

At startup the :py:class:`BaseHistorian` class starts a new thread to handle
all data caching and publishing (the publishing thread). The main thread then
subscribes to all Historian related topics on the message bus. Whenever
subscribed data comes in it is published to a Queue to be be processed by the
publishing thread as soon as possible.

At startup the publishing thread calls two methods:

- :py:meth:`BaseHistorianAgent.historian_setup` to give the implemented
Historian a chance to setup any connections in the thread.
- :py:meth:`BaseQueryHistorianAgent.record_table_definitions` to give the
implemented Historian a chance to record the table/collection names into a
meta table/collection with the named passed as parameter. The implemented
historian is responsible for creating the meta table if it does not exist.

The process thread then enters the following logic loop:
::

    Wait for data to appear in the Queue. Proceed if data appears or a
    `retry_period` time elapses.
    If new data appeared in Queue:
        Save new data to cache.
    While data is in cache:
        Publish data to store by calling
            :py:meth:`BaseHistorianAgent.publish_to_historian`.
        If no data was published:
            Go back to start and check Queue for data.
        Remove published data from cache.
        If we have been publishing for `max_time_publishing`:
            Go back to start and check Queue for data.

The logic will also forgo waiting the `retry_period` for new data to appear
when checking for new data if publishing has been successful and there is
still data in the cache to be publish.

Storing Data
------------

The :py:class:`BaseHistorian` will call
:py:meth:`BaseHistorianAgent.publish_to_historian` as the time series data
becomes available. Data is batched in a groups up to `submit_size_limit`.

After processing the list or individual items in the list
:py:meth:`BaseHistorianAgent.publish_to_historian` must call
:py:meth:`BaseHistorianAgent.report_handled` to report an individual point
of data was published or :py:meth:`BaseHistorianAgent.report_all_handled` to
report that everything from the batch was successfully published. This tells
the :py:class:`BaseHistorianAgent` class what to remove from the cache and if
any publishing was successful.

The `to_publish_list` argument of
:py:meth:`BaseHistorianAgent.publish_to_historian` is a list of records that
takes the following form:

.. code-block:: python

    [
        {
            '_id': 1,
            'timestamp': timestamp1.replace(tzinfo=pytz.UTC),
            'source': 'scrape',
            'topic': "pnnl/isb1/hvac1/thermostat",
            'value': 73.0,
            'meta': {"units": "F", "tz": "UTC", "type": "float"}
        },
        {
            '_id': 2,
            'timestamp': timestamp2.replace(tzinfo=pytz.UTC),
            'source': 'scrape',
            'topic': "pnnl/isb1/hvac1/temperature",
            'value': 74.1,
            'meta': {"units": "F", "tz": "UTC", "type": "float"}
        },
        ...
    ]

As records are published to the data store
:py:meth:`BaseHistorianAgent.publish_to_historian` must call
:py:meth:`BaseHistorianAgent.report_handled` with the record or list of
records that was published or :py:meth:`BaseHistorianAgent.report_all_handled`
if everything was published.

Querying Data
-------------

- When an request is made to query data the
  :py:meth:`BaseQueryHistorianAgent.query_historian` method is called.
- When a request is made for the list of topics in the store
  :py:meth:`BaseQueryHistorianAgent.query_topic_list` will be called.
- When a request is made to get the metadata of a topic
  :py:meth:`BaseQueryHistorianAgent.query_topics_metadata` will be called.
- When a request is made for the list of aggregate topics available
  :py:meth:`BaseQueryHistorianAgent.query_aggregate_topics` will be called


Other Notes
-----------

Implemented Historians must be tolerant to receiving the same data for
submission twice.  While very rare, it is possible for a Historian to be
forcibly shutdown after data is published but before it is removed from the
cache. When restarted the :py:class:`BaseHistorian` will submit
the same date over again.

"""

from __future__ import absolute_import, print_function

import logging
import sqlite3
import threading
import weakref
from Queue import Queue, Empty
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Thread

import pytz
import re
from dateutil.parser import parse
from volttron.platform.agent.base_aggregate_historian import AggregateHistorian
from volttron.platform.agent.utils import process_timestamp, \
    fix_sqlite3_datetime, get_aware_utc_now, parse_timestamp_string
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.vip.agent import *
from volttron.platform.vip.agent import compat



try:
    import ujson
    def dumps(data):
        return ujson.dumps(data, double_precision=15)
    def loads(data_string):
        return ujson.loads(data_string, precise_float=True)
except ImportError:
    from zmq.utils.jsonapi import dumps, loads

from volttron.platform.agent import utils

_log = logging.getLogger(__name__)

ACTUATOR_TOPIC_PREFIX_PARTS = len(topics.ACTUATOR_VALUE.split('/'))
ALL_REX = re.compile('.*/all$')

# Register a better datetime parser in sqlite3.
fix_sqlite3_datetime()


def add_timing_data_to_header(headers, agent_id, phase):
    if "timing_data" not in headers:
        headers["timing_data"] = timing_data = {}
    else:
        timing_data = headers["timing_data"]

    if agent_id not in timing_data:
        timing_data[agent_id] = agent_timing_data = {}
    else:
        agent_timing_data = timing_data[agent_id]

    agent_timing_data[phase] = utils.format_timestamp(utils.get_aware_utc_now())

    values = agent_timing_data.values()

    if len(values) < 2:
        return 0.0

    #Assume 2 phases and proper format.
    time1 = datetime.strptime(values[0][11:26], "%H:%M:%S.%f")
    time2 = datetime.strptime(values[1][11:26], "%H:%M:%S.%f")

    return abs((time1 - time2).total_seconds())

class BaseHistorianAgent(Agent):
    """This is the base agent for historian Agents.
    It automatically subscribes to all device publish topics.

    Event processing occurs in its own thread as to not block the main
    thread.  Both the historian_setup and publish_to_historian happen in
    the same thread.

    By default the base historian will listen to 4 separate root topics (
    datalogger/*, record/*, analysis/*, and device/*.
    Messages published to datalogger will be assumed to be timepoint data that
    is composed of units and specific types with the assumption that they have
    the ability to be graphed easily. Messages published to devices
    are data that comes directly from drivers. Data sent to analysis/* topics
    is result of analysis done by applications. The format of data sent to
    analysis/* topics is similar to data sent to device/* topics.
    Messages that are published to record will be handled as string data and
    can be customized to the user specific situation. Refer to
    `Historian-Topic-Syntax
    </core_services/historians/Historian-Topic-Syntax.html>`_ for data syntax

    This base historian will cache all received messages to a local database
    before publishing it to the historian.  This allows recovery for
    unexpected happenings before the successful writing of data to the
    historian.
    """

    def __init__(self,
                 retry_period=300.0,
                 submit_size_limit=1000,
                 max_time_publishing=30,
                 backup_storage_limit_gb=None,
                 topic_replace_list=None,
                 gather_timing_data=False,
                 readonly=False,
                 **kwargs):

        super(BaseHistorianAgent, self).__init__(**kwargs)
        # This should resemble a dictionary that has key's from and to which
        # will be replaced within the topics before it's stored in the
        # cache database
        self._topic_replace_list = topic_replace_list

        _log.info('Topic string replace list: {}'
                  .format(self._topic_replace_list))

        self._gather_timing_data = gather_timing_data

        self.volttron_table_defs = 'volttron_table_definitions'
        self._backup_storage_limit_gb = backup_storage_limit_gb
        self._started = False
        self._retry_period = retry_period
        self._submit_size_limit = submit_size_limit
        self._max_time_publishing = timedelta(seconds=max_time_publishing)
        self._successful_published = set()
        self._topic_replace_map = {}
        self._event_queue = Queue()
        self._readonly = readonly
        self._process_thread = Thread(target=self._process_loop)
        self._process_thread.daemon = True  # Don't wait on thread to exit.
        self._process_thread.start()

    @RPC.export
    def insert(self, records):
        """RPC method to allow remote inserts to the local cache

        :param records: List of items to be added to the local event queue
        :type records: list of dictionaries
        """
        for r in records:
            topic = r['topic']
            headers = r['headers']
            message = r['message']

            if topic.startswith(topics.DRIVER_TOPIC_BASE):
                capture_func = self._capture_device_data
            elif topic.startswith(topics.LOGGER_BASE):
                capture_func = self._capture_log_data
            elif topic.startswith(topics.ANALYSIS_TOPIC_BASE):
                capture_func = self._capture_analysis_data
            elif topic.startswith(topics.RECORD_BASE):
                capture_func = self._capture_record_data

            capture_func(peer=None, sender=None, bus=None,
                         topic=topic, headers=headers, message=message)

    def _create_subscriptions(self):

        subscriptions = [
            (topics.DRIVER_TOPIC_BASE, self._capture_device_data),
            (topics.LOGGER_BASE, self._capture_log_data),
            #(topics.ACTUATOR, self._capture_actuator_data),
            (topics.ANALYSIS_TOPIC_BASE, self._capture_analysis_data),
            (topics.RECORD_BASE, self._capture_record_data)
        ]

        for prefix, cb in subscriptions:
            _log.debug("subscribing to {}".format(prefix))
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=prefix,
                                      callback=cb)

    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Subscribes to the platform message bus on the actuator, record,
        datalogger, and device topics to capture data.
        """
        if self._readonly:
            _log.debug("Starting base historian in readonly mode. Historian"
                       "will not subscribe to any topic")
        else:
            self._create_subscriptions()
            _log.debug("Starting base historian")


        self._started = True

        self.vip.heartbeat.start()

    @Core.receiver("onstop")
    def stopping(self, sender, **kwargs):
        """
        Release subscription to the message bus because we are no longer able
        to respond to messages now.
        """
        if not self._readonly:
            try:
                # unsubscribes to all topics that we are subscribed to.
                self.vip.pubsub.unsubscribe(peer='pubsub', prefix=None,
                                            callback=None)
            except KeyError:
                # means that the agent didn't start up properly so the pubsub
                # subscriptions never got finished.
                pass

    def parse_table_def(self, config):
        default_table_def = {"table_prefix": "",
                             "data_table": "data",
                             "topics_table": "topics",
                             "meta_table": "meta"}
        tables_def = config.get('tables_def', None)
        if not tables_def:
            tables_def = default_table_def
        table_names = dict(tables_def)

        table_prefix = tables_def.get('table_prefix', None)
        table_prefix = table_prefix + "_" if table_prefix else ""
        if table_prefix:
            for key, value in table_names.items():
                table_names[key] = table_prefix + table_names[key]
        table_names["agg_topics_table"] = table_prefix + \
            "aggregate_" + tables_def["topics_table"]
        table_names["agg_meta_table"] = table_prefix + \
            "aggregate_" + tables_def["meta_table"]
        return tables_def, table_names

    def _get_topic(self, input_topic):
        output_topic = input_topic
        # Only if we have some topics to replace.
        if self._topic_replace_list:
            # if we have already cached the topic then return it.
            if input_topic in self._topic_replace_map.keys():
                output_topic = self._topic_replace_map[input_topic]
            else:
                self._topic_replace_map[input_topic] = input_topic
                temptopics = {}
                for x in self._topic_replace_list:
                    if x['from'] in input_topic:
                        # this allows multiple things to be replaced from
                        # from a given topic.
                        new_topic = temptopics.get(input_topic, input_topic)
                        temptopics[input_topic] = new_topic.replace(
                            x['from'], x['to'])

                for k, v in temptopics.items():
                    self._topic_replace_map[k] = v
                output_topic = self._topic_replace_map[input_topic]

        return output_topic

    def _capture_record_data(self, peer, sender, bus, topic, headers,
                             message):
        _log.debug('Capture record data {}'.format(topic))
        # Anon the topic if necessary.
        topic = self._get_topic(topic)
        timestamp_string = headers.get(headers_mod.DATE, None)
        timestamp = get_aware_utc_now()
        if timestamp_string is not None:
            timestamp, my_tz = process_timestamp(timestamp_string, topic)

        if sender == 'pubsub.compat':
            message = compat.unpack_legacy_message(headers, message)

        if self._gather_timing_data:
            add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "collected")

        self._event_queue.put(
            {'source': 'record',
             'topic': topic,
             'readings': [(timestamp, message)],
             'meta': {},
             'headers': headers})

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

        if self._gather_timing_data:
            add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "collected")

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

            self._event_queue.put({'source': 'log',
                                   'topic': topic + '/' + point,
                                   'readings': readings,
                                   'meta': meta,
                                   'headers': headers})

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

    def _capture_analysis_data(self, peer, sender, bus, topic, headers,
                               message):
        """Capture analaysis data and submit it to be published by a historian.

        Filter out all but the all topics
        """

        # Anon the topic.
        topic = self._get_topic(topic)

        if topic.endswith('/'):
            topic = topic[:-1]

        if not topic.endswith('all'):
            topic += '/all'

        parts = topic.split('/')
        # strip off the first part of the topic.
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

        if self._gather_timing_data:
            add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "collected")

        for key, value in values.iteritems():
            point_topic = device + '/' + key
            self._event_queue.put({'source': source,
                                   'topic': point_topic,
                                   'readings': [(timestamp, value)],
                                   'meta': meta.get(key, {}),
                                   'headers': headers})

    def _capture_actuator_data(self, topic, headers, message, match):
        """Capture actuation data and submit it to be published by a historian.
        """
        # Anon the topic if necessary.
        topic = self._get_topic(topic)
        timestamp_string = headers.get('time')
        if timestamp_string is None:
            _log.error(
                "message for {topic} missing timetamp".format(topic=topic))
            return
        try:
            timestamp = parse(timestamp_string)
        except (ValueError, TypeError) as e:
            _log.error("message for {} bad timetamp string: "
                       "{}".format(topic, timestamp_string))
            return

        parts = topic.split('/')
        topic = '/'.join(parts[ACTUATOR_TOPIC_PREFIX_PARTS:])

        try:
            value = message[0]
        except ValueError as e:
            _log.error("message for {topic} bad message string: "
                       "{message_string}".format(topic=topic,
                                                 message_string=message[0]))
            return
        except IndexError as e:
            _log.error("message for {topic} missing message string".format(
                topic=topic))
            return

        source = 'actuator'
        _log.debug(
            "Queuing {topic} from {source} for publish".format(topic=topic,
                                                               source=source))

        if self._gather_timing_data:
            add_timing_data_to_header(headers, self.core.agent_uuid or self.core.identity, "collected")

        self._event_queue.put({'source': source,
                               'topic': topic,
                               'readings': [timestamp, value],
                               'meta': {},
                               'headers': headers})

    def _process_loop(self):
        """
        The process loop is called off of the main thread and will not exit
        unless the main agent is shutdown.
        """

        _log.debug("Starting process loop.")

        # Sets up the concrete historian
        # call this method even in case of readonly mode in case historian
        # is setting up connections that are shared for both query and write
        # operations
        self.historian_setup()

        if self._readonly:
            _log.info("Historian setup in readonly mode.")
            return

        # Record the names of data, topics, meta tables in a metadata table
        self.record_table_definitions(self.volttron_table_defs)
        backupdb = BackupDatabase(self, self._backup_storage_limit_gb)

        # now that everything is setup we need to make sure that the topics
        # are synchronized between

        # Based on the state of the back log and whether or not successful
        # publishing is currently happening (and how long it's taking)
        # we may or may not want to wait on the event queue for more input
        # before proceeding with the rest of the loop.
        wait_for_input = not bool(
            backupdb.get_outstanding_to_publish(self._submit_size_limit))

        while True:
            try:
                _log.debug("Reading from/waiting for queue.")
                new_to_publish = [
                    self._event_queue.get(wait_for_input, self._retry_period)]
            except Empty:
                _log.debug("Queue wait timed out. Falling out.")
                new_to_publish = []

            if new_to_publish:
                _log.debug("Checking for queue build up.")
                while True:
                    try:
                        new_to_publish.append(self._event_queue.get_nowait())
                    except Empty:
                        break


            backupdb.backup_new_data(new_to_publish)

            wait_for_input = True
            start_time = datetime.utcnow()

            while True:
                to_publish_list = backupdb.get_outstanding_to_publish(
                    self._submit_size_limit)
                if not to_publish_list or not self._started:
                    break

                try:
                    self.publish_to_historian(to_publish_list)
                except Exception as exp:
                    _log.exception(
                        "An unhandled exception occured while publishing.")

                # if the successful queue is empty then we need not remove
                # them from the database.
                if not self._successful_published:
                    break

                backupdb.remove_successfully_published(
                    self._successful_published, self._submit_size_limit)
                self._successful_published = set()
                now = datetime.utcnow()
                if now - start_time > self._max_time_publishing:
                    wait_for_input = False
                    break

        _log.debug("Finished processing")

    def report_handled(self, record):
        """
        Call this from :py:meth:`BaseHistorianAgent.publish_to_historian` to
        report a record or
        list of records has been successfully published and should be
        removed from the cache.

        :param record: Record or list of records to remove from cache.
        :type record: dict or list
        """
        if isinstance(record, list):
            for x in record:
                self._successful_published.add(x['_id'])
        else:
            self._successful_published.add(record['_id'])

    def report_all_handled(self):
        """
        Call this from :py:meth:`BaseHistorianAgent.publish_to_historian`
        to report that all records passed to
        :py:meth:`BaseHistorianAgent.publish_to_historian`
        have been successfully published and should be removed from the cache.
        """
        self._successful_published.add(None)

    @abstractmethod
    def publish_to_historian(self, to_publish_list):
        """
        Main publishing method for historian Agents.

        :param to_publish_list: List of records
        :type to_publish_list: list

        to_publish_list takes the following form:

        .. code-block:: python

            [
                {
                    '_id': 1,
                    'timestamp': timestamp1.replace(tzinfo=pytz.UTC),
                    'source': 'scrape',
                    'topic': "pnnl/isb1/hvac1/thermostat",
                    'value': 73.0,
                    'meta': {"units": "F", "tz": "UTC", "type": "float"}
                },
                {
                    '_id': 2,
                    'timestamp': timestamp2.replace(tzinfo=pytz.UTC),
                    'source': 'scrape',
                    'topic': "pnnl/isb1/hvac1/temperature",
                    'value': 74.1,
                    'meta': {"units": "F", "tz": "UTC", "type": "float"}
                },
                ...
            ]

        The contents of `meta` is not consistent. The keys in the meta data
        values can be different and can
        change along with the values of the meta data. It is safe to assume
        that the most recent value of
        the "meta" dictionary are the only values that are relevant. This is
        the way the cache
        treats meta data.

        Once one or more records are published either
        :py:meth:`BaseHistorianAgent.report_handled` or
        :py:meth:`BaseHistorianAgent.report_handled` must be called to
        report records as being published.
        """

    def historian_setup(self):
        """
        Optional setup routine, run in the processing thread before
        main processing loop starts. Gives the Historian a chance to setup
        connections in the publishing thread.
        """

    @abstractmethod
    def record_table_definitions(self, meta_table_name):
        """
        Record the table or collection names in which data, topics and
        metadata are stored into the metadata table.  This is essentially
        information from information from configuration item
        'table_defs'. The metadata table contents will be used by the
        corresponding aggregate historian(if any)

        :param meta_table_name: table name into which the table names and
        table name prefix for data, topics, and meta tables should be inserted
        """



#TODO: Finish this.
# from collections import deque
#
# class MemoryDatabase:
#     def __init__(self, owner, backup_storage_limit_gb):
#         # The topic cache is only meant as a local lookup and should not be
#         # accessed via the implemented historians.
#         self._backup_cache = {}
#         self._meta_data = defaultdict(dict)
#         self._owner = weakref.ref(owner)
#         self._backup_storage_limit_gb = backup_storage_limit_gb
#         self._deque = deque()
#
#     def get_outstanding_to_publish(self, size_limit):
#         _log.debug("Getting oldest outstanding to publish.")
#         results = []
#
#         count = 0
#         for row in self._deque:
#             timestamp = row[0]
#             source = row[1]
#             topic = row[2]
#             value = row[3]
#             headers = {} if row[4] is None else row[4]
#             meta = self._meta_data[(source, topic)].copy()
#             results.append({'timestamp': timestamp.replace(tzinfo=pytz.UTC),
#                             'source': source,
#                             'topic': topic,
#                             'value': value,
#                             'headers': headers,
#                             'meta': meta})
#             count += 1
#             if count >= size_limit:
#                 break
#
#         return results
#
#     def backup_new_data(self, new_publish_list):
#         _log.debug("Backing up unpublished values.")
#         for item in new_publish_list:
#             source = item['source']
#             topic = item['topic']
#             readings = item['readings']
#             headers = item.get('headers', {})
#
#             for timestamp, value in readings:
#                 if timestamp is None:
#                     timestamp = get_aware_utc_now()
#
#                 self._deque.append((timestamp, source, topic, value, headers))
#
#
#     def remove_successfully_published(self, successful_publishes,
#                                       submit_size):
#         _log.debug("Cleaning up successfully published values.")
#         if len(self._deque) <= submit_size:
#             self._deque.clear()
#             return
#         my_deque = self._deque
#         for i in xrange(submit_size):
#             my_deque.popleft()




class BackupDatabase:
    """
    A creates and manages backup cache for the
    :py:class:`BaseHistorianAgent` class.

    Historian implementors do not need to use this class. It is for internal
    use only.
    """

    def __init__(self, owner, backup_storage_limit_gb):
        # The topic cache is only meant as a local lookup and should not be
        # accessed via the implemented historians.
        self._backup_cache = {}
        self._meta_data = defaultdict(dict)
        self._owner = weakref.ref(owner)
        self._backup_storage_limit_gb = backup_storage_limit_gb
        self._setupdb()

    def backup_new_data(self, new_publish_list):
        """
        :param new_publish_list: A list of records to cache to disk.
        :type new_publish_list: list
        """
        _log.debug("Backing up unpublished values.")
        c = self._connection.cursor()

        if self._backup_storage_limit_gb is not None:

            def page_count():
                c.execute("PRAGMA page_count")
                return c.fetchone()[0]

            while page_count() >= self.max_pages:
                self._owner().vip.pubsub.publish('pubsub', 'backupdb/nomore')
                c.execute(
                    '''DELETE FROM outstanding
                    WHERE ROWID IN
                    (SELECT ROWID FROM outstanding
                    ORDER BY ROWID ASC LIMIT 100)''')

        for item in new_publish_list:
            source = item['source']
            topic = item['topic']
            meta = item.get('meta', {})
            readings = item['readings']
            headers = item.get('headers', {})

            topic_id = self._backup_cache.get(topic)

            if topic_id is None:
                c.execute('''INSERT INTO topics values (?,?)''',
                          (None, topic))
                c.execute('''SELECT last_insert_rowid()''')
                row = c.fetchone()
                topic_id = row[0]
                self._backup_cache[topic_id] = topic
                self._backup_cache[topic] = topic_id

            meta_dict = self._meta_data[(source, topic_id)]
            for name, value in meta.iteritems():
                current_meta_value = meta_dict.get(name)
                if current_meta_value != value:
                    c.execute('''INSERT OR REPLACE INTO metadata
                                 values(?, ?, ?, ?)''',
                              (source, topic_id, name, value))
                    meta_dict[name] = value

            for timestamp, value in readings:
                if timestamp is None:
                    timestamp = get_aware_utc_now()
                try:
                    c.execute(
                        '''INSERT INTO outstanding
                        values(NULL, ?, ?, ?, ?, ?)''',
                        (timestamp, source, topic_id, dumps(value), dumps(headers)))
                except sqlite3.IntegrityError:
                    #In the case where we are upgrading an existing installed historian the
                    #unique constraint may still exist on the outstanding database.
                    #Ignore this case.
                    pass

        self._connection.commit()

    def remove_successfully_published(self, successful_publishes,
                                      submit_size):
        """
        Removes the reported successful publishes from the backup database.
        If None is found in `successful_publishes` we assume that everything
        was published.

        :param successful_publishes: List of records that was published.
        :param submit_size: Number of things requested from previous call to
                            :py:meth:`get_outstanding_to_publish`

        :type successful_publishes: list
        :type submit_size: int

        """

        _log.debug("Cleaning up successfully published values.")
        c = self._connection.cursor()

        if None in successful_publishes:
            c.execute('''DELETE FROM outstanding
                        WHERE ROWID IN
                        (SELECT ROWID FROM outstanding
                          ORDER BY ts LIMIT ?)''', (submit_size,))
        else:
            temp = list(successful_publishes)
            temp.sort()
            c.executemany('''DELETE FROM outstanding
                            WHERE id = ?''',
                          ((_id,) for _id in
                           successful_publishes))

        self._connection.commit()

    def get_outstanding_to_publish(self, size_limit):
        """
        Retrieve up to `size_limit` records from the cache.

        :param size_limit: Max number of records to retrieve.
        :type size_limit: int
        :returns: List of records for publication.
        :rtype: list
        """
        _log.debug("Getting oldest outstanding to publish.")
        c = self._connection.cursor()
        c.execute('select * from outstanding order by ts limit ?',
                  (size_limit,))
        results = []
        for row in c:
            _id = row[0]
            timestamp = row[1]
            source = row[2]
            topic_id = row[3]
            value = loads(row[4])
            headers = {} if row[5] is None else loads(row[5])
            meta = self._meta_data[(source, topic_id)].copy()
            results.append({'_id': _id,
                            'timestamp': timestamp.replace(tzinfo=pytz.UTC),
                            'source': source,
                            'topic': self._backup_cache[topic_id],
                            'value': value,
                            'headers': headers,
                            'meta': meta})

        c.close()
        return results

    def _setupdb(self):
        """ Creates a backup database for the historian if doesn't exist."""

        _log.debug("Setting up backup DB.")
        self._connection = sqlite3.connect(
            'backup.sqlite',
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

        c = self._connection.cursor()

        if self._backup_storage_limit_gb is not None:
            c.execute('''PRAGMA page_size''')
            page_size = c.fetchone()[0]
            max_storage_bytes = self._backup_storage_limit_gb * 1024 ** 3
            self.max_pages = max_storage_bytes / page_size

        c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                  "AND name='outstanding';")

        if c.fetchone() is None:
            _log.debug("Configuring backup DB for the first time.")
            self._connection.execute('''PRAGMA auto_vacuum = FULL''')
            self._connection.execute('''CREATE TABLE outstanding
                                        (id INTEGER PRIMARY KEY,
                                         ts timestamp NOT NULL,
                                         source TEXT NOT NULL,
                                         topic_id INTEGER NOT NULL,
                                         value_string TEXT NOT NULL,
                                         header_string TEXT)''')
        else:
            #Check to see if we have a header_string column.
            c.execute("pragma table_info(outstanding);")
            name_index = 0
            for description in c.description:
                if description[0] == "name":
                    break
                name_index += 1

            found_header_column = False
            for row in c:
                if row[name_index] == "header_string":
                    found_header_column = True
                    break

            if not found_header_column:
                _log.info("Updating cache database to support storing header data.")
                c.execute("ALTER TABLE outstanding ADD COLUMN header_string text;")

        c.execute('''CREATE INDEX IF NOT EXISTS outstanding_ts_index
                                           ON outstanding (ts)''')

        c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                  "AND name='metadata';")

        if c.fetchone() is None:
            self._connection.execute('''CREATE TABLE metadata
                                        (source TEXT NOT NULL,
                                         topic_id INTEGER NOT NULL,
                                         name TEXT NOT NULL,
                                         value TEXT NOT NULL,
                                         UNIQUE(topic_id, source, name))''')
        else:
            c.execute("SELECT * FROM metadata")
            for row in c:
                self._meta_data[(row[0], row[1])][row[2]] = row[3]

        c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                  "AND name='topics';")

        if c.fetchone() is None:
            self._connection.execute('''create table topics
                                        (topic_id INTEGER PRIMARY KEY,
                                         topic_name TEXT NOT NULL,
                                         UNIQUE(topic_name))''')
        else:
            c.execute("SELECT * FROM topics")
            for row in c:
                self._backup_cache[row[0]] = row[1]
                self._backup_cache[row[1]] = row[0]

        c.close()

        self._connection.commit()


class BaseQueryHistorianAgent(Agent):
    """This is the base agent for historian Agents that support querying of
    their data stores.
    """

    @RPC.export
    def get_version(self):
        """RPC call to get the version of the historian

        :return: version number of the historian used
        :rtype: string
        """
        return self.version()

    @abstractmethod
    def version(self):
        """
        Return the current version number of the historian
        :return: version number
        """

    @RPC.export
    def get_topic_list(self):
        """RPC call to get a list of topics in data store

        :return: List of topics in the data store.
        :rtype: list
        """
        return self.query_topic_list()

    @abstractmethod
    def query_topic_list(self):
        """
        This function is called by
        :py:meth:`BaseQueryHistorianAgent.get_topic_list`
        to actually topic list from the data store.

        :return: List of topics in the data store.
        :rtype: list

        """

    @RPC.export
    def get_aggregate_topics(self):
        """
        RPC call to get the list of aggregate topics

        :return: List of aggregate topics in the data store. Each list
                 element contains (topic_name, aggregation_type,
                 aggregation_time_period, metadata)
        :rtype: list

        """
        return self.query_aggregate_topics()

    @abstractmethod
    def query_aggregate_topics(self):
        """
        This function is called by
        :py:meth:`BaseQueryHistorianAgent.get_aggregate_topics`
        to find out the available aggregates in the data store

        :return: List of tuples containing (topic_name, aggregation_type,
                 aggregation_time_period, metadata)
        :rtype: list

        """

    @RPC.export
    def get_topics_metadata(self, topics):

        """
        RPC call to get one or more topic's metadata

        :param topics: single topic or list of topics for which metadata is
                       requested
        :return: List of aggregate topics in the data store. Each list
                 element contains (topic_name, aggregation_type,
                 aggregation_time_period, metadata)
        :rtype: list

        """
        if isinstance(topics, str) or isinstance(topics, list):
            return self.query_topics_metadata(topics)
        else:
            raise ValueError(
                "Please provide a valid topic name string or "
                "a list of topic names. Invalid input {}".format(topics))

    @abstractmethod
    def query_topics_metadata(self, topics):
        """
        This function is called by
        :py:meth:`BaseQueryHistorianAgent.get_topics_metadata`
        to find out the metadata for the given topics

        :param topics: single topic or list of topics
        :type topics: str or list
        :return: dictionary with the format

        .. code-block:: python

                 {topic_name: {metadata_key:metadata_value, ...},
                 topic_name: {metadata_key:metadata_value, ...} ...}

        :rtype: dict

        """

    @RPC.export
    def query(self, topic=None, start=None, end=None, agg_type=None,
              agg_period=None, skip=0, count=None, order="FIRST_TO_LAST"):
        """RPC call to query an Historian for time series data.

        :param topic: Topic or topics to query for.
        :param start: Start time of the query. Defaults to None which is the
                      beginning of time.
        :param end: End time of the query.  Defaults to None which is the
                    end of time.
        :param skip: Skip this number of results.
        :param count: Limit results to this value.
        :param order: How to order the results, either "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        :type topic: str or list
        :type start: str
        :type end: str
        :param agg_type: If this is a query for aggregate data, the type of
                         aggregation ( for example, sum, avg)
        :param agg_period: If this is a query for aggregate data, the time
                           period of aggregation
        :type skip: int
        :type count: int
        :type order: str

        :return: Results of the query
        :rtype: dict

        Return values will have the following form:

        .. code-block:: python

            {
                "values": [(<timestamp string1>: value1),
                           (<timestamp string2>: value2),
                            ...],
                "metadata": {"key1": value1,
                             "key2": value2,
                             ...}
            }

        The string arguments can be either the output from
        :py:func:`volttron.platform.agent.utils.format_timestamp` or the
        special string "now".

        Times relative to "now" may be specified with a relative time string
        using the Unix "at"-style specifications. For instance "now -1h" will
        specify one hour ago.
        "now -1d -1h -20m" would specify 25 hours and 20 minutes ago.

        """

        if topic is None:
            raise TypeError('"Topic" required')

        if agg_type:
            if not agg_period:
                raise TypeError("You should provide both aggregation type"
                                "(agg_type) and aggregation time period"
                                "(agg_period) to query aggregate data")
        else:
            if agg_period:
                raise TypeError("You should provide both aggregation type"
                                "(agg_type) and aggregation time period"
                                "(agg_period) to query aggregate data")

        if agg_period:
            agg_period = AggregateHistorian.normalize_aggregation_time_period(
                agg_period)
        if start is not None:
            try:
                start = parse_timestamp_string(start)
            except TypeError:
                start = time_parser.parse(start)
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=pytz.UTC)

        if end is not None:
            try:
                end = parse_timestamp_string(end)
            except TypeError:
                end = time_parser.parse(end)
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=pytz.UTC)

        if start:
            _log.debug("start={}".format(start))

        results = self.query_historian(topic, start, end, agg_type,
                                       agg_period, skip, count, order)
        metadata = results.get("metadata", None)
        values = results.get("values", None)
        if values and metadata is None:
            results['metadata'] = {}

        return results

    @abstractmethod
    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None, order=None):
        """
        This function is called by :py:meth:`BaseQueryHistorianAgent.query`
        to actually query the data store and must return the results of a
        query in the following format:

        **Single topic query:**

        .. code-block:: python

            {
            "values": [(timestamp1, value1),
                        (timestamp2:,value2),
                        ...],
             "metadata": {"key1": value1,
                          "key2": value2,
                          ...}
            }

        **Multiple topics query:**

        .. code-block:: python

            {
            "values": {topic_name:[(timestamp1, value1),
                        (timestamp2:,value2),
                        ...],
                       topic_name:[(timestamp1, value1),
                        (timestamp2:,value2),
                        ...],
                        ...}
             "metadata": {} #empty metadata
            }

        Timestamps must be strings formatted by
        :py:func:`volttron.platform.agent.utils.format_timestamp`.

        "metadata" is not required. The caller will normalize this to {} for
        you if it is missing.

        :param topic: Topic or list of topics to query for.
        :param start: Start of query timestamp as a datetime.
        :param end: End of query timestamp as a datetime.
        :param agg_type: If this is a query for aggregate data, the type of
                         aggregation ( for example, sum, avg)
        :param agg_period: If this is a query for aggregate data, the time
                           period of aggregation
        :param skip: Skip this number of results.
        :param count: Limit results to this value. When the query is for
                      multiple topics, count applies to individual topics. For
                      example, a query on 2 topics with count=5 will return 5
                      records for each topic
        :param order: How to order the results, either "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        :type topic: str or list
        :type start: datetime
        :type end: datetime
        :type skip: int
        :type count: int
        :type order: str

        :return: Results of the query
        :rtype: dict

        """


class BaseHistorian(BaseHistorianAgent, BaseQueryHistorianAgent):
    def __init__(self, **kwargs):
        _log.debug('Constructor of BaseHistorian thread: {}'.format(
            threading.currentThread().getName()
        ))
        super(BaseHistorian, self).__init__(**kwargs)


# The following code is
# Copyright (c) 2011, 2012, Regents of the University of California
# and is under the same licence as the remainder of the code in this file.
# Modification were made to remove unneeded pieces and to fit with the
# intended use.
import ply.lex as lex
import ply.yacc as yacc
from dateutil.tz import gettz
from tzlocal import get_localzone

# use get_localzone from tzlocal instead of dateutil.tz.tzlocal as dateutil
# tzlocal does not take into account day light savings time
local = get_localzone()


def now(tzstr='UTC'):
    """Returns an aware datetime object with the current time in
    tzstr timezone"""
    if tzstr == 'Local':
        tz = local
    else:
        tz = gettz(tzstr)
    return datetime.datetime.now(tz)


def strptime_tz(str, format='%x %X', tzstr='Local'):
    """Returns an aware datetime object. tzstr is a timezone string such as
       'US/Pacific' or 'Local' by default which uses the local timezone.
    """
    dt = datetime.datetime.strptime(str, format)
    if tzstr == 'Local':
        tz = local
    else:
        tz = gettz(tzstr)
    return dt.replace(tzinfo=tz)


tokens = ('NOW', "QSTRING", 'LVALUE', 'NUMBER')

reserved = {
    'now': 'NOW'}

literals = '()[]*^.,<>=+-/'

time_units = re.compile('^(d|days?|h|hours?|m|minutes?|s|seconds?)$')


def get_timeunit(t):
    if not time_units.match(t):
        raise ValueError("Invalid timeunit: %s" % t)
    if t.startswith('d'):
        return 'days'
    elif t.startswith('h'):
        return 'hours'
    elif t.startswith('m'):
        return 'minutes'
    elif t.startswith('s'):
        return 'seconds'


def t_QSTRING(t):
    r"""("[^"\\]*?(\\.[^"\\]*?)*?")|(\'[^\'\\]*?(\\.[^\'\\]*?)*?\')"""
    if t.value[0] == '"':
        t.value = t.value[1:-1].replace('\\"', '"')
    elif t.value[0] == "'":
        t.value = t.value[1:-1].replace("\\'", "'")
    return t


def t_LVALUE(t):
    r"""[a-zA-Z\~\$\_][a-zA-Z0-9\/\%_\-]*"""
    t.type = reserved.get(t.value, 'LVALUE')
    return t


def t_NUMBER(t):
    r"""([+-]?([0-9]*\.)?[0-9]+)"""
    if '.' in t.value:
        try:
            t.value = float(t.value)
        except ValueError:
            print("Invalid floating point number", t.value)
            t.value = 0
    else:
        try:
            t.value = int(t.value)
        except ValueError:
            print("Integer value too large %d", t.value)
            t.value = 0

    return t


is_number = lambda x: isinstance(x, int) or isinstance(x, float)

t_ignore = " \t"


def t_newline(t):
    r"""[\n\r]+"""
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    raise ValueError("Syntax Error in Query")
    # print("Illegal character '%s'" % t.value[0])
    # t.lexer.skip(1)


smapql_lex = lex.lex()

TIMEZONE_PATTERNS = [
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
]


def parse_time(ts):
    for pat in TIMEZONE_PATTERNS:
        try:
            return strptime_tz(ts, pat)
        except ValueError:
            continue
    raise ValueError("Invalid time string:" + ts)


def p_query_pair(t):
    """query : '(' timeref ',' timeref ')' """
    t[0] = (t[2], t[4])


def p_query_single(t):
    """query : timeref """
    t[0] = t[1]


# an absolute time reference.  can be a unix timestamp, a date string,
# or "now"
def p_timeref(t):
    """timeref : abstime
               | abstime reltime"""
    t[0] = t[1]
    if len(t) == 2:
        ref = t[1]
    else:
        ref = t[1] + t[2]
    t[0] = ref


def p_abstime(t):
    """abstime : NUMBER
               | QSTRING
               | NOW"""
    if t[1] == 'now':
        t[0] = now()
    elif type(t[1]) == type(''):
        t[0] = parse_time(t[1])
    else:
        t[0] = datetime.datetime.utcfromtimestamp(t[1] / 1000)


def p_reltime(t):
    """reltime : NUMBER LVALUE
               | NUMBER LVALUE reltime"""
    timeunit = get_timeunit(t[2])
    delta = datetime.timedelta(**{timeunit: t[1]})
    if len(t) == 3:
        t[0] = delta
    else:
        t[0] = t[3] + delta


# Error rule for syntax errors
def p_error(p):
    raise ValueError("Syntax Error in Query")


# Build the parser
time_parser = yacc.yacc(write_tables=0)
