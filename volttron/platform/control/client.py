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

import gevent.monkey
gevent.monkey.patch_all()

import argparse
import collections
import logging
from logging import handlers
import os
import re
import signal
import sys
import traceback

from flexjsonrpc.core import RemoteError

from .. import aip
from .. import config
from .server import ControlConnector, get_peercred
from volttron.platform.agent import utils

try:
    import volttron.restricted
except ImportError:
    have_restricted = False
else:
    from paramiko import PasswordRequiredException, SSHException
    from volttron.restricted import comms, resmon
    have_restricted = True

_stdout = sys.stdout
_stderr = sys.stderr

_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)


def log_to_file(file, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
            '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    
Agent = collections.namedtuple('Agent', 'name tag uuid')

def _list_agents(aip):
    return [Agent(name, aip.agent_tag(uuid), uuid)
            for uuid, name in aip.list_agents().iteritems()]

def escape(pattern):
    strings = re.split(r'([*?])', pattern)
    if len(strings) == 1:
        return re.escape(pattern), False
    return ''.join('.*' if s == '*' else '.' if s == '?' else
                   s if s in [r'\?', r'\*'] else re.escape(s)
                   for s in strings), True

def filter_agents(agents, patterns, opts):
    by_name, by_tag, by_uuid = opts.by_name, opts.by_tag, opts.by_uuid
    for pattern in patterns:
        regex, wildcard = escape(pattern)
        result = set()
        if not (by_uuid or by_name or by_tag):
            reobj = re.compile(regex)
            matches = [agent for agent in agents if reobj.match(agent.uuid)]
            if len(matches) == 1:
                result.update(matches)
        else:
            reobj = re.compile(regex + '$')
            if by_uuid:
                result.update(agent for agent in agents if reobj.match(agent.uuid))
            if by_name:
                result.update(agent for agent in agents if reobj.match(agent.name))
            if by_tag:
                result.update(agent for agent in agents if reobj.match(agent.tag or ''))
        yield pattern, result

def filter_agent(agents, pattern, opts):
    return next(filter_agents(agents, [pattern], opts))[1]


def install_agent(opts):
    aip = opts.aip
    for wheel in opts.wheel:
        try:
            tag, filename = wheel.split('=', 1)
        except ValueError:
            tag, filename = None, wheel
        try:
            uuid = aip.install_agent(filename)
            if tag:
                aip.tag_agent(uuid, tag)
        except Exception as exc:
            if opts.debug:
                traceback.print_exc()
            _stderr.write('{}: error: {}: {}\n'.format(opts.command, exc, filename))
            return 10
        name = aip.agent_name(uuid)
        _stdout.write('Installed {} as {} {}\n'.format(filename, uuid, name))

def tag_agent(opts):
    agents = filter_agent(_list_agents(opts.aip), opts.agent, opts)
    if len(agents) != 1:
        if agents:
            msg = 'multiple agents selected'
        else:
            msg = 'agent not found'
        _stderr.write('{}: error: {}: {}\n'.format(opts.command, msg, opts.agent))
        return 10
    agent, = agents
    if opts.tag:
        _stdout.write('Tagging {} {}\n'.format(agent.uuid, agent.name))
        opts.aip.tag_agent(agent.uuid, opts.tag)
    elif opts.remove:
        if agent.tag is not None:
            _stdout.write('Removing tag for {} {}\n'.format(agent.uuid, agent.name))
            opts.aip.tag_agent(agent.uuid, None)
    else:
        if agent.tag is not None:
            _stdout.writelines([agent.tag, '\n'])

def remove_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
        elif len(match) > 1 and not opts.force:
            _stderr.write('{}: error: pattern returned multiple agents: {}\n'.format(opts.command, pattern))
            _stderr.write('Use -f or --force to force removal of multiple agents.\n')
            return 10
        for agent in match:
            _stdout.write('Removing {} {}\n'.format(agent.uuid, agent.name))
            opts.aip.remove_agent(agent.uuid)

def _calc_min_uuid_length(agents):
    n = 0
    for agent1 in agents:
        for agent2 in agents:
            if agent1 is agent2:
                continue
            common_len = len(os.path.commonprefix([agent1.uuid, agent2.uuid]))
            if common_len > n:
                n = common_len
    return n + 1

def list_agents(opts):
    agents = _list_agents(opts.aip)
    if opts.pattern:
        filtered = set()
        for pattern, match in filter_agents(agents, opts.pattern, opts):
            if not match:
                _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
            filtered |= match
        agents = list(filtered)
    if not agents:
        return
    if not opts.min_uuid_len:
        n = None
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    agents.sort()
    name_width = max(5, max(len(agent.name) for agent in agents))
    tag_width = max(3, max(len(agent.tag or '') for agent in agents))
    fmt = '{} {:{}} {:{}} {:>3}\n'
    _stderr.write(fmt.format(' '*n, 'AGENT', name_width, 'TAG', tag_width, 'PRI'))
    for agent in agents:
        priority = opts.aip.agent_priority(agent.uuid) or ''
        _stdout.write(fmt.format(agent.uuid[:n], agent.name, name_width,
                                 agent.tag or '', tag_width, priority))

def status_agents(opts):
    agents = {agent.uuid: agent for agent in _list_agents(opts.aip)}
    status = {}
    for uuid, name, stat in \
            ControlConnector(opts.control_socket).call.status_agents():
        try:
            agent = agents[uuid]
        except KeyError:
            agents[uuid] = agent = Agent(name, None, uuid)
        status[uuid] = stat
    agents = agents.values()
    if opts.pattern:
        filtered = set()
        for pattern, match in filter_agents(agents, opts.pattern, opts):
            if not match:
                _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
            filtered |= match
        agents = list(filtered)
    if not agents:
        return
    agents.sort()
    if not opts.min_uuid_len:
        n = 36
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    name_width = max(5, max(len(agent.name) for agent in agents))
    tag_width = max(3, max(len(agent.tag or '') for agent in agents))
    fmt = '{} {:{}} {:{}} {:>6}\n'
    _stderr.write(fmt.format(' '*n, 'AGENT', name_width, 'TAG', tag_width, 'STATUS'))
    for agent in agents:
        try:
            pid, stat = status[agent.uuid]
        except KeyError:
            pid = stat = None
        _stdout.write(fmt.format(agent.uuid[:n], agent.name, name_width,
            agent.tag or '', tag_width, ('running [{}]'.format(pid)
                 if stat is None else str(stat)) if pid else ''))

def clear_status(opts):
    ControlConnector(opts.control_socket).call.clear_status(opts.clear_all)

def enable_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
        for agent in match:
            _stdout.write('Enabling {} {} with priority {}\n'.format(
                    agent.uuid, agent.name, opts.priority))
            opts.aip.prioritize_agent(agent.uuid, opts.priority)

def disable_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
        for agent in match:
            priority = opts.aip.agent_priority(agent.uuid)
            if priority is not None:
                _stdout.write('Disabling {} {}\n'.format(agent.uuid, agent.name))
                opts.aip.prioritize_agent(agent.uuid, None)

def start_agent(opts):
    conn = ControlConnector(opts.control_socket)
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
        for agent in match:
            pid, status = conn.call.agent_status(agent.uuid)
            if pid is None or status is not None:
                _stdout.write('Starting {} {}\n'.format(agent.uuid, agent.name))
                conn.call.start_agent(agent.uuid)

def stop_agent(opts):
    conn = ControlConnector(opts.control_socket)
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write('{}: error: agent not found: {}\n'.format(opts.command, pattern))
        for agent in match:
            pid, status = conn.call.agent_status(agent.uuid)
            if pid and status is None:
                _stdout.write('Stopping {} {}\n'.format(agent.uuid, agent.name))
                conn.call.stop_agent(agent.uuid)

def run_agent(opts):
    conn = ControlConnector(opts.control_socket)
    for directory in opts.directory:
        conn.call.run_agent(directory)

def shutdown_agents(opts):
    conn = ControlConnector(opts.control_socket)
    conn.call.shutdown()
    if opts.platform:
        pid, uid, gid = get_peercred(conn._sock)
        os.kill(pid, signal.SIGINT)

def create_cgroups(opts):
    try:
        resmon.create_cgroups(user=opts.user, group=opts.group)
    except ValueError as exc:
        _stderr.write('{}: error: {}\n'.format(opts.command, exc))
        return os.EX_NOUSER

def send_agent(opts):
    _log.debug("send_agent: "+ str(opts))
    ssh_dir = os.path.join(opts.volttron_home, 'ssh')
    _log.debug('ssh_dir: ' + ssh_dir)
    try:
        host_key, client = comms.client(ssh_dir, opts.host, opts.port)
    except (OSError, IOError, PasswordRequiredException, SSHException) as exc:
        if opts.debug:
            traceback.print_exc()
        _stderr.write('{}: error: {}\n'.format(opts.command, exc))
        if isinstance(exc, OSError):
            return os.EX_OSERR
        if isinstance(exc, IOError):
            return os.EX_IOERR
        return os.EX_SOFTWARE
    if host_key is None:
        _stderr.write('warning: no public key found for remote host\n')
    with client:
        for wheel in opts.wheel:
            with open(wheel) as file:
                client.send_and_start_agent(file)


def priority(value):
    n = int(value)
    if not 0 <= n < 100:
        raise ValueError('invalid priority (0 <= n < 100): {}'.format(n))
    return '{:02}'.format(n)


def main(argv=sys.argv):
    volttron_home = config.expandall(
            os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = volttron_home

    global_args = config.ArgumentParser(description='global options', add_help=False)
    global_args.add_argument('-c', '--config', metavar='FILE',
        action='parse_config', ignore_unknown=True,
        sections=[None, 'global', 'volttron-ctl'],
        help='read configuration from FILE')
    global_args.add_argument('--debug', action='store_true',
        help='show tracbacks for errors rather than a brief message')
    global_args.add_argument('--control-socket', metavar='FILE',
        help='path to socket used for control messages')

    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]), add_help=False,
        description='Manage and control VOLTTRON agents.',
        usage='%(prog)s command [OPTIONS] ...',
        argument_default=argparse.SUPPRESS,
        parents=[global_args]
    )
    parser.add_argument('-l', '--log', metavar='FILE', default=None,
        help='send log output to FILE instead of stderr')
    parser.add_argument('-L', '--log-config', metavar='FILE',
        help='read logging configuration from FILE')
    parser.add_argument('-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument('-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument('--verboseness', type=int, metavar='LEVEL',
        default=logging.WARNING,
        help='set logger verboseness')

    filterable = config.ArgumentParser(add_help=False)
    filterable.add_argument('--name', dest='by_name', action='store_true',
        help='filter/search by agent name')
    filterable.add_argument('--tag', dest='by_tag', action='store_true',
        help='filter/search by tag name')
    filterable.add_argument('--uuid', dest='by_uuid', action='store_true',
        help='filter/search by UUID (default)')
    filterable.set_defaults(by_name=False, by_tag=False, by_uuid=False)

    parser.add_help_argument()
    parser.set_defaults(
        log_config=None,
        volttron_home=volttron_home,
        control_socket='@$VOLTTRON_HOME/run/control',
    )

    subparsers = parser.add_subparsers(title='commands', metavar='', dest='command')
    def add_parser(*args, **kwargs):
        parents = kwargs.get('parents', [])
        parents.append(global_args)
        kwargs['parents'] = parents
        return subparsers.add_parser(*args, **kwargs)

    install = add_parser('install', help='install agent from wheel',
        epilog='The wheel argument can take the form tag=wheelfile to tag the '
               'agent during install without requiring a separate call to '
               'the tag command.')
    install.add_argument('wheel', nargs='+', help='path to agent wheel')
    if have_restricted:
        install.add_argument('--verify', action='store_true', dest='verify_agents',
            help='verify agent integrity during install')
        install.add_argument('--no-verify', action='store_false', dest='verify_agents',
            help=argparse.SUPPRESS)
    install.set_defaults(func=install_agent, verify_agents=True)

    tag = add_parser('tag', parents=[filterable],
        help='set, show, or remove agent tag')
    tag.add_argument('agent', help='UUID or name of agent')
    group = tag.add_mutually_exclusive_group()
    group.add_argument('tag', nargs='?', const=None, help='tag to give agent')
    group.add_argument('-r', '--remove', action='store_true', help='remove tag')
    tag.set_defaults(func=tag_agent, tag=None, remove=False)

    remove = add_parser('remove', parents=[filterable],
        help='remove agent')
    remove.add_argument('pattern', nargs='+', help='UUID or name of agent')
    remove.add_argument('-f', '--force', action='store_true',
        help='force removal of multiple agents')
    remove.set_defaults(func=remove_agent, force=False)

    list_ = add_parser('list', parents=[filterable],
        help='list installed agent')
    list_.add_argument('pattern', nargs='*',
        help='UUID or name of agent')
    list_.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
        help='show at least N characters of UUID (0 to show all)')
    list_.set_defaults(func=list_agents, min_uuid_len=1)

    status = add_parser('status', parents=[filterable],
        help='show status of agents')
    status.add_argument('pattern', nargs='*',
        help='UUID or name of agent')
    status.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
        help='show at least N characters of UUID (0 to show all)')
    status.set_defaults(func=status_agents, min_uuid_len=1)

    clear = add_parser('clear', help='clear status of defunct agents')
    clear.add_argument('-a', '--all', dest='clear_all', action='store_true',
        help='clear the status of all agents')
    clear.set_defaults(func=clear_status, clear_all=False)

    enable = add_parser('enable', parents=[filterable],
        help='enable agent to start automatically')
    enable.add_argument('pattern', nargs='+', help='UUID or name of agent')
    enable.add_argument('-p', '--priority', type=priority,
        help='2-digit priority from 00 to 99')
    enable.set_defaults(func=enable_agent, priority='50')

    disable = add_parser('disable', parents=[filterable],
        help='prevent agent from start automatically')
    disable.add_argument('pattern', nargs='+', help='UUID or name of agent')
    disable.set_defaults(func=disable_agent)

    start = add_parser('start', parents=[filterable],
        help='start installed agent')
    start.add_argument('pattern', nargs='+', help='UUID or name of agent')
    if have_restricted:
        start.add_argument('--verify', action='store_true', dest='verify_agents',
            help='verify agent integrity during start')
        start.add_argument('--no-verify', action='store_false', dest='verify_agents',
            help=argparse.SUPPRESS)
    start.set_defaults(func=start_agent)

    stop = add_parser('stop', parents=[filterable],
        help='stop agent')
    stop.add_argument('pattern', nargs='+', help='UUID or name of agent')
    stop.set_defaults(func=stop_agent)

    run = add_parser('run',
        help='start any agent by path')
    run.add_argument('directory', nargs='+', help='path to agent directory')
    if have_restricted:
        run.add_argument('--verify', action='store_true', dest='verify_agents',
            help='verify agent integrity during run')
        run.add_argument('--no-verify', action='store_false', dest='verify_agents',
            help=argparse.SUPPRESS)
    run.set_defaults(func=run_agent)

    shutdown = add_parser('shutdown',
        help='stop all agents')
    shutdown.add_argument('--platform', action='store_true',
        help='also stop the platform process')
    shutdown.set_defaults(func=shutdown_agents, platform=False)

    if have_restricted:
        send = add_parser('send',
            help='send mobile agent to and start on a remote platform')
        send.add_argument('-p', '--port', type=int, metavar='NUMBER',
            help='alternate port number to connect to')
        send.add_argument('host', help='DNS name or IP address of host')
        send.add_argument('wheel', nargs='+',
            help='agent package to send')
        send.set_defaults(func=send_agent, port=2522)

        cgroup = add_parser('create-cgroups',
            help='setup VOLTTRON control group for restricted execution')
        cgroup.add_argument('-u', '--user', metavar='USER',
            help='owning user name or ID')
        cgroup.add_argument('-g', '--group', metavar='GROUP',
            help='owning group name or ID')
        cgroup.set_defaults(func=create_cgroups, user=None, group=None)

    args = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'SKIP_VOLTTRON_CONFIG' not in os.environ:
        args = ['--config', conf] + args
    opts = parser.parse_args(args)
    # Configure logging
    level = max(1, opts.verboseness)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(opts.log, level, handler_class=handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        logging.config.fileConfig(opts.log_config)

    opts.control_socket = config.expandall(opts.control_socket)
    opts.aip = aip.AIPplatform(opts)
    opts.aip.setup()

    try:
        return opts.func(opts)
    except RemoteError as exc:
        print_tb = exc.print_tb
        error = exc.message
    except Exception as exc:
        print_tb = traceback.print_exc
        error = str(exc)
    else:
        return 0
    if opts.debug:
        print_tb()
    _stderr.write('{}: error: {}\n'.format(opts.command, error))
    return 20


def _main():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == '__main__':
    _main()
