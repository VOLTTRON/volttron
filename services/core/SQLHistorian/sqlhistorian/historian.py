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

# }}}
from __future__ import absolute_import, print_function

import datetime
import errno
import inspect
import logging
import threading
import os, os.path
from pprint import pprint
import sys
import uuid

import gevent
from zmq.utils import jsonapi

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

__version__ = "3.5.0"


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

    # determine if identity is specified in the config file.  If so, then
    # add it identity to the kwargs.
    identity = config.get('identity', None)
    if identity:
        kwargs['identity'] = identity

    mod_name = databaseType+"functs"
    mod_name_path = "sqlhistorian.db.{}".format(mod_name)
    loaded_mod = __import__(mod_name_path, fromlist=[mod_name])
    
    for name, cls in inspect.getmembers(loaded_mod):
        # assume class is not the root dbdriver
        if inspect.isclass(cls) and name != 'DbDriver':
            DbFuncts = cls
            break
    try:
        _log.debug('Historian using module: '+DbFuncts.__name__)
    except NameError:
        functerror = 'Invalid module named '+mod_name_path+ "."
        raise Exception(functerror)

    class SQLHistorian(BaseHistorian):
        '''This is a simple example of a historian agent that writes stuff
        to a SQLite database. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        '''

        def __init__(self, **kwargs):
            """ Initialise the historian.

            The historian makes two connections to the data store.  Both of
            these connections are available across the main and processing
            thread of the historian.  topic_map and topic_meta are used as
            cache for the meta data and topic maps.

            :param kwargs:
            :return:
            """
            self.reader = DbFuncts(**connection['params'])
            self.writer = DbFuncts(**connection['params'])
            self.topic_map = {}
            self.topic_meta = {}

            super(SQLHistorian, self).__init__(**kwargs)

        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):
            """ Called right after connections to the Router occured.

            :param sender:
            :param kwargs:
            :return:
            """
            _log.info("Starting historian with identity: {}".format(
                self.core.identity
            ))
            _log.debug("starting Thread is: {}".format(
                threading.currentThread().getName())
            )

            self.topic_map.update(self.reader.get_topic_map())

            if self.core.identity == 'platform.historian':
                if 'platform.agent' in self.vip.peerlist().get(timeout=2):
                    _log.info(
                        'Registering with platform.agent as a  service.'
                    )
                    self.vip.rpc.call('platform.agent', 'register_service',
                                      self.core.identity).get(timeout=2)
                else:
                    _log.info('No platform.agent available to register with.')
                # # Check to see if the platform agent is available, if it isn't then
                # # subscribe to the /platform topic to be notified when the platform
                # # agent becomes available.
                # try:
                #     ping = self.vip.ping('platform.agent',
                #                          'awake?').get(timeout=3)
                #     _log.debug("Ping response was? "+ str(ping))
                #     self.vip.rpc.call('platform.agent', 'register_service',
                #                       self.core.identity).get(timeout=3)
                # except Unreachable:
                #     _log.debug('Could not register historian service')
                # finally:
                #     self.vip.pubsub.subscribe('pubsub', '/platform',
                #                               self.__platform)
                #     _log.debug("Listening to /platform")

        # def __platform(self, peer, sender, bus, topic, headers, message):
        #     _log.debug('Platform is now: {}'.format(message))
        #     if message == 'available' and \
        #             self.core.identity == 'platform.historian':
        #         gevent.spawn(self.vip.rpc.call, 'platform.agent', 'register_service',
        #                            self.core.identity)
        #         gevent.sleep(0)

        def publish_to_historian(self, to_publish_list):
            thread_name = threading.currentThread().getName()
            _log.debug("publish_to_historian number of items: {} Thread: {}"
                       .format(len(to_publish_list), thread_name))

            try:
                real_published = []
                for x in to_publish_list:
                    ts = x['timestamp']
                    topic = x['topic']
                    value = x['value']
                    meta = x['meta']

                    # look at the topics that are stored in the database
                    # already to see if this topic has a value
                    topic_id = self.topic_map.get(topic, None)
    
                    if topic_id is None:
                        _log.debug('Inserting topic: {}'.format(topic))
                        row = self.writer.insert_topic(topic)
                        topic_id = row[0]
                        self.topic_map[topic] = topic_id
                        _log.debug('TopicId: {} => {}'.format(topic_id, topic))

                    old_meta = self.topic_meta.get(topic_id, {})
                    if set(old_meta.items()) != set(meta.items()):
                        _log.debug('Updating meta for topic: {} {}'.format(
                            topic, meta
                        ))
                        self.writer.insert_meta(topic_id, meta)
                        self.topic_meta[topic_id] = meta
                    
                    if self.writer.insert_data(ts,topic_id, value):
                        # _log.debug('item was inserted')
                        real_published.append(x)

                if len(real_published) > 0:            
                    if self.writer.commit():
                        _log.debug('published {} data values'.format(
                            len(to_publish_list))
                        )
                        self.report_all_handled()
                    else:
                        msg = 'commit error. rolling back {} values.'
                        _log.debug(msg.format(len(to_publish_list)))
                        self.writer.rollback()
                else:
                    _log.debug('Unable to publish {}'.format(len(to_publish_list)))
            except:
                self.writer.rollback()
                # Raise to the platform so it is logged properly.
                raise

        def query_topic_list(self):

            _log.debug("query_topic_list Thread is: {}".format(
                threading.currentThread().getName())
            )
            _log.debug("The topic_map is: ".format(self.topic_map))
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
            _log.debug("query_historian Thread is: {}".format(
                threading.currentThread().getName())
            )

            results = self.reader.query(
                topic, start=start, end=end, skip=skip, count=count,
                order=order)

            topic_id = self.topic_map[topic]
            results['metadata'] = self.topic_meta.get(topic_id, {})
            return results

        def historian_setup(self):
            thread_name = threading.currentThread().getName()
            _log.debug("historian_setup on Thread: {}".format(thread_name))

    SQLHistorian.__name__ = 'SQLHistorian'
    return SQLHistorian(**kwargs)


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
