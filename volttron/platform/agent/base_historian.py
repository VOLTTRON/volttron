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
Historian Agent that subclassing :py:class:`BaseHistorian`. The
:py:class:`BaseHistorian` class provides the following features:

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

At startup the publishing thread calls
:py:meth:`BaseHistorianAgent.historian_setup` to give the implemented
Historian a chance to setup any connections in the thread.

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

When an request is made to query data the
:py:meth:`BaseQueryHistorianAgent.query_historian` method is called.
When a request is made for the list of topics in the store
:py:meth:`BaseQueryHistorianAgent.query_topic_list`
will be called.

Other Notes
-----------

Implemented Historians must be tolerant to receiving the same data for
submission twice.  While very rare, it is possible for a Historian to be
forcibly shutdown after data is published but before it is removed from the
cache. When restarted the :py:class:`BaseHistorian` will submit
the same date over again.

"""

from __future__ import absolute_import, print_function

from abc import abstractmethod
from dateutil.parser import parse
import logging
import re
import sqlite3
from Queue import Queue, Empty
from collections import defaultdict
from datetime import datetime, timedelta
import threading
from threading import Thread
import weakref

import pytz
from zmq.utils import jsonapi

from volttron.platform.agent.utils import process_timestamp, \
    fix_sqlite3_datetime, get_aware_utc_now
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.vip.agent import *
from volttron.platform.vip.agent import compat

_log = logging.getLogger(__name__)

ACTUATOR_TOPIC_PREFIX_PARTS = len(topics.ACTUATOR_VALUE.split('/'))
ALL_REX = re.compile('.*/all$')

# Register a better datetime parser in sqlite3.
fix_sqlite3_datetime()


class BaseHistorianAgent(Agent):
    """This is the base agent for historian Agents.
    It automatically subscribes to all device publish topics.

    Event processing occurs in its own thread as to not block the main
    thread.  Both the historian_setup and publish_to_historian happen in
    the same thread.

    By default the base historian will listen to 4 separate root topics (
    datalogger/*, record/*, actuators/*, and device/*.  Messages that are
    published to actuator are assumed to be part of the actuation process.
    Messages published to datalogger will be assumed to be timepoint data that
    is composed of units and specific types with the assumption that they have
    the ability to be graphed easily. Messages published to devices
    are data that comes directly from drivers.  Finally Messages that are
    published to record will be handled as string data and can be customized
    to the user specific situation.

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
                 **kwargs):

        super(BaseHistorianAgent, self).__init__(**kwargs)
        # This should resemble a dictionary that has key's from and to which
        # will be replaced within the topics before it's stored in the
        # cache database
        self._topic_replace_list = topic_replace_list

        _log.info('Topic string replace list: {}'
                  .format(self._topic_replace_list))

        self._backup_storage_limit_gb = backup_storage_limit_gb
        self._started = False
        self._retry_period = retry_period
        self._submit_size_limit = submit_size_limit
        self._max_time_publishing = timedelta(seconds=max_time_publishing)
        self._successful_published = set()
        self._topic_replace_map = {}
        self._event_queue = Queue()
        self._process_thread = Thread(target=self._process_loop)
        self._process_thread.daemon = True  # Don't wait on thread to exit.
        self._process_thread.start()

    def _create_subscriptions(self):

        subscriptions = [
            (topics.DRIVER_TOPIC_BASE, self._capture_device_data),
            (topics.LOGGER_BASE, self._capture_log_data),
            (topics.ACTUATOR, self._capture_actuator_data),
            (topics.ANALYSIS_TOPIC_BASE, self._capture_analysis_data),
            (topics.RECORD, self._capture_record_data)
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
        _log.debug("Starting base historian")

        self._create_subscriptions()

        self._started = True

        self.vip.heartbeat.start()

    @Core.receiver("onstop")
    def stopping(self, sender, **kwargs):
        """
        Release subscription to the message bus because we are no longer able
        to respond to messages now.
        """
        try:
            # unsubscribes to all topics that we are subscribed to.
            self.vip.pubsub.unsubscribe(peer='pubsub', prefix=None,
                                        callback=None)
        except KeyError:
            # means that the agent didn't start up properly so the pubsub
            # subscriptions never got finished.
            pass

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
        _log.debug('Capture record data {}'.format(message))
        # Anon the topic if necessary.
        topic = self._get_topic(topic)
        timestamp_string = headers.get(headers_mod.DATE, None)
        timestamp = get_aware_utc_now()
        if timestamp_string is not None:
            timestamp, my_tz = process_timestamp(timestamp_string, topic)

        if sender == 'pubsub.compat':
            message = compat.unpack_legacy_message(headers, message)
        self._event_queue.put(
            {'source': 'record',
             'topic': topic,
             'readings': [(timestamp, message)],
             'meta': {}})

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

        source = 'log'
        _log.debug(
            "Queuing {topic} from {source} for publish".format(topic=topic,
                                                               source=source))
        _log.debug(data)
        for point, item in data.iteritems():
            #             ts_path = location + '/' + point
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

            self._event_queue.put({'source': source,
                                   'topic': topic + '/' + point,
                                   'readings': readings,
                                   'meta': meta})

    def _capture_device_data(self, peer, sender, bus, topic, headers,
                             message):
        """Capture device data and submit it to be published by a historian.

        Filter out only the */all topics for publishing to the historian.
        """

        if not ALL_REX.match(topic):
            _log.debug("Unmatched topic: {}".format(topic))
            return

        # Anon the topic if necessary.
        topic = self._get_topic(topic)

        # Because of the above if we know that all is in the topic so
        # we strip it off to get the base device
        parts = topic.split('/')
        device = '/'.join(parts[1:-1])  # '/'.join(reversed(parts[2:]))

        _log.debug("found topic {}".format(topic))

        self._capture_data(peer, sender, bus, topic, headers, message, device)

    def _capture_analysis_data(self, peer, sender, bus, topic, headers,
                               message):
        """Capture analaysis data and submit it to be published by a historian.

        Filter out all but the all topics
        """

        if topic.endswith("/all") or '/all/' in topic:
            return

        # Anon the topic if necessary.
        topic = self._get_topic(topic)
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
        _log.debug("### In capture_data timestamp str {} ".format(timestamp))
        try:
            _log.debug(
                "### In capture_data Actual message {} ".format(message))
            # 2.0 agents compatability layer makes sender == pubsub.compat so
            # we can do the proper thing when it is here
            if sender == 'pubsub.compat':
                # message = jsonapi.loads(message[0])
                message = compat.unpack_legacy_message(headers, message)
                _log.debug("### message after compat {}".format(message))

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
            self._event_queue.put({'source': source,
                                   'topic': point_topic,
                                   'readings': [(timestamp, value)],
                                   'meta': meta.get(key, {})})

    def _capture_actuator_data(self, topic, headers, message, match):
        """Capture actuation data and submit it to be published by a historian.
        """
        # Anon the topic if necessary.
        topic = self._get_topic(topic)
        timestamp_string = headers.get('time')
        _log.debug("TIMESTMAMP_STRING: {}".format(timestamp_string))
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

        self._event_queue.put({'source': source,
                               'topic': topic,
                               'readings': [timestamp, value],
                               'meta': {}})

    def _process_loop(self):
        """
        The process loop is called off of the main thread and will not exit
        unless the main agent is shutdown.
        """

        _log.debug("Starting process loop.")

        backupdb = BackupDatabase(self, self._backup_storage_limit_gb)

        # Sets up the concrete historian
        self.historian_setup()

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

            _log.debug("Calling publish_to_historian.")
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
        Call this from :py:meth:`BaseHistorianAgent.publish_to_historian` to report a record or
        list of records has been successfully published and should be removed from the cache.

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
            Call this from :py:meth:`BaseHistorianAgent.publish_to_historian` to report that all records
             passed to :py:meth:`BaseHistorianAgent.publish_to_historian` have been successfully published
             and should be removed from the cache.
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

        The contents of `meta` is not consistent. The keys in the meta data values can be different and can
        change along with the values of the meta data. It is safe to assume that the most recent value of
        the "meta" dictionary are the only values that are relevant. This is the way the cache
        treats meta data.

        Once one or more records are published either :py:meth:`BaseHistorianAgent.report_handled` or
        :py:meth:`BaseHistorianAgent.report_handled` must be called to report records as being published.
        """

    def historian_setup(self):
        """Optional setup routine, run in the processing thread before
           main processing loop starts. Gives the Historian a chance to setup
           connections in the publishing thread.
        """


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
            values = item['readings']

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

            for timestamp, value in values:
                if timestamp is None:
                    timestamp = get_aware_utc_now()
                _log.debug("Inserting into outstanding table with timestamp "
                           "{}".format(timestamp))
                c.execute(
                    '''INSERT OR REPLACE INTO outstanding
                    values(NULL, ?, ?, ?, ?)''',
                    (timestamp, source, topic_id, jsonapi.dumps(value)))

        self._connection.commit()

    def remove_successfully_published(self, successful_publishes,
                                      submit_size):
        """
        Removes the reported successful publishes from the backup database.
        If None is found in `successful_publishes` we assume that everything
        was published.

        :param successful_publishes: List of records that was published.
        :param submit_size: Number of things requested from previous call to :py:meth:`get_outstanding_to_publish`.
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
            value = jsonapi.loads(row[4])
            meta = self._meta_data[(source, topic_id)].copy()
            results.append({'_id': _id,
                            'timestamp': timestamp.replace(tzinfo=pytz.UTC),
                            'source': source,
                            'topic': self._backup_cache[topic_id],
                            'value': value,
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
            _log.debug("Configuring backup BD for the first time.")
            self._connection.execute('''PRAGMA auto_vacuum = FULL''')
            self._connection.execute('''CREATE TABLE outstanding
                                        (id INTEGER PRIMARY KEY,
                                         ts timestamp NOT NULL,
                                         source TEXT NOT NULL,
                                         topic_id INTEGER NOT NULL,
                                         value_string TEXT NOT NULL,
                                         UNIQUE(ts, topic_id, source))''')

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
    def query(self, topic=None, start=None, end=None, skip=0,
              count=None, order="FIRST_TO_LAST"):
        """RPC call

        Call this method to query an Historian for time series data.

        :param topic: Topic to query for.
        :param start: Start time of the query. Defaults to None which is the beginning of time.
        :param end: End time of the query.  Defaults to None which is the end of time.
        :param skip: Skip this number of results.
        :param count: Limit results to this value.
        :param order: How to order the results, either "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :type topic: str
        :type start: str
        :type end: str
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
        :py:func:`volttron.platform.agent.utils.format_timestamp` or the special string "now".

        Times relative to "now" may be specified with a relative time string using
        the Unix "at"-style specifications. For instance "now -1h" will specify one hour ago.
        "now -1d -1h -20m" would specify 25 hours and 20 minutes ago.

        """

        if topic is None:
            raise TypeError('"Topic" required')

        if start is not None:
            try:
                start = parse(start)
            except TypeError:
                start = time_parser.parse(start)

        if end is not None:
            try:
                end = parse(end)
            except TypeError:
                end = time_parser.parse(end)

        if start:
            _log.debug("start={}".format(start))

        results = self.query_historian(topic, start, end, skip, count, order)
        metadata = results.get("metadata", None)
        values = results.get("values", None)
        if values is not None and metadata is None:
            results['metadata'] = {}
        return results

    @RPC.export
    def get_topic_list(self):
        """RPC call

        :return: List of topics in the data store.
        :rtype: list
        """
        return self.query_topic_list()

    @abstractmethod
    def query_topic_list(self):
        """
        This function is called by :py:meth:`BaseQueryHistorianAgent.get_topic_list`
        to actually topic list from the data store.

        :return: List of topics in the data store.
        :rtype: list
        """

    @abstractmethod
    def query_historian(self, topic, start=None, end=None, skip=0, count=None,
                        order=None):
        """
        This function is called by :py:meth:`BaseQueryHistorianAgent.query`
        to actually query the data store
        and must return the results of a query in the form:

        .. code-block:: python

            {
            "values": [(timestamp1: value1),
                        (timestamp2: value2),
                        ...],
             "metadata": {"key1": value1,
                          "key2": value2,
                          ...}
            }
         
        Timestamps must be strings formatted by
        :py:func:`volttron.platform.agent.utils.format_timestamp`.

        "metadata" is not required. The caller will normalize this to {} for you if it is missing.

        :param topic: Topic to query for.
        :param start: Start of query timestamp as a datetime.
        :param end: End of query timestamp as a datetime.
        :param skip: Skip this number of results.
        :param count: Limit results to this value.
        :param order: How to order the results, either "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :type topic: str
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
from dateutil.tz import gettz, tzlocal

local = tzlocal()


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
