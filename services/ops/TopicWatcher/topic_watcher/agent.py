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

import logging
import os

import gevent

import sqlite3
import datetime

from zmq import ZMQError

from volttron.platform.agent.known_identities import PLATFORM_TOPIC_WATCHER
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD, STATUS_GOOD
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.agent.utils import get_aware_utc_now
from volttron.platform.scheduling import periodic

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '2.1'


class AlertAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(AlertAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.group_instances = {}
        self._connection = None
        self.publish_settings = self.config.get('publish-settings')
        self._remote_agent = None
        self._creating_agent = False
        self._resetting_remote_agent = False
        self.publish_remote = False
        self.publish_local = True

        if self.publish_settings:
            self.publish_local = self.publish_settings.get('publish-local', True)
            self.publish_remote = self.publish_settings.get('publish-remote', False)
            remote = self.publish_settings.get('remote')
            if self.publish_remote and not remote:
                raise ValueError("Configured publish-remote without remote section")

            self.remote_identity = remote.get('identity', None)
            self.remote_serverkey = remote.get('serverkey', None)
            self.remote_address = remote.get('vip-address', None)

            # The remote serverkey need not be specified if the serverkey is added
            # to the known hosts file.  If it is not specified then the call to
            # build agent will fail.  Note not sure what rabbit will do in this
            # case
            #
            # TODO: check rabbit.
            if self.publish_remote:
                assert self.remote_identity
                assert self.remote_address

    @property
    def remote_agent(self):
        if self._remote_agent is None:
            if not self._creating_agent:
                self._creating_agent = True
                try:
                    # Single method to connect to remote instance in following combinations
                    # zmq -> zmq
                    # rmq -> rmq enabled with web
                    # zmq -> zmq enabled with web
                    # rmq -> zmq enabled with web
                    value = self.core.connect_remote_platform(self.remote_address,
                                                                  serverkey=self.remote_serverkey)

                    if isinstance(value, Agent):
                        self._remote_agent = value
                        self._remote_agent.vip.ping("").get(timeout=2)
                        self.vip.health.set_status(STATUS_GOOD)
                    else:
                        _log.error("Exception creation remote agent")
                        status_context = "Couldn't connect to remote platform at: {}".format(
                            self.remote_address)
                        _log.error(status_context)
                        self._remote_agent = None
                except (gevent.Timeout, ZMQError):
                    _log.error("Exception creation remote agent")
                    status_context = "Couldn't connect to remote platform at: {}".format(
                        self.remote_address)
                    _log.error(status_context)
                    self._remote_agent = None
                    self.vip.health.set_status(STATUS_BAD, status_context)
                finally:
                    self._creating_agent = False
        return self._remote_agent

    def reset_remote_agent(self):
        if not self._resetting_remote_agent and not self._creating_agent:
            if self._remote_agent is not None:
                self._remote_agent.core.stop()
            self._remote_agent = None
            self._resetting_remote_agent = False

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        """
        Setup database tables for persistent logs
        """
        db_dir = os.getcwd()
        data_dir = ""
        if utils.is_secure_mode():
            for d  in os.listdir(os.path.basename(os.getcwd())):
                if d.endswith(".agent-data"):
                    data_dir = d
                    break
            if data_dir:
                db_dir = os.path.join(os.getcwd(), data_dir)

        self._connection = sqlite3.connect(
            os.path.join(db_dir, 'alert_log.sqlite'),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        c = self._connection.cursor()

        c.execute("CREATE TABLE IF NOT EXISTS topic_log( "
                  "topic TEXT, "
                  "last_seen_before_timeout TIMESTAMP, "
                  "first_seen_after_timeout TIMESTAMP,"
                  "PRIMARY KEY(topic, last_seen_before_timeout))")

        c.execute("CREATE INDEX IF NOT EXISTS topic_index ON "
                  "topic_log (topic)")
        c.execute("CREATE INDEX IF NOT EXISTS down_time_index ON "
                  "topic_log (last_seen_before_timeout)")
        c.execute("CREATE INDEX IF NOT EXISTS up_time_index ON "
                  "topic_log (first_seen_after_timeout)")


        c.execute("CREATE TABLE IF NOT EXISTS agent_log ("
                  "start_time TIMESTAMP, "
                  "stop_time TIMESTAMP)")
        c.execute("CREATE INDEX IF NOT EXISTS stop_ts_index ON "
                  "agent_log (stop_time)")
        c.execute("INSERT INTO agent_log(start_time) values(?)",
                  (get_aware_utc_now(),))
        c.close()
        self._connection.commit()

        for group_name, config in self.config.items():
            if group_name != 'publish-settings':
                self.group_instances[group_name] = self.create_alert_group(group_name, config)

    def create_alert_group(self, group_name, config):
        group = AlertGroup(group_name, config, self._connection,
                           main_agent=self,
                           publish_local=self.publish_local,
                           publish_remote=self.publish_remote)

        return group

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        c = self._connection.cursor()
        c.execute("UPDATE agent_log set stop_time = ? "
                  " WHERE start_time = (SELECT max(start_time) from agent_log)",
                  (get_aware_utc_now(),))
        c.close()
        gevent.sleep(0.1)
        self._connection.commit()
        self._connection.close()

    @RPC.export
    def watch_topic(self, group, topic, timeout):
        """RPC method

        Listen for a topic to be published within a given
        number of seconds or send alerts. If the given group is new
        creates and starts an instance of AlertGroup agent for the new group.
        The alert group agent, onstart, will start watching for the given
        topics

        :pararm group: Group that should watch the topic.
        :type group: str
        :param topic: Topic expected to be published.
        :type topic: str
        :param timeout: Seconds before an alert is sent.
        :type timeout: int
        """
        if self.group_instances.get(group) is None:
            self.group_instances[group] = self.create_alert_group(group,
                                                                  {topic: timeout})
        else:
            self.group_instances[group].watch_topic(topic, timeout)
            self.group_instances[group].restart_timer()

    @RPC.export
    def watch_device(self, group, topic, timeout, points):
        """RPC method

        Watch a device's ALL topic and expect points. If the given group is new
        creates and starts an instance of group agent for the new group. The
        group onstart will start watching for the given device points

        :pararm group: Group that should watch the device.
        :type group: str
        :param topic: Topic expected to be published.
        :type topic: str
        :param timeout: Seconds before an alert is sent.
        :type timeout: int
        :param points: Points to expect in the publish message.
        :type points: [str]
        """
        if self.group_instances.get(group) is None:
            self.group_instances[group] = self.create_alert_group(
                group,
                {topic: {"seconds": timeout, "points": points}})
        else:
            self.group_instances[group].watch_device(topic, timeout, points)
            self.group_instances[group].restart_timer()

    @RPC.export
    def ignore_topic(self, group, topic):
        """RPC method

        Remove a topic from agent's watch list. Alerts will no
        longer be sent if a topic stops being published.

        :param group: Group that should ignore the topic.
        :type group: str
        :param topic: Topic to remove from the watch list.
        :type topic: str
        """
        group = self.group_instances[group]
        group.ignore_topic(topic)

    @Core.schedule(periodic(1))
    def decrement_ttl(self):
        """Periodic call

        Used to maintain the time since each topic's last publish.
        Sends an alert if any topics are missing.
        """

        # Loop through each alert group
        for name in self.group_instances:

            topics_timedout = set()
            alert_topics = set()

            # Loop through topics in alert group
            for topic in self.group_instances[name].wait_time.keys():

                # Send an alert if a topic hasn't been
                self.group_instances[name].topic_ttl[topic] -= 1
                if self.group_instances[name].topic_ttl[topic] <= 0:
                    alert_topics.add(topic)
                    self.group_instances[name].topic_ttl[topic] = self.group_instances[name].wait_time[topic]
                    if topic not in self.group_instances[name].unseen_topics:
                        topics_timedout.add(topic)
                        self.group_instances[name].unseen_topics.add(topic)

                # Send an alert if a point hasn't been seen
                try:
                    points = self.group_instances[name].point_ttl[topic].keys()
                    for p in points:
                        self.group_instances[name].point_ttl[topic][p] -= 1
                        if self.group_instances[name].point_ttl[topic][p] <= 0:
                            self.group_instances[name].point_ttl[topic][p] = self.group_instances[name].wait_time[topic]
                            alert_topics.add((topic, p))
                            if (topic, p) not in self.group_instances[name].unseen_topics:
                                topics_timedout.add((topic, p))
                                self.group_instances[name].unseen_topics.add((topic, p))
                except KeyError:
                    pass

            if alert_topics:
                try:
                    self.group_instances[name].send_alert(list(alert_topics))
                except ZMQError:
                    self.group_instances[name].main_agent.reset_remote_agent()

            if topics_timedout:
                self.group_instances[name].log_timeout(list(topics_timedout))


class AlertGroup():
    def __init__(self, group_name, config, connection, main_agent,
                 publish_local=True, publish_remote=False):
        self.group_name = group_name
        self.connection = connection
        self.config = config
        self.main_agent = main_agent

        self.wait_time = {}
        self.topic_ttl = {}
        self.point_ttl = {}
        self.unseen_topics = set()
        self.last_seen = {}
        self.publish_local = publish_local
        self.publish_remote = publish_remote
        self.parse_config()

    def parse_config(self):
        _log.info("Listening for alert group {}".format(self.group_name))
        config = self.config
        for topic in config.keys():

            # Optional config option with a list of points that
            # might not be published.
            if type(config[topic]) is dict:
                point_config = config[topic]
                self.watch_device(topic,
                                  point_config["seconds"],
                                  point_config["points"])

            # Default config option
            else:
                timeout = config[topic]
                self.watch_topic(topic, timeout)

    def watch_topic(self, topic, timeout):
        """Listen for a topic to be published within a given
        number of seconds or send alerts.

        :param topic: Topic expected to be published.
        :type topic: str
        :param timeout: Seconds before an alert is sent.
        :type timeout: int
        """
        self.wait_time[topic] = timeout
        self.topic_ttl[topic] = timeout
        self.main_agent.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=self.reset_time)

    def watch_device(self, topic, timeout, points):
        """Watch a device's ALL topic and expect points. This
        method calls the watch topic method so both methods
        don't need to be called.

        :param topic: Topic expected to be published.
        :type topic: str
        :param timeout: Seconds before an alert is sent.
        :type timeout: int
        :param points: Points to expect in the publish message.
        :type points: [str]
        """
        self.point_ttl[topic] = {}

        for p in points:
            self.point_ttl[topic][p] = timeout

        self.watch_topic(topic, timeout)

    def ignore_topic(self, topic):
        """Remove a topic from the group watchlist

        :param topic: Topic to remove from the watch list.
        :type topic: str
        """
        _log.info("Removing topic {} from watchlist".format(topic))

        self.main_agent.vip.pubsub.unsubscribe(peer='pubsub', prefix=topic, callback=self.reset_time)
        points = self.point_ttl.pop(topic, None)
        self.topic_ttl.pop(topic, None)
        self.wait_time.pop(topic, None)
        self.unseen_topics.remove(topic)
        for p in points:
            self.unseen_topics.remove((topic, p))

    def restart_timer(self):
        """
        Reset timer for all topics in this alert group. Should be called
        when a new topic is added to a currently active alert group
        """

        for t in self.topic_ttl:
            self.topic_ttl[t] = self.wait_time[t]
        for topic in self.point_ttl:
            for point in self.point_ttl[topic]:
                self.point_ttl[topic][point] = self.wait_time[topic]

    def reset_time(self, peer, sender, bus, topic, headers, message):
        """Callback for topic subscriptions

        Resets the timeout for topics and devices when publishes are received.
        """
        up_time = get_aware_utc_now()
        # TODO: What is the use case for this IF STMT
        # topic should always be there?? Ask Craig
        if topic not in self.wait_time:
            found = False
            # if topic isn't in wait time we need to figure out the
            # prefix topic so that we can determine the wait time
            for x in self.wait_time:
                # TODO: order the wait_time topics so furthest down the tree wins.
                if topic.startswith(x):
                    topic = x
                    found = True
                    break
            if not found:
                _log.debug("No configured topic prefix for topic {}".format(
                    topic))
                return

        log_topics = set()
        # Reset the standard topic timeout
        self.topic_ttl[topic] = self.wait_time[topic]
        self.last_seen[topic] = get_aware_utc_now()
        if topic in self.unseen_topics:
            self.unseen_topics.remove(topic)
            # log time we saw topic only if we had earlier recorded a timeout
            log_topics.add(topic)

        # Reset timeouts on volatile points
        if topic in self.point_ttl:
            received_points = message[0].keys()
            expected_points = self.point_ttl[topic].keys()
            for point in expected_points:
                if point in received_points:
                    self.point_ttl[topic][point] = self.wait_time[topic]
                    self.last_seen[(topic, point)] = get_aware_utc_now()
                    if (topic, point) in self.unseen_topics:
                        self.unseen_topics.remove((topic, point))
                        log_topics.add((topic, point))

        if log_topics:
            self.log_time_up(up_time, log_topics)

    def log_timeout(self, log_topics):
        """
        logs into database the last time a topic was seen before a time out
        or current time if topic was never seen from the time of alert agent
        start.
        :param log_topics: The list of configured topics for which message
        was received. Entries in this list can either be topic string or a
        tuple containing an all topic and a point name.
        :type log_topics: list
        """
        values = []
        for topic in log_topics:
            values.append((self.get_topic_name(topic),
                           self.last_seen.get(topic)))

        c = self.connection.cursor()
        c.executemany(
            "INSERT INTO topic_log (topic, last_seen_before_timeout) "
            "VALUES (?, ?)", values)
        c.close()
        self.connection.commit()

    def log_time_up(self, up_time, log_topics):
        """
        Log into topic_log table when the alert agent found publishes to a topic
        after the last time it timed out.
        :param up_time: Time when message was published to the topic. Note that
        this need not be the same as the timestamp in message header which gets
        recorded in the historian.  For example, when older device scrapes
        are replayed.
        :param log_topics: The list of configured topics for which message
        was received. Entries in this list can either be topic string or a
        tuple containing an all topic and a point name.
        :type up_time: datetime
        :type log_topics: list
        """
        c = self.connection.cursor()
        for topic in log_topics:
            c.execute("UPDATE topic_log "
                      "SET first_seen_after_timeout = ? "
                      "WHERE rowid = "
                      " (SELECT max(rowid) FROM topic_log "
                      "  WHERE topic = ? )",
                      (up_time, self.get_topic_name(topic)))

        c.close()
        self.connection.commit()

    @staticmethod
    def get_topic_name(parts):
        """
        Return the input parameter if input parameter is a string. If input
        parameter is a tuple, expects an all topic as the first list element
        and point name as the second element of the tuple.  strips "all" from
        the end of topic name and add the point name to it to get point
        topic string
        :param parts: topic name or (all topic, point name)
        :type parts: str or list
        :return: topic string
        :rtype: str
        """
        if isinstance(parts, str):
            return parts
        elif parts[0].endswith("/all"):
            return parts[0][:-3] + parts[1]
        else:
            raise ValueError("Invalid topic and point name:{} Only all "
                             "topics can use multiple points in an "
                             "alert group. For topics not ending in "
                             "/all use standard topic configuration format in "
                             "alert agent configuration".format(parts))


    def send_alert(self, unseen_topics):
        """Send an alert for the group, summarizing missing topics.

        :param unseen_topics: List of topics that were expected but not received
        :type unseen_topics: list
        """
        alert_key = "AlertAgent Timeout for group {}".format(self.group_name)
        _log.debug(f"unseen_topics {unseen_topics}")
        _log.debug(f"sorted : {sorted(unseen_topics, key = lambda x: x[0] if isinstance(x, tuple) else x)}")
        context = "Topic(s) not published within time limit: {}".format(
             sorted(unseen_topics, key = lambda x: x[0] if isinstance(x, tuple) else x))
        status = Status.build(STATUS_BAD, context=context)
        if self.publish_remote:
            try:
                remote_agent = self.main_agent.remote_agent
                if not remote_agent:
                    raise RuntimeError("Remote agent unavailable")
                else:
                    remote_agent.vip.health.send_alert(alert_key, status)
            except gevent.Timeout:
                self.main_agent.vip.health.send_alert(alert_key, status)
            else:
                if self.publish_local:
                    self.main_agent.vip.health.send_alert(alert_key, status)
        else:
            self.main_agent.vip.health.send_alert(alert_key, status)


def main():
    utils.vip_main(AlertAgent, identity=PLATFORM_TOPIC_WATCHER, version=__version__)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
