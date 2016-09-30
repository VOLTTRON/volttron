# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
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
import inspect
import logging
import os, os.path
from pprint import pprint
import re
import sys
import uuid

import gevent
from zmq.utils import jsonapi

from volttron.platform.vip.agent import Core, Agent
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from gevent.core import callback
from __builtin__ import list

#import sqlhistorian
#import sqlhistorian.settings
#import settings


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'


def simpleforwarder(config_path, **kwargs):

    config = utils.load_config(config_path)
    connection = config.get('connection', None);

    destination_vip = config.get('destination-vip')
    identity = config.get('identity', kwargs.pop('identity', None))
    forward_identity = config.get('forward_identity', None)
    forward_points = config.get('forward_points', [])
    
    point_ex = [re.compile(v) for v in forward_points]
    has_point_ex = len(point_ex) > 0
        
    assert destination_vip
                
    class SimpleForwarder(Agent):
        '''This is a simple example of a historian agent that writes stuff
        to a SQLite database. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        '''

        
        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):
            '''
            Subscribes to the platform message bus on the actuator, record,
            datalogger, and device topics to capture data.
            '''
            _log.info('Starting forwarder to {}'.format(destination_vip))
            
            
            agent = Agent(identity=forward_identity, address=destination_vip)
            event = gevent.event.Event()
            
            # agent.core.run set the event flag to true when agent is running
            gevent.spawn(agent.core.run, event)
            
            # Wait until the agent is fully initialized and ready to 
            # send and receive messages.
            event.wait()

            self._target_platform = agent
            
            #subscribe to everything on the local bus.
            self.vip.pubsub.subscribe(peer='pubsub', prefix='', 
                                     callback=self.data_received)
    

        def data_received(self, peer, sender, bus, topic, headers, message):
            
            def publish_external(agent, topic, headers, message):
                try:
                    _log.debug('Attempting to publish remotely {}, {}, {}'.format(topic, headers, message))
                    agent.vip.pubsub.publish(peer='pubsub',
                                topic=topic,
                                headers=headers,
                                message=message).get(timeout=30)
                except:
                    _log.debug('Data dropped {}, {}, {}'.format(topic, headers, message))

            if sender == 'pubsub.compat':
                message = jsonapi.loads(message[0])
                del(headers[headers_mod.CONTENT_TYPE])
                assert isinstance(message, list)
                assert isinstance(message[0], dict)
                assert isinstance(message[1], dict)
                print("MESSAGE VALUES ARE: {}".format(message[0]))
                print("DATA VALUES ARE: {}".format(message[1]))
                for v in message[1].values():
                    assert 'tz' in v.keys()
                    assert 'units' in v.keys()
                    assert 'type' in v.keys()
                #message = [jsonapi.loads(message[0]), jsonapi.loads(message[1])]
                                            
            if has_point_ex:
                for rex in point_ex:
                    if rex.match(topic):
                        publish_external(self._target_platform, topic, headers, message)
            else:
                publish_external(self._target_platform, topic, headers, message)
                    
            
        @Core.receiver("onstop")
        def stopping(self, sender, **kwargs):
            '''
            Release subscription to the message bus because we are no longer able
            to respond to messages now.
            '''
            try:
                # unsubscribes to all topics that we are subscribed to.
                self.vip.pubsub.unsubscribe(peer='pubsub', prefix=None, callback=None)
            except KeyError:
                # means that the agent didn't start up properly so the pubsub
                # subscriptions never got finished.
                pass
    SimpleForwarder.__name__ = 'SimpleForwarder'
    return SimpleForwarder(**kwargs)



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(simpleforwarder)
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
