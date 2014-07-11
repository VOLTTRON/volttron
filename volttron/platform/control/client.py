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

# pylint: disable=W0142,W0403
#}}}

import argparse
import os
import sys

from .. import aip
from .. import config
from .server import ControlConnector


def install_agent(parser, opts):
    opts.aip.install_agent(opts.wheel)

def remove_agent(parser, opts):
    opts.aip.remove_agent(opts.agent)

def list_agents(parser, opts):
    agents = opts.aip.list_agents()
    if not agents:
        return
    agents.sort()
    for name in agents:
        sys.stdout.writelines([name, '\n'])

def status_agents(parser, opts):
    agents = ControlConnector(opts.control_socket).call.status_agents()
    if not agents:
        return
    agents.sort()
    width = max(5, min(60, max(len(x[0]) for x in agents)))
    fmt = '{:{}}  {:>9}  {:>6}\n'
    sys.stderr.write(fmt.format('AGENT', width, 'AUTOSTART', 'STATUS'))
    for name, enabled, (pid, status) in agents:
        if enabled is None:
            enabled = 'n/a'
        elif enabled:
            enabled = 'enabled '
        else:
            enabled = 'disabled '
        sys.stdout.write(fmt.format(name, width, enabled,
            ('running [{}]'.format(pid) if status is None else str(status))
             if pid else ''))

def enable_agent(parser, opts):
    opts.aip.enable_agent(opts.agent)

def disable_agent(parser, opts):
    opts.aip.disable_agent(opts.agent)

def start_agent(parser, opts):
    ControlConnector(opts.control_socket).call.start_agent(opts.agent)

def stop_agent(parser, opts):
    ControlConnector(opts.control_socket).call.stop_agent(opts.agent)

def run_agent(parser, opts):
    ControlConnector(opts.control_socket).call.run_agent(opts.agent)

def shutdown_agent(parser, opts):
    ControlConnector(opts.control_socket).call.shutdown()


def main(argv=sys.argv):
    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]),
        description='Manage and control VOLTTRON agents.',
    )
    parser.add_argument('--control-socket', metavar='FILE',
        help='path to socket used for control messages')

    subparsers = parser.add_subparsers(help='command help')

    install = subparsers.add_parser('install', help='install agent from wheel')
    install.add_argument('wheel', help='path to agent wheel')
    install.set_defaults(func=install_agent)

    remove = subparsers.add_parser('remove', help='remove agent')
    remove.add_argument('agent', help='name of agent')
    remove.set_defaults(func=remove_agent)

    list_ = subparsers.add_parser('list', help='list installed agent')
    list_.set_defaults(func=list_agents)

    status = subparsers.add_parser('status', help='show status of agents')
    status.set_defaults(func=status_agents)

    enable = subparsers.add_parser('enable',
        help='enable agent to start automatically')
    enable.add_argument('agent', help='name of agent')
    enable.set_defaults(func=enable_agent)

    disable = subparsers.add_parser('disable',
        help='prevent agent from start automatically')
    disable.add_argument('agent', help='name of agent')
    disable.set_defaults(func=disable_agent)

    start = subparsers.add_parser('start',
        help='start installed agent')
    start.add_argument('agent', help='name of agent')
    start.set_defaults(func=start_agent)

    stop = subparsers.add_parser('stop',
        help='stop agent')
    stop.add_argument('agent', help='name of agent')
    stop.set_defaults(func=stop_agent)

    run = subparsers.add_parser('run',
        help='start any agent by path')
    run.add_argument('agent', help='path to agent directory')
    run.set_defaults(func=run_agent)

    shutdown = subparsers.add_parser('shutdown',
        help='stop all agents')
    shutdown.set_defaults(func=shutdown_agent)

    parser.set_defaults(**config.get_volttron_defaults())

    opts = parser.parse_args(argv[1:])
    expandall = lambda string: os.path.expandvars(os.path.expanduser(string))
    opts.volttron_home = expandall(os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = opts.volttron_home
    opts.control_socket = expandall(opts.control_socket)
    opts.aip = aip.AIPplatform(opts)
    opts.aip.setup()
    opts.func(parser, opts)


def _main():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == '__main__':
    _main()
