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
    
    destination_vip = config.get('destination-vip')
    identity = config.get('identity', kwargs.pop('identity', None))
            
    class ForwardHistorian(BaseHistorian):
        '''This historian forwards data to another platform.
        '''

        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):
            
            print('Starting address: {} identity: {}'.format(self.core.address, self.core.identity))
            #TODO: Check that destination exists
            self.topic_map = {}

            

        def __platform(self, peer, sender, bus, topic, headers, message):
            _log.debug('Platform is now: {}'.format(message))
            

        def publish_to_historian(self, to_publish_list):
            _log.debug("publish_to_historian number of items: {}"
                       .format(len(to_publish_list)))
            
            # load a topic map if there isn't one yet.
#             try:
#                 self.topic_map.items()
#             except:
#                 self.topic_map = self.reader.get_topic_map()

            
            datalog ={}

            for x in to_publish_list:
                ts = x['timestamp']
                topic = x['topic']
                value = x['value']
                meta = x['meta']
                # look at the topics that are stored in the database already
                # to see if this topic has a value
                if topic.startswith('datalogger'):
                    continue
                topic_id = self.topic_map.get(topic)

#                 if topic_id is None:
#                     row  = self.writer.insert_topic(topic)
#                     topic_id = row[0]
#                     self.topic_map[topic] = topic_id

#                 self.writer.insert_data(ts,topic_id, value)
#                 parts = topic.split('/')
#                 all_topic = '/'.join(reversed(parts[2:]))

                
                datalog[topic] = {'Readings': value,
                                  'Units': meta['units']}
                
            base_topic = 'datalogger/devices'



            
            message = jsonapi.dumps(datalog)
            
#             agent = self._get_rpc_agent(destination_vip)
            _log.debug("about to publish to destination: {}".format(destination_vip))
#                         agent.vip.publish()
#             agent.vip.pubsub.publish(peer='pubsub',headers=headers,
#                                         topic=topic,
#                                         message=message)

            self._target_platform.vip.pubsub.publish(peer='pubsub',
                                    topic=base_topic,
                                    message=datalog)


            self.report_all_published()

        def query_topic_list(self):
            if len(self.topic_map) > 0:
                return self.topic_map.keys()
            else:
                # No topics present.
                return []

        def query_historian(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
            """Not implemented
            """
            return None

        def historian_setup(self):
            _log.debug("Setting up")
            agent = Agent(identity="target",address=destination_vip)
            event = gevent.event.Event()
            agent.core.onstart.connect(lambda *a, **kw: event.set(), event)
            gevent.spawn(agent.core.run)
            event.wait()
            self._target_platform = agent

    ForwardHistorian.__name__ = 'ForwardHistorian'
    return ForwardHistorian(identity=identity, **kwargs)



def main(argv=sys.argv):
    '''Main method called by the aip.'''
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
