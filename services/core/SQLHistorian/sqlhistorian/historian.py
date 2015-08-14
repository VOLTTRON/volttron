# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
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
import errno
import logging
import os, os.path
from pprint import pprint
import sqlite3
import sys
import uuid

import gevent
from zmq.utils import jsonapi

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

#import sqlhistorian
#import sqlhistorian.settings
#import settings


utils.setup_logging()
_log = logging.getLogger(__name__)



def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    connection = config.get('connection', None);

    assert connection is not None
    databaseType = connection.get('type', None)
    assert databaseType is not None
    params = connection.get('params', None)
    assert params is not None
    identity = config.get('identity', kwargs.pop('identity', None))

    if databaseType == 'sqlite':
        from .db.sqlitefuncts import SqlLiteFuncts as DbFuncts
    elif databaseType == 'mysql':
        from .db.mysqlfuncts import MySqlFuncts as DbFuncts
    else:
        _log.error("Unknown database type specified!")
        raise Exception("Unkown database type specified!")
        
    class SQLHistorian(BaseHistorian):
        '''This is a simple example of a historian agent that writes stuff
        to a SQLite database. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        '''

        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):
            
            print('Starting address: {} identity: {}'.format(self.core.address, self.core.identity))
            try:
                self.reader = DbFuncts(**connection['params'])
            except AttributeError:
                self.core.stop()
                return
                        
            self.topic_map = self.reader.get_topic_map()

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
            
            # load a topic map if there isn't one yet.
            try:
                self.topic_map.items()
            except:
                self.topic_map = self.reader.get_topic_map()

            for x in to_publish_list:
                ts = x['timestamp']
                topic = x['topic']
                value = x['value']
                # look at the topics that are stored in the database already
                # to see if this topic has a value
                topic_id = self.topic_map.get(topic)

                if topic_id is None:
                    row  = self.writer.insert_topic(topic)
                    topic_id = row[0]
                    self.topic_map[topic] = topic_id

                self.writer.insert_data(ts,topic_id, value)

            _log.debug('published {} data values:'.format(len(to_publish_list)))
            self.report_all_published()

        def query_topic_list(self):
            if len(self.topic_map) > 0:
                return self.topic_map.keys()
            else:
                # No topics present.
                return []

        def query_historian(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
            """This function should return the results of a query in the form:
            {"values": [(timestamp1, value1), (timestamp2, value2), ...],
             "metadata": {"key1": value1, "key2": value2, ...}}

             metadata is not required (The caller will normalize this to {} for you)
            """
            return self.reader.query(topic, start=start, end=end, skip=skip,
                                     count=count, order=order)

        def historian_setup(self):
            try:
                self.writer = DbFuncts(**connection['params'])
            except AttributeError as exc:
                print(exc)
                self.core.stop()

    SQLHistorian.__name__ = 'SQLHistorian'
    return SQLHistorian(identity=identity, **kwargs)



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(historian)
        #utils.default_main(historian,
        #                   description='Historian agent that saves a history to a sqlite db.',
        #                   argv=argv,
        #                   no_pub_sub_socket=True)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
