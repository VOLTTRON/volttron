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

import sys
import time

import pytest
import zmq

publish_address = 'ipc:///tmp/volttron-platform-agent-publish'
subscribe_address = 'ipc:///tmp/volttron-platform-agent-subscribe'


ctx = zmq.Context()

def broker():
    pub = zmq.Socket(ctx, zmq.PUB)
    pull = zmq.Socket(ctx, zmq.PULL)
    pub.bind('ipc:///tmp/volttron-platform-agent-subscribe')
    pull.bind('ipc:///tmp/volttron-platform-agent-publish')
    while True:
        message = pull.recv_multipart()
        print message
        pub.send_multipart(message)


def publisher():
    push = zmq.Socket(ctx, zmq.PUSH)
    push.connect('ipc:///tmp/volttron-platform-agent-publish')
    while True:
        sys.stdout.write('Topic: ')
        sys.stdout.flush()
        topic = sys.stdin.readline()
        sys.stdout.write('Message: ')
        sys.stdout.flush()
        message = sys.stdin.readline()
        push.send_multipart([topic, message])


def subscriber():
    sub = zmq.Socket(ctx, zmq.SUB)
    sub.connect('ipc:///tmp/volttron-platform-agent-subscribe')
    sub.subscribe = ''
    while True:
        print sub.recv_multipart()

@pytest.mark.slow        
@pytest.mark.zmq
def test_broker():
    pub = zmq.Socket(ctx, zmq.PUB)
    pull = zmq.Socket(ctx, zmq.PULL)
    pub.bind('ipc:///tmp/volttron-platform-agent-subscribe')
    pull.bind('ipc:///tmp/volttron-platform-agent-publish')
    
    pub.send_multipart(['topic1', 'Hello world1'])
    time.sleep(2)
    pub.send_multipart(['foo', 'bar'])
    time.sleep(2)
    pub.send_multipart(['topic2', 'Goodbye'])
    time.sleep(2)
    pub.send_multipart(['platform', 'Hello from platform'])
    time.sleep(2)
    pub.send_multipart(['platform.shutdown', 'Goodbye'])

if __name__ == '__main__':
    subscriber()
