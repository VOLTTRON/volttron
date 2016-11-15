# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
from __future__ import absolute_import, print_function

import logging
import sys
import threading

from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.dbutils import sqlutils
from volttron.platform.vip.agent import *

__version__ = "3.6.1"

utils.setup_logging()
_log = logging.getLogger(__name__)


def historian(config_path, **kwargs):
    """
    This method is called by the :py:func:`sqlhistorian.historian.main` to
    parse the passed config file or configuration dictionary object, validate
    the configuration entries, and create an instance of SQLHistorian

    :param config_path: could be a path to a configuration file or can be a
                        dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`sqlhistorian.historian.SQLHistorian`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    connection = config_dict.get('connection', None)

    assert connection is not None
    database_type = connection.get('type', None)
    assert database_type is not None
    params = connection.get('params', None)
    assert params is not None

    identity_from_platform = kwargs.pop('identity', None)
    identity = config_dict.get('identity')

    if identity is not None:
        _log.warning("DEPRECATION WARNING: Setting a historian's VIP IDENTITY"
                     " from its configuration file will no longer be "
                     "supported after VOLTTRON 4.0")
        _log.warning("DEPRECATION WARNING: Using the identity configuration "
                     "setting will override the value provided by the "
                     "platform. This new value will not be reported correctly"
                     " by 'volttron-ctl status'")
        _log.warning("DEPRECATION WARNING: Please remove 'identity' from your "
                     "configuration file and use the new method provided by "
                     "the platform to set an agent's identity. See "
                     "scripts/core/make-sqlite-historian.sh for an example "
                     "of how this is done.")
    else:
        identity = identity_from_platform

    topic_replace_list = config_dict.get("topic_replace_list", None)
    if topic_replace_list:
        _log.debug("topic replace list is: {}".format(topic_replace_list))


    SQLHistorian.__name__ = 'SQLHistorian'
    return SQLHistorian(config_dict, identity=identity,
                        topic_replace_list=topic_replace_list, **kwargs)

class SQLHistorian(BaseHistorian):
    """This is a historian agent that writes data to a SQLite or Mysql
    database based on the connection parameters in the configuration.

    .. seealso::
     - :py:mod:`volttron.platform.dbutils.basedb`
     - :py:mod:`volttron.platform.dbutils.mysqlfuncts`
     - :py:mod:`volttron.platform.dbutils.sqlitefuncts`

    """

    def __init__(self, config, **kwargs):
        """Initialise the historian.

        The historian makes two connections to the data store.  Both of
        these connections are available across the main and processing
        thread of the historian.  topic_map and topic_meta are used as
        cache for the meta data and topic maps.

        :param config: dictionary object containing the configurations for
                       this historian
        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)
        """
        self.config = config
        self.topic_id_map = {}
        self.topic_name_map = {}
        self.topic_meta = {}
        self.agg_topic_id_map = {}
        self.tables_def = {}
        self.reader = None
        self.writer = None
        super(SQLHistorian, self).__init__(**kwargs)


    def record_table_definitions(self, meta_table_name):
        self.writer.record_table_definitions(self.tables_def,
                                             meta_table_name)

    def publish_to_historian(self, to_publish_list):
        thread_name = threading.currentThread().getName()
        _log.debug(
            "publish_to_historian number of items: {} Thread: {}".format(
                len(to_publish_list), thread_name))

        try:
            real_published = []
            for x in to_publish_list:
                ts = x['timestamp']
                topic = x['topic']
                value = x['value']
                meta = x['meta']

                # look at the topics that are stored in the database
                # already to see if this topic has a value
                lowercase_name = topic.lower()
                topic_id = self.topic_id_map.get(lowercase_name, None)
                db_topic_name = self.topic_name_map.get(lowercase_name,
                                                        None)
                _log.debug('topic is {}, db topic is {}'.format(
                    topic, db_topic_name))
                if topic_id is None:
                    _log.debug('Inserting topic: {}'.format(topic))
                    # Insert topic name as is in db
                    row = self.writer.insert_topic(topic)
                    topic_id = row[0]
                    # user lower case topic name when storing in map
                    # for case insensitive comparison
                    self.topic_id_map[lowercase_name] = topic_id
                    self.topic_name_map[lowercase_name] = topic
                    _log.debug('TopicId: {} => {}'.format(topic_id, topic))
                elif db_topic_name != topic:
                    _log.debug('Updating topic: {}'.format(topic))
                    self.writer.update_topic(topic, topic_id)
                    self.topic_name_map[lowercase_name] = topic

                old_meta = self.topic_meta.get(topic_id, {})
                if set(old_meta.items()) != set(meta.items()):
                    _log.debug(
                        'Updating meta for topic: {} {}'.format(topic,
                                                                meta))
                    self.writer.insert_meta(topic_id, meta)
                    self.topic_meta[topic_id] = meta

                if self.writer.insert_data(ts, topic_id, value):
                    # _log.debug('item was inserted')
                    real_published.append(x)

            if len(real_published) > 0:
                if self.writer.commit():
                    _log.debug('published {} data values'.format(
                        len(to_publish_list)))
                    self.report_all_handled()
                else:
                    msg = 'commit error. rolling back {} values.'
                    _log.debug(msg.format(len(to_publish_list)))
                    self.writer.rollback()
            else:
                _log.debug(
                    'Unable to publish {}'.format(len(to_publish_list)))
        except:
            self.writer.rollback()
            # Raise to the platform so it is logged properly.
            raise

    def query_topic_list(self):

        _log.debug("query_topic_list Thread is: {}".format(
            threading.currentThread().getName()))
        if len(self.topic_name_map) > 0:
            return self.topic_name_map.values()
        else:
            # No topics present.
            return []

    def query_topics_metadata(self, topics):
        meta = {}
        if isinstance(topics, str):
            topic_id = self.topic_id_map.get(topics.lower())
            if topic_id:
                meta = {topics: self.topic_meta.get(topic_id)}
        elif isinstance(topics, list):
            for topic in topics:
                topic_id = self.topic_id_map.get(topic.lower())
                if topic_id:
                    meta[topic] = self.topic_meta.get(topic_id)
        return meta

    def query_aggregate_topics(self):
        return self.reader.get_agg_topics()

    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None,
                        order="FIRST_TO_LAST"):
        _log.debug("query_historian Thread is: {}".format(
            threading.currentThread().getName()))
        results = dict()
        topics_list = []
        if isinstance(topic, str):
            topics_list.append(topic)
        elif isinstance(topic, list):
            topics_list = topic

        topic_ids = []
        id_name_map = {}
        for topic in topics_list:
            topic_lower = topic.lower()
            topic_id = self.topic_id_map.get(topic_lower)
            if agg_type:
                agg_type = agg_type.lower()
                topic_id = self.agg_topic_id_map.get(
                    (topic_lower, agg_type, agg_period))
                if topic_id is None:
                    # load agg topic id again as it might be a newly
                    # configured aggregation
                    agg_map = self.reader.get_agg_topic_map()
                    self.agg_topic_id_map.update(agg_map)
                    _log.debug(" Agg topic map after updating {} "
                               "".format(self.agg_topic_id_map))
                    topic_id = self.agg_topic_id_map.get(
                        (topic_lower, agg_type, agg_period))
            if topic_id:
                topic_ids.append(topic_id)
                id_name_map[topic_id] = topic
            else:
                _log.warn('No such topic {}'.format(topic))

        if not topic_ids:
            _log.warn('No topic ids found for topics{}. Returning '
                      'empty result'.format(topics_list))
            return results

        _log.debug(
            "Querying db reader with topic_ids {} ".format(topic_ids))
        multi_topic_query = len(topic_ids) > 1

        values = self.reader.query(topic_ids, id_name_map, start=start,
                                   end=end, agg_type=agg_type,
                                   agg_period=agg_period, skip=skip,
                                   count=count, order=order)
        metadata = {}

        if len(values) > 0:
            # If there are results add metadata if it is a query on a
            # single topic
            if not multi_topic_query:
                values = values.values()[0]
                if agg_type:
                    # if aggregation is on single topic find the topic id
                    # in the topics table that corresponds to agg_topic_id
                    # so that we can grab the correct metadata
                    _log.debug("Single topic aggregate query. Try to get "
                               "metadata")
                    tid = self.topic_id_map.get(topic.lower(), None)
                    if tid:
                        _log.debug("aggregation of a single topic, "
                                   "found topic id in topic map. "
                                   "topic_id={}".format(tid))
                        metadata = self.topic_meta.get(tid, {})
                    else:
                        # if topic name does not have entry in topic_id_map
                        # it is a user configured aggregation_topic_name
                        # which denotes aggregation across multiple points
                        metadata = {}
                else:
                    # this is a query on raw data, get metadata for
                    # topic from topic_meta map
                    metadata = self.topic_meta.get(topic_ids[0], {})
            return {'values': values, 'metadata': metadata}
        else:
            results = dict()
        return results

    def historian_setup(self):
        thread_name = threading.currentThread().getName()
        _log.debug("historian_setup on Thread: {}".format(thread_name))

        database_type = self.config['connection']['type']
        self.tables_def, table_names = self.parse_table_def(self.config)
        db_functs_class = sqlutils.get_dbfuncts_class(database_type)
        self.reader = db_functs_class(self.config['connection']['params'],
                                      table_names)
        self.writer = db_functs_class(self.config['connection']['params'],
                                      table_names)
        self.reader.setup_historian_tables()

        topic_id_map, topic_name_map = self.reader.get_topic_map()
        self.topic_id_map.update(topic_id_map)
        self.topic_name_map.update(topic_name_map)
        self.agg_topic_id_map = self.reader.get_agg_topic_map()



def main(argv=sys.argv):
    """ Main entry point for the agent.

    :param argv:
    :return:
    """

    try:
        utils.vip_main(historian)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
