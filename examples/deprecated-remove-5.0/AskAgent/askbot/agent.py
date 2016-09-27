# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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

'''VOLTTRON platform™ example service for user interaction.

Opens a listening socket on 127.0.0.1:7575 to interact with the user by
displaying the current state and asking for a new one. When the new
state is entered, the new state is printed and the next state is
requested.  State transitions are sent to the VOLTTRON message bus on
the topic 'askbot/state' as a two-tuple (previous_state, current_state).

The listening address, backlog count, and initial state can be
configured through the agent configuration file.

Many security and error checks are omitted for clarity. Please do not
use this agent without validating all connections and inputs.

Connect to the agent using one of the following commands:

    nc 127.0.0.1 7575
    netcat 127.0.0.1 7575
    socat - TCP-CONNECT:127.0.0.1:7575
    telnet 127.0.0.1 7575
'''

import logging
import socket
import sys

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils


_log = logging.getLogger(__name__)
__version__ = '0.1'

class AskAgent(PublishMixin, BaseAgent):
    '''Example agent to demonstrate user interaction.'''

    def __init__(self, config_path, **kwargs):
        '''Initialize instance attributes.'''
        super(AskAgent, self).__init__(**kwargs)
        self.config = {'address': ('127.0.0.1', 7575),
                       'state': 'on', 'backlog': 5}
        if config_path:
            self.config.update(utils.load_config(config_path))
        self.ask_socket = None
        self.state = None

    def setup(self):
        '''Perform additional setup.'''
        super(AskAgent, self).setup()
        self.change_state(str(self.config['state']))
        # Open a socket to listen for incoming connections
        self.ask_socket = sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(tuple(self.config['address']))
        sock.listen(int(self.config['backlog']))
        # Register a callback to accept new connections
        self.reactor.register(self.ask_socket, self.handle_accept)

    def change_state(self, state):
        '''Change state and notify other agents.'''
        prev_state, self.state = self.state, state
        self.publish_json('askbot/state', {}, (prev_state, state))

    def handle_accept(self, ask_sock):
        '''Accept new connections.'''
        sock, addr = ask_sock.accept()
        file = sock.makefile('r+', 0)
        _log.info('Connection {} accepted from {}:{}'.format(file.fileno(), *addr))
        try:
            self.ask_input(file)
        except socket.error:
            _log.info('Connection {} disconnected'.format(file.fileno()))
        # Register a callback to recieve input from the client.
        self.reactor.register(file, self.handle_input)

    def ask_input(self, file):
        '''Send the current state and ask for a new one.'''
        file.write("I'm currently {!r}. "
                   "What state do you want me in? ".format(self.state))

    def handle_input(self, file):
        '''Recieve the new state from the client and ask for another.'''
        try:
            response = file.readline()
            if not response:
                raise socket.error('disconnected')
            response = response.strip()
            if response:
                self.change_state(response)
            self.ask_input(file)
        except socket.error:
            _log.info('Connection {} disconnected'.format(file.fileno()))
            self.reactor.unregister(file)


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.setup_logging()
    try:
        utils.default_main(AskAgent,
            description='VOLTTRON platform™ agent for remote user interaction.',
            argv=argv)
    except Exception:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
