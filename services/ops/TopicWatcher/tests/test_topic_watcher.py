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

import json
import sqlite3

import gevent
import os
import pytest

from volttron.platform import get_ops
from volttron.platform.agent.known_identities import PLATFORM_TOPIC_WATCHER
from volttron.platform.agent.utils import get_aware_utc_now

agent_version = '1.0'
WATCHER_CONFIG = {
    "group1": {
        "fakedevice": 5,
        "fakedevice2/all": {
            "seconds": 5,
            "points": ["point"]
        }
    }
}

alert_messages = {}

db_connection = None
db_path = None
alert_uuid = None


@pytest.fixture(scope='module')
def agent(request, volttron_instance1):
    global db_connection, agent_version, db_path, alert_uuid
    assert os.path.exists(get_ops("TopicWatcher"))
    alert_uuid = volttron_instance1.install_agent(
        agent_dir=get_ops("TopicWatcher"),
        config_file=WATCHER_CONFIG,
        vip_identity=PLATFORM_TOPIC_WATCHER
    )
    gevent.sleep(2)
    db_path = os.path.join(volttron_instance1.volttron_home, 'agents',
                           alert_uuid, 'topic_watcheragent-' + agent_version,
                           'topic-watcheragent-' + agent_version + '.agent-data',
                           'alert_log.sqlite')

    print ("DB PATH: {}".format(db_path))
    db_connection = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

    agent = volttron_instance1.build_agent()

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = json.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1
        print("In on message: {}".format(alert_messages))

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alert',
                               callback=onmessage)

    def stop():
        volttron_instance1.stop_agent(alert_uuid)
        agent.core.stop()
        db_connection.close()

    request.addfinalizer(stop)
    return agent


@pytest.fixture(scope='function')
def cleanup_db():
    global db_connection
    c = db_connection.cursor()
    c.execute("DELETE FROM topic_log")
    c.execute("DELETE FROM agent_log")
    db_connection.commit()


@pytest.mark.alert
def test_basic(agent):
    """
    Test if alert agent watches for configured device and topic messages and
    sends alerts and logs time in database correctly
    :param agent: fake agent used to make rpc calls to alert agent
    """
    global alert_messages, db_connection
    publish_time = get_aware_utc_now()
    for _ in range(10):
        alert_messages.clear()
        agent.vip.pubsub.publish(peer='pubsub',
                                 topic='fakedevice')
        agent.vip.pubsub.publish(peer='pubsub',
                                 topic='fakedevice2/all',
                                 message=[{'point': 'value'}])
        gevent.sleep(1)

    assert not alert_messages
    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE last_seen_before_timeout > "{}"'.format(publish_time))
    result = c.fetchone()
    assert result is None

    gevent.sleep(6)
    print("DB Path {}".format(db_path))
    print("Publish time {}".format(publish_time))
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout > "{}"'.format(publish_time))
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 3
    for r in results:
        topics.append(r[0])
        assert r[1] is not None
    assert sorted(topics) == sorted([u'fakedevice', u'fakedevice2/all',
                                     u'fakedevice2/point'])
    assert len(alert_messages) == 1

    # c.execute('SELECT * FROM topic_log '
    #           'WHERE first_seen_after_timeout is NULL '
    #           'AND last_seen_before_timeout > ?', (publish_time,))
    # results = c.fetchall()
    # topics = []
    # assert results is not None
    # assert len(results) == 3


@pytest.mark.alert
def test_ignore_topic(agent):
    """
    Test ignore_topic rpc call. When a topic is ignored, it should not appear
    in future alert messages
    :param agent: fake agent used to make rpc calls to alert agent
    """
    global alert_messages, db_connection

    agent.vip.rpc.call(PLATFORM_TOPIC_WATCHER, 'ignore_topic', 'group1',
                       'fakedevice2/all').get()
    alert_messages.clear()
    publish_time = get_aware_utc_now()
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice')
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice2/all',
                             message=[{'point': 'value'}])
    print("Alert messages {}".format(alert_messages))
    gevent.sleep(7)
    assert len(alert_messages) == 1
    assert u"Topic(s) not published within time limit: ['fakedevice']" in \
           alert_messages
    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout > "{}"'.format(publish_time))
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 1
    assert results[0][0] == u'fakedevice'
    assert results[0][2] == None


@pytest.mark.alert
def test_watch_topic_same_group(volttron_instance1, agent, cleanup_db):
    """
    Test adding a new topic to watch list. Add the topic to a already configured
    group. Agent should watching for the new topic and should send correct
    alert messages
    :param volttron_instance1: instance in which alert agent is running
    :param agent: fake agent used to make rpc calls to alert agent
    :param cleanup_db: function scope fixture to clean up alert and agent log
    tables in database.
    """
    global alert_messages, db_connection, alert_uuid
    volttron_instance1.stop_agent(alert_uuid)
    alert_messages.clear()
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(1)
    publish_time = get_aware_utc_now()
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice')
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice2/all',
                             message=[{'point': 'value'}])
    gevent.sleep(1)
    agent.vip.rpc.call(PLATFORM_TOPIC_WATCHER, 'watch_topic', 'group1', 'newtopic',
                       5).get()
    gevent.sleep(6)

    assert u"Topic(s) not published within time limit: ['fakedevice', " \
           u"'fakedevice2/all', 'newtopic', ('fakedevice2/all', 'point')]" in \
           alert_messages

    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout IS NULL '
              'AND last_seen_before_timeout IS NULL')
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 1
    assert results[0][0] == u'newtopic'
    assert results[0][2] == None

    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout > "{}"'.format(publish_time))
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 3


@pytest.mark.alert
def test_watch_topic_new_group(volttron_instance1, agent, cleanup_db):
    """
    Test adding a new topic to watch list. Add the topic to a new watch group.
    Agent should start watching for the new topic and should send correct
    alert messages and update database entries for the new topic
    :param volttron_instance1: instance in which alert agent is running
    :param agent: fake agent used to make rpc calls to alert agent
    :param cleanup_db: function scope fixture to clean up alert and agent log
    tables in database.
    """
    global alert_messages, db_connection, alert_uuid
    volttron_instance1.stop_agent(alert_uuid)
    alert_messages.clear()
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(1)
    publish_time = get_aware_utc_now()
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice')
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice2/all',
                             message=[{'point': 'value'}])
    gevent.sleep(1)
    agent.vip.rpc.call(PLATFORM_TOPIC_WATCHER, 'watch_topic', 'group2', 'newtopic',
                       5).get()
    gevent.sleep(6)

    assert len(alert_messages) == 2
    assert u"Topic(s) not published within time limit: ['fakedevice', " \
           u"'fakedevice2/all', ('fakedevice2/all', 'point')]" in \
           alert_messages
    assert u"Topic(s) not published within time limit: ['newtopic']" in \
           alert_messages

    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout IS NULL '
              'AND last_seen_before_timeout IS NULL')
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 1
    assert results[0][0] == u'newtopic'
    assert results[0][2] == None

    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout > "{}"'.format(publish_time))
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 3


@pytest.mark.alert
def test_watch_device_same_group(volttron_instance1, agent, cleanup_db):
    """
    Test adding a new point topic to watch list. Add the topic to an existing
    watch group. Agent should start watching for the new topic and should
    send correct alert messages and update database entries for the new topic
    :param volttron_instance1: instance in which alert agent is running
    :param agent: fake agent used to make rpc calls to alert agent
    :param cleanup_db: function scope fixture to clean up alert and agent log
    tables in database.
    """
    global alert_messages, db_connection
    volttron_instance1.stop_agent(alert_uuid)
    alert_messages.clear()
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(1)
    publish_time = get_aware_utc_now()
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice')
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice2/all',
                             message=[{'point': 'value'}])
    gevent.sleep(1)
    agent.vip.rpc.call(PLATFORM_TOPIC_WATCHER, 'watch_device', 'group1',
                       'newtopic/all', 5, ['point']).get()
    gevent.sleep(6)

    assert u"Topic(s) not published within time limit: ['fakedevice', " \
           u"'fakedevice2/all', 'newtopic/all', ('fakedevice2/all', " \
           u"'point'), ('newtopic/all', 'point')]" in \
           alert_messages

    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout IS NULL '
              'AND last_seen_before_timeout IS NULL')
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 2
    assert {results[0][0], results[1][0]} == {u'newtopic/all',
                                              u'newtopic/point'}
    assert results[0][2] == results[1][2] is None

    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout > "{}"'.format(publish_time))
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 3


@pytest.mark.alert
def test_watch_device_new_group(volttron_instance1, agent, cleanup_db):
    """
    Test adding a new point topic to watch list. Add the topic to a new watch
    group. Agent should start watching for the new topic and should send correct
    alert messages and update database entries for the new topic
    :param volttron_instance1: instance in which alert agent is running
    :param agent: fake agent used to make rpc calls to alert agent
    :param cleanup_db: function scope fixture to clean up alert and agent log
    tables in database.
    """
    global alert_messages, db_connection
    volttron_instance1.stop_agent(alert_uuid)
    alert_messages.clear()
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(1)
    publish_time = get_aware_utc_now()
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice')
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice2/all',
                             message=[{'point': 'value'}])
    gevent.sleep(1)
    agent.vip.rpc.call(PLATFORM_TOPIC_WATCHER, 'watch_device', 'group2',
                       'newtopic/all', 5, ['point']).get()
    gevent.sleep(7)

    assert len(alert_messages) == 2
    assert u"Topic(s) not published within time limit: ['fakedevice', " \
           u"'fakedevice2/all', ('fakedevice2/all', 'point')]" in \
           alert_messages
    assert u"Topic(s) not published within time limit: ['newtopic/all', " \
           u"('newtopic/all', 'point')]" in \
           alert_messages

    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout IS NULL '
              'AND last_seen_before_timeout IS NULL')
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 2
    assert {results[0][0], results[1][0]} == {u'newtopic/all',
                                              u'newtopic/point'}
    assert results[0][2] == results[1][2] is None

    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout > "{}"'.format(publish_time))
    results = c.fetchall()
    topics = []
    assert results is not None
    assert len(results) == 3


@pytest.mark.alert
def test_agent_logs(volttron_instance1, agent):
    """
    Test if alert agent's start and stop time are getting logged correctly
    :param volttron_instance1: instance in which alert agent is running
    :param agent: fake agent used to make rpc calls to alert agent
    """
    global alert_messages, db_connection, alert_uuid
    stop_t = get_aware_utc_now()
    volttron_instance1.stop_agent(alert_uuid)
    gevent.sleep(1)
    c = db_connection.cursor()
    c.execute("SELECT * FROM agent_log "
              "WHERE start_time IS NOT NULL AND "
              "stop_time > '{}'".format(stop_t))
    r = c.fetchall()
    assert len(r) == 1
    start_t = get_aware_utc_now()
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(4)
    stop_t = get_aware_utc_now()
    volttron_instance1.stop_agent(alert_uuid)
    c.execute("SELECT * FROM agent_log "
              "WHERE start_time > '{}' AND "
              "stop_time > '{}'".format(start_t, stop_t))
    r = c.fetchall()
    assert len(r) == 1
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(1)


@pytest.mark.alert
def test_for_duplicate_logs(volttron_instance1, agent, cleanup_db):
    """
    Test if records are not getting duplicated in database after every watch
    time interval. When a topic is not seen within the configured time
    frame a single row is inserted into database for that topic. When the topic
    is seen again the same row is updated with timestamp of when the
    topic message was seen.
    :param volttron_instance1: instance in which alert agent is running
    :param agent: fake agent used to make rpc calls to alert agent
    :param cleanup_db: function scope fixture to clean up alert and agent log
    tables in database.
    """
    global db_connection, alert_messages, alert_uuid
    volttron_instance1.stop_agent(alert_uuid)
    gevent.sleep(1)
    start_t = get_aware_utc_now()
    volttron_instance1.start_agent(alert_uuid)
    gevent.sleep(6)
    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout is NULL'.format(start_t))
    results = c.fetchall()
    assert results is not None
    assert len(results)

    gevent.sleep(6)
    c = db_connection.cursor()
    c.execute('SELECT * FROM topic_log '
              'WHERE first_seen_after_timeout is NULL '
              'AND last_seen_before_timeout is NULL'.format(start_t))
    results = c.fetchall()
    assert results is not None
    assert len(results) == 3

    publish_time = get_aware_utc_now()
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice')
    agent.vip.pubsub.publish(peer='pubsub',
                             topic='fakedevice2/all',
                             message=[{'point': 'value'}])
    gevent.sleep(2)
    c = db_connection.cursor()
    c.execute('SELECT topic, last_seen_before_timeout, '
              'first_seen_after_timeout FROM topic_log ')
    results = c.fetchall()
    assert len(results) == 3
    for r in results:
        assert r[1] is None
        non_utc = publish_time.replace(tzinfo=None)
        assert r[2] >= non_utc
