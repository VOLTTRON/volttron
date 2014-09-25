# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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

import zmq
import time

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
        
def broker_test():
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
