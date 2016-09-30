# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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
#}}}

import logging
import sys
import uuid

import gevent
import zmq
import zmq.green
import zmq.utils
import zmq.utils.z85
#import zmq.green as zmq
zmq.green.green = zmq.green
zmq.green.utils = zmq.utils
sys.modules['zmq'] = zmq.green
zmq = zmq.green

#def wrap_context(Context_):
#    ctx = Context_()
#    def Context():
#        return ctx
#    return Context
#zmq.Context = wrap_context(zmq.Context)


from volttron.platform.main import agent_exchange
from multibuilding.agent import MultiBuildingAgent

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform import messaging
from volttron.platform.messaging import topics
from volttron.platform.messaging.headers import COOKIE


def cookie_headers(request, **headers):
    if request:
        try:
            headers[COOKIE] = request[COOKIE]
        except KeyError:
            pass
    return headers
    

class Requester(PublishMixin, BaseAgent):
    def __init__(self, **kwargs):
        super(Requester, self).__init__(**kwargs)
        self.uuid = str(uuid.uuid4())

    def setup(self):
        super(Requester, self).setup()
        print 'Sending hello'
        self.publish(topics.BUILDING_SEND(
                campus='campus1', building='building1', topic='test/topic/hello'),
                {COOKIE: self.uuid}, 'Hello, Building!')

    @matching.match_exact(topics.BUILDING_RECV(
            campus='campus1', building='building1', topic='test/topic/reply'))
    def on_reply(self, topic, headers, message, match):
        if headers.get(COOKIE) != self.uuid:
            return
        print 'Received response', message
        self._sub.close()


class Provider(PublishMixin, BaseAgent):
    @matching.match_exact(topic='test/topic/hello')
    def on_reply(self, topic, headers, message, match):
        print 'Received hello', message
        print 'Sending response'
        self.publish('test/topic/reply', cookie_headers(headers), 'I am here!')
        

def building(name, pub_addr, sub_addr, hosts, agent_class, keys=None):
    print 'spawning exchange for', name
    exchange = gevent.spawn(agent_exchange, pub_addr, sub_addr, name)
    config = {'hosts': hosts,
              'building-subscribe-address': hosts[name]['sub'],
              'building-publish-address': hosts[name]['pub'],
             }
    if keys:
        config.update({'public-key': keys[0],
                       'secret-key': keys[1]})
    print 'spawning mutli-building agent for', name
    mbagent = gevent.spawn(MultiBuildingAgent(config=config,
            subscribe_address=sub_addr, publish_address=pub_addr).run)
    mbagent.link(lambda *a: exchange.kill())
    print 'spawning worker agent for', name
    agent = gevent.spawn(agent_class(
            subscribe_address=sub_addr, publish_address=pub_addr).run)
    agent.link(lambda *a: exchange.kill())
    return exchange


_hosts = {'campus1/building1': {'pub': 'tcp://127.0.0.1:12101',
                                'sub': 'tcp://127.0.0.1:12102'},
          'campus1/building2': {'pub': 'tcp://127.0.0.1:12201',
                                'sub': 'tcp://127.0.0.1:12202'},
         }
_buildings = [('campus1/building1',
               'ipc://multibuilding-test-building1-pub',
               'ipc://multibuilding-test-building1-sub'),
              ('campus1/building2',
               'ipc://multibuilding-test-building2-pub',
               'ipc://multibuilding-test-building2-sub')]
_keys = [zmq.curve_keypair() for _ in xrange(2)]


def two_building_test():
    building1 = building(*(_buildings[0] + (_hosts, Provider)))
    building2 = building(*(_buildings[1] + (_hosts, Requester)))
    building2.join()
    gevent.sleep(1)
    building1.kill()


def two_building_auth_test():
    hosts = _hosts.copy()
    hosts['campus1/building1'].update({'public-key': _keys[0][0],
                                       'allow': 'pub'})
    hosts['campus1/building2'].update({'public-key': _keys[1][0],
                                       'allow': 'pub'})
    building1 = building(*(_buildings[0] + (hosts, Provider, _keys[0])))
    building2 = building(*(_buildings[1] + (hosts, Requester, _keys[1])))
    building2.join()
    gevent.sleep(1)
    building1.kill()



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    #two_building_test()
    two_building_auth_test()

