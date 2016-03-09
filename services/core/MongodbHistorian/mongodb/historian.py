# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
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

#}}}
from __future__ import absolute_import, print_function

import datetime
import logging
import sys
import dateutil
import pymongo
from pymongo import ReplaceOne, InsertOne
from bson.objectid import ObjectId

import gevent

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    connection = config.get('connection', None)
    assert connection is not None

    databaseType = connection.get('type', None)
    assert databaseType is not None

    params = connection.get('params', None)
    assert params is not None

    aggregation = config.get('aggregation', 'minute')


    identity = config.get('identity', kwargs.pop('identity', None))

    class MongodbHistorian(BaseHistorian):
        '''This is a simple example of a historian agent that writes stuff
        to Mongodb. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        This is very similar to SQLHistorian implementation
        '''

        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):
            _log.debug('Starting address: {} identity: {}'.format(self.core.address, self.core.identity))

            if self.core.identity == 'platform.historian':
                # Check to see if the platform agent is available, if it isn't then
                # subscribe to the /platform topic to be notified when the platform
                # agent becomes available.
                try:
                    ping = self.vip.ping('platform.agent',
                                         'awake?').get(timeout=3)
                    _log.debug("Ping response was? "+ str(ping))
                    self.vip.rpc.call('platform.agent', 'register_service',
                                      self.core.identity).get(timeout=3)
                except Unreachable:
                    _log.debug('Could not register historian service')
                finally:
                    self.vip.pubsub.subscribe('pubsub', '/platform',
                                              self._connect_platform)
                    _log.debug("Listening to /platform")

        def _connect_platform(self, peer, sender, bus, topic, headers, message):
            ''' Connect to the platform.agent and register service.
            '''
            _log.debug('Platform is now: {}'.format(message))
            if message == 'available' and \
                    self.core.identity == 'platform.historian':
                gevent.spawn(self.vip.rpc.call, 'platform.agent',
                    'register_service', self.core.identity)
                gevent.sleep(0)

        def publish_to_historian(self, to_publish_list):
            _log.debug("publish_to_historian number of items: {}"
                       .format(len(to_publish_list)))

            # Use the db instance to insert/update the topics and data collections
            db = self.mongoclient[self.database_name]
            bulk_publish = []
            for x in to_publish_list:
                ts = x['timestamp']
                topic = x['topic']
                value = x['value']

                # look at the topics that are stored in the database already
                # to see if this topic has a value
                topic_id = self.topic_map.get(topic, None)

                if topic_id is None:
                    row  = db.topics.insert_one({'topic_name': topic})# self.insert_topic(topic)
                    topic_id = row.inserted_id
                    # topic map should hold both a lookup from topic name
                    # and from id to topic_name.
                    self.topic_map[topic] = topic_id
                    self.topic_map[topic_id] = topic

                # Reformat to a filter tha bulk inserter.
                bulk_publish.append(InsertOne(
                    {'ts': ts, 'topic_id': topic_id, 'value': value}))

            # http://api.mongodb.org/python/current/api/pymongo/collection.html#pymongo.collection.Collection.bulk_write
            result = db['data'].bulk_write(bulk_publish)

            # No write errros here when
            if not result.bulk_api_result['writeErrors']:
                self.report_all_handled()
            else:
                # TODO handle when something happens during writing of data.
                _log.error('SOME THINGS DID NOT WORK')

        def query_historian(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
            """ Returns the results of the query from the mongo database.

            This historian stores data to the nearest second.  It will not
            store subsecond resolution data.  This is an optimisation based
            upon storage for the database.

            This function should return the results of a query in the form:
            {"values": [(timestamp1, value1), (timestamp2, value2), ...],
             "metadata": {"key1": value1, "key2": value2, ...}}

             metadata is not required (The caller will normalize this to {}
             for you)
            """
            try:
                topic_id = self.topic_map.get(topic, None)
            except:
                self.topic_map = {}
                _log.debug('CONNECTED TO {}'.format(self.database_name))
                for row in self.mongoclient[self.database_name]['topics'].find():
                    self.topic_map[row['topic_name']] = row['_id']
                    self.topic_map[row['_id']] = row['topic_name']

                topic_id = self.topic_map.get(topic, None)

            if not topic_id:
                _log.debug('Topic id was None for topic: {}'.format(topic))
                return {}

            if self.mongoclient is None:
                _log.debug('No mongo client available')
                return {}

            db = self.mongoclient[self.database_name]

            ts_filter = {}
            order_by = 1
            if order == 'LAST_TO_FIRST':
                order_by = -1
            if start is not None:
                ts_filter["$gte"] = start
            if end is not None:
                ts_filter["$lte"] = end
            if count is None:
                count = 100
            skip_count = 0
            if skip > 0:
                skip_count = skip

            find_params = {"topic_id": ObjectId(topic_id)}
            if ts_filter:
                find_params['ts'] = ts_filter

            cursor = db["data"].find(find_params)
            cursor = cursor.skip(skip_count).limit(count)
            cursor = cursor.sort( [ ("ts", order_by) ] )
            _log.debug('cursor count is: {}'.format(cursor.count()))

            # Create list of tuples for return values.
            values = [(row['ts'].isoformat(), row['value']) for row in cursor]

            return {'values': values}

        def query_topic_list(self):
            if self.mongoclient is None:
                _log.debug('self.mongo was None')
                return None

            items = self.get_topic_map()
            _log.debug('topic_list: {}'.format(items))
            #_log.debug(items)
            #items = ['abcdef'] # self.get_topic_map().keys()
            return items.keys()

        def get_topic_map(self):
            if self.mongoclient is None:
                self.mongoclient = self.get_mongo_client()

            _log.debug('getting topic map')
            db = self.mongoclient.get_default_database()
            cursor = db["topics"].find()
            _log.debug("Topic count {}".format(cursor.count()))
            res = {}
            for document in cursor:
                res[document['topic_name']] = document['_id']
            _log.debug('RETURNING {}'.format(res))
            return res

        def get_mongo_client(self):
            self._params = connection['params']
            self.database_name = self._params['database']
            hosts = connection['params']['host']
            ports = connection['params']['port']
            user = connection['params']['user']
            passwd = connection['params']['passwd']

            if isinstance(hosts, list):
                if not ports:
                    hosts=','.join(hosts)
    	        else:
                    if len(ports) != len(hosts):
                        _log.exception('port an hosts must have the same number of items')
                        self.core.stop()
    	            hostports = zip(hosts,ports)
                    hostports = [str(e[0])+':'+str(e[1]) for e in hostports]
                    hosts = ','.join(hostports)
            else:
    	        if isinstance(ports, list):
                    _log.exception('port cannot be a list if hosts is not also a list.')
                    self.core.stop()
                hosts = '{}:{}'.format(hosts,ports)

            self._params = {'hostsandports': hosts, 'user': user,
                'passwd': passwd, 'database': self.database_name}

            mongo_uri = "mongodb://{user}:{passwd}@{hostsandports}/{database}"
            mongo_uri = mongo_uri.format(**self._params)
            print(mongo_uri)
            self.mongoclient = pymongo.MongoClient(mongo_uri)
            if self.mongoclient == None:
                _log.exception("Couldn't connect using specified configuration credentials")
                self.core.stop()

            return self.mongoclient

        def historian_setup(self):
            _log.debug("HISTORIAN SETUP")
            self.mongoclient = self.get_mongo_client()
            self.topic_map = self.get_topic_map()


    MongodbHistorian.__name__ = 'MongodbHistorian'
    return MongodbHistorian(identity=identity, **kwargs)



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
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
