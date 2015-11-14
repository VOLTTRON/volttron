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
import pymongo

import gevent

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    connection = config.get('connection', None)
    assert connection is not None

    databaseType = connection.get('type', None)
    assert databaseType is not None

    params = connection.get('params', None)
    assert params is not None

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
                                              self.__platform)
                    _log.debug("Listening to /platform")

        def __platform(self, peer, sender, bus, topic, headers, message):
            _log.debug('Platform is now: {}'.format(message))
            if message == 'available' and \
                    self.core.identity == 'platform.historian':
                gevent.spawn(self.vip.rpc.call, 'platform.agent', 'register_service',
                                   self.core.identity)
                gevent.sleep(0)

        def publish_to_historian(self, to_publish_list):
            _log.debug("publish_to_historian number of items: {}"
                       .format(len(to_publish_list)))
            try:
                real_published = []
                for x in to_publish_list:
                    ts = x['timestamp']
                    topic = x['topic']
                    value = x['value']
                    # look at the topics that are stored in the database already
                    # to see if this topic has a value
                    topic_id = self.topic_map.get(topic, None)
    
                    if topic_id is None:
                        _log.debug('Inserting topic: {}'.format(topic))
                        row  = self.insert_topic(topic)
                        topic_id = row[0]
                        self.topic_map[topic] = topic_id
                        _log.debug('TopicId: {} => {}'.format(topic_id, topic))
                    
                    if self.insert_data(ts,topic_id, value):
                        real_published.append(x)
                if len(real_published) > 0:            
                    if self.commit():
                        _log.debug('published {} data values'.format(len(to_publish_list)))
                        self.report_all_handled()
                    else:
                        _log.debug('failed to commit so rolling back {} data values'.format(len(to_publish_list)))
                        self.rollback()
                else:
                    _log.debug('Unable to publish {}'.format(len(to_publish_list)))
            except:
                self.rollback()
                # Raise to the platform so it is logged properly.
                raise

        def query_topic_list(self):
            if len(self.topic_map) > 0:
                return self.topic_map.keys()
            return []

        def query_historian(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
            """This function should return the results of a query in the form:
            {"values": [(timestamp1, value1), (timestamp2, value2), ...],
             "metadata": {"key1": value1, "key2": value2, ...}}

             metadata is not required (The caller will normalize this to {} for you)
            """
            if self.__connection is None:
                return False
            db = self.__connection[self.__connect_params["database"]]
            #Find topic_id for topic
            row = db["topics"].find_one({"topic_name": topic})
            id_ = row.topic_id

            order_by = 1
            if order == 'LAST_TO_FIRST':
                order_by = -1
            if start is not None:
                start = datetime.datetime(2000, 1, 1, 0, 0, 0)
            if end is not None:
                end = datetime.datetime(3000, 1, 1, 0, 0, 0)
            if count is None:
                count = 100
            skip_count = 0
            if skip > 0:
                skip_count = skip

            cursor = db["data"].find({
                        "topic_id": id_,
                        "ts": { "$gte": start, "$lte": end},
                    }).skip(skip_count).limit(count).sort( { "ts": order_by } )

            values = [(document.ts.isoformat(), document.value) for document in cursor]

            return {'values': values}

        #TODO: see if Mongodb has commit and rollback (or something equivalent)
        def commit(self):
            return True

        def rollback(self):
            return True

        def insert_data(self, ts, topic_id, data):
            if self.__connection is None:
                return False
            db = self.__connection[self.__connect_params["database"]]
            id_ = db["data"].insert({
                "ts": ts,
                "topic_id": topic_id,
                "value": data})

            return True

        def insert_topic(self, topic):
            if self.__connection is None:
                return False
            db = self.__connection[self.__connect_params["database"]]
            id_ = db["topics"].insert({"topic_name": topic})
            return [id_]

        def get_topic_map(self):
            if self.__connection is None:
                return False
            db = self.__connection[self.__connect_params["database"]]
            cursor = db["topics"].find()
            res = dict([(document["topic_name"], document["_id"]) for document in cursor])
            _log.debug("TOPIC MAP RESULT {}".format(res))
            return res

        def historian_setup(self):
            self.__connection = None
            self.__connect_params = connection['params']
            mongo_uri = "mongodb://{user}:{passwd}@{host}:{port}/{database}".format(**self.__connect_params)
            self.__connection = pymongo.MongoClient(mongo_uri)
            if self.__connection == None:
                _log.exception("Couldn't connect using specified configuration credentials")
                self.core.stop()
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
