# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
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
        print(message)
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
        print(sub.recv_multipart())

@pytest.mark.slow
@pytest.mark.zmq
def test_broker():
    pub = zmq.Socket(ctx, zmq.PUB)
    pull = zmq.Socket(ctx, zmq.PULL)
    pub.bind('ipc:///tmp/volttron-platform-agent-subscribe')
    pull.bind('ipc:///tmp/volttron-platform-agent-publish')

    pub.send_multipart([b'topic1', b'Hello world1'])
    time.sleep(2)
    pub.send_multipart([b'foo', b'bar'])
    time.sleep(2)
    pub.send_multipart([b'topic2', b'Goodbye'])
    time.sleep(2)
    pub.send_multipart([b'platform', b'Hello from platform'])
    time.sleep(2)
    pub.send_multipart([b'platform.shutdown', b'Goodbye'])

if __name__ == '__main__':
    subscriber()
