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
import grp
import os
import pwd
import re
import sys

from flexjsonrpc.core import RemoteError

from .. import aip
from .. import config
from .server import ControlConnector
from . import (CTL_STATUS,
               CTL_INSTALL,
               CTL_STATUS,
               CTL_START,
               CTL_STOP)

try:
    import volttron.restricted
except ImportError:
    have_restricted = False
else:
    import contextlib
    import errno
    import socket
    
    from paramiko import RSAKey, PasswordRequiredException, SSHException
    from paramiko.config import SSHConfig
    from paramiko.hostkeys import HostKeys
    from volttron.restricted import resmon
    from volttron.restricted.comms import CommsClient
    have_restricted = True


def search_agents(agents, queries):
    for query in queries:
        strings = re.split(r'([*?])', query)
        parts = ['^']
        if len(strings) == 1:
            parts.append(re.escape(query))
        else:
            parts.extend('.*' if s == '*' else
                         '.' if s == '?' else re.escape(s)
                         for s in strings)
            parts.append('$')
        regex = re.compile(''.join(parts))
        yield query, [uuid for uuid, name in agents.iteritems()
                      if regex.search(uuid) or regex.search(name)]

def install_agent(parser, opts):
    for wheel in opts.wheel:
        opts.aip.install_agent(wheel)

def remove_agent(parser, opts):
    agents = opts.aip.list_agents()
    for query, uuids in search_agents(agents, opts.agent):
        if not uuids:
            opts.stderr.write('{}: agent not found: {}\n'.format(
                    opts.command, query))
        elif len(uuids) > 1:
            if not opts.force:
                opts.stderr.write('{}: query returned multiple agents: {}\n'.format(
                        opts.command, query))
                continue
        for uuid in uuids:
            opts.stdout.write('Removing {} {}\n'.format(uuid, agents[uuid]))
            opts.aip.remove_agent(uuid)


def _calc_min_uuid_length(agents):
    n = 0
    for uuid1 in agents:
        for uuid2 in agents:
            if uuid1 == uuid2:
                continue
            common_len = len(os.path.commonprefix([uuid1, uuid2]))
            if common_len > n:
                n = common_len
    return n + 1

def list_agents(parser, opts):
    agents = opts.aip.list_agents()
    if not agents:
        return
    if opts.pattern:
        filtered = {}
        for query, uuids in search_agents(agents, opts.pattern):
            if not uuids:
                opts.stderr.write('{}: agent not found: {}\n'.format(
                        opts.command, query))
            for uuid in uuids:
                filtered[uuid] = agents[uuid]
        agents = filtered
    if not opts.min_uuid_len:
        n = None
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    agents = agents.items()
    agents.sort(key=lambda i: i[1])
    for uuid, name in agents:
        opts.stdout.writelines([uuid[:n], '  ', name, '\n'])

def status_agents(parser, opts):
    agents = ControlConnector(opts.control_socket).call.status_agents()
    if not agents:
        return
    agents.sort(key=lambda x: x[1])
    if not opts.min_uuid_len:
        n = 36
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    width = max(5, min(58-n, max(len(x[0]) for x in agents)))
    fmt = '{} {:{}} {:>3} {:>6}\n'
    opts.stderr.write(fmt.format(' '*n, 'AGENT', width, 'PRI', 'STATUS'))
    for uuid, name, priority, (pid, status) in agents:
        if priority is None:
            priority = ''
        opts.stdout.write(fmt.format(uuid[:n], name, width, priority,
            ('running [{}]'.format(pid) if status is None else str(status))
             if pid else ''))

def enable_agent(parser, opts):
    agents = opts.aip.list_agents()
    for query, uuids in search_agents(agents, opts.agent):
        if not uuids:
            opts.stderr.write('{}: agent not found: {}\n'.format(
                    opts.command, query))
        for uuid in uuids:
            opts.stdout.write('Enabling {} {} with priority {}\n'.format(
                    uuid, agents[uuid], opts.priority))
            opts.aip.enable_agent(uuid, opts.priority)

def disable_agent(parser, opts):
    agents = opts.aip.list_agents()
    for query, uuids in search_agents(agents, opts.agent):
        if not uuids:
            opts.stderr.write('{}: agent not found: {}\n'.format(
                    opts.command, query))
        for uuid in uuids:
            opts.stdout.write('Disabling {} {}\n'.format(uuid, agents[uuid]))
            opts.aip.disable_agent(uuid)

def start_agent(parser, opts):
    agents = opts.aip.list_agents()
    conn = ControlConnector(opts.control_socket)
    for query, uuids in search_agents(agents, opts.agent):
        if not uuids:
            opts.stderr.write('{}: agent not found: {}\n'.format(
                    opts.command, query))
        for uuid in uuids:
            opts.stdout.write('Starting {} {}\n'.format(uuid, agents[uuid]))
            conn.call.start_agent(uuid)

def stop_agent(parser, opts):
    agents = opts.aip.list_agents()
    conn = ControlConnector(opts.control_socket)
    for query, uuids in search_agents(agents, opts.agent):
        if not uuids:
            opts.stderr.write('{}: agent not found: {}\n'.format(
                    opts.command, query))
        for uuid in uuids:
            opts.stdout.write('Stopping {} {}\n'.format(uuid, agents[uuid]))
            conn.call.stop_agent(uuid)

def run_agent(parser, opts):
    for directory in opts.directory:
        ControlConnector(opts.control_socket).call.run_agent(directory)

def shutdown_agents(parser, opts):
    ControlConnector(opts.control_socket).call.shutdown()

def create_cgroups(parser, opts):
    user = opts.user
    group = opts.group
    if user is None:
        uid = os.getuid()
    else:
        try:
            uid = int(user)
        except ValueError:
            try:
                uid = pwd.getpwnam(user).pw_uid
            except KeyError:
                parser.error('unknown user: {}'.format(user))
    if group is None:
        gid = os.getgid()
    else:
        try:
            gid = int(group)
        except ValueError:
            try:
                gid = grp.getgrnam(group).gr_gid
            except KeyError:
                parser.error('unknown group: {}'.format(group))
    for name in resmon._cgroups_used:
        path = os.path.join(resmon._cgroups_root, name, 'volttron')
        if not os.path.exists(path):
            os.mkdir(path, 0775)
        os.chmod(path, 0775)
        os.chown(path, uid, gid)


def send_agent(parser, opts):
    ssh_dir = os.path.join(opts.volttron_home, 'ssh')
    ssh_config = SSHConfig()
    host_keys = HostKeys()
    try:
        try:
            ssh_config.parse(open(os.path.join(ssh_dir, 'config')))
        except IOError as exc:
            if exc.errno != errno.ENOENT:
                raise
        priv_key = RSAKey(filename=os.path.join(ssh_dir, 'id_rsa'))
        try:
            host_keys.load(os.path.join(ssh_dir, 'known_hosts'))
        except IOError as exc:
            if exc.errno != errno.ENOENT:
                raise
    except (OSError, IOError, PasswordRequiredException, SSHException) as exc:
        parser.error(exc)
    host = ssh_config.lookup(opts.host)
    hostname = host.get('hostname', opts.host)
    port = host.get('port', opts.port)
    address = hostname, port
    keys = host_keys.lookup(hostname)
    if not keys:
        host_key = None
    else:
        host_key = keys.get('ssh-rsa')
    if host_key is None:
        opts.stderr.write('warning: no public key found for remote host\n')
    with contextlib.closing(CommsClient(
            address, host_key, socket.gethostname(), priv_key)) as client:
        for wheel in opts.agent_wheel:
            with open(wheel) as file:
                client.send_and_start_agent(file)


def priority(value):
    n = int(value)
    if not 0 <= n < 100:
        raise ValueError('invalid priority (0 <= n < 100): {}'.format(n))
    return '{:02}'.format(n)


def main(argv=sys.argv):
    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]),
        description='Manage and control VOLTTRON agents.',
        usage='%(prog)s command [OPTIONS] ...',
    )

    parser.add_argument('--control-socket', metavar='FILE',
        help='path to socket used for control messages')

    subparsers = parser.add_subparsers(title='commands', metavar='', dest='command')

    install = subparsers.add_parser('install', help='install agent from wheel')
    install.add_argument('wheel', nargs='+', help='path to agent wheel')
    if have_restricted:
        install.add_argument('--verify', action='store_true', dest='verify_agents', 
            help='verify agent integrity during install')
        install.add_argument('--no-verify', action='store_false',
            dest='verify_agents', help=argparse.SUPPRESS)
    install.set_defaults(func=install_agent)

    remove = subparsers.add_parser('remove', help='remove agent')
    remove.add_argument('agent', nargs='+', help='UUID or name of agent')
    remove.add_argument('-f', '--force', action='store_true',
        help='force removal of multiple agents')
    remove.set_defaults(func=remove_agent)

    list_ = subparsers.add_parser('list', help='list installed agent')
    list_.add_argument('pattern', nargs='*', help='UUID or name of agent (w/ optional wildcards)')
    list_.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
        help='show at least N characters of UUID (0 to show all)')
    list_.set_defaults(func=list_agents, min_uuid_len=1)

    status = subparsers.add_parser(CTL_STATUS, help='show status of agents')
    status.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
        help='show at least N characters of UUID (0 to show all)')
    status.set_defaults(func=status_agents, min_uuid_len=1)

    enable = subparsers.add_parser('enable',
        help='enable agent to start automatically')
    enable.add_argument('agent', nargs='+', help='UUID or name of agent')
    enable.add_argument('-p', '--priority', type=priority,
        help='2-digit priority from 00 to 99')
    enable.set_defaults(func=enable_agent, priority='50')

    disable = subparsers.add_parser('disable',
        help='prevent agent from start automatically')
    disable.add_argument('agent', nargs='+', help='UUID or name of agent')
    disable.set_defaults(func=disable_agent)

    start = subparsers.add_parser('start',
        help='start installed agent')
    start.add_argument('agent', nargs='+', help='UUID or name of agent')
    start.set_defaults(func=start_agent)

    stop = subparsers.add_parser('stop',
        help='stop agent')
    stop.add_argument('agent', nargs='+', help='UUID or name of agent')
    stop.set_defaults(func=stop_agent)

    run = subparsers.add_parser('run',
        help='start any agent by path')
    run.add_argument('directory', nargs='+', help='path to agent directory')
    run.set_defaults(func=run_agent)

    shutdown = subparsers.add_parser('shutdown',
        help='stop all agents')
    shutdown.set_defaults(func=shutdown_agents)

    if have_restricted:
        send = subparsers.add_parser('send-agent',
            help='send mobile agent to and start on a remote platform')
        send.add_argument('-p', '--port', type=int, metavar='NUMBER',
            help='alternate port number to connect to')
        send.add_argument('host', help='DNS name or IP address of host')
        send.add_argument('agent_wheel', nargs='+',
            help='agent package to send')
        send.set_defaults(func=send_agent, port=2522)

        cgroup = subparsers.add_parser('create-cgroups',
            help='setup VOLTTRON control group for restricted execution')
        cgroup.add_argument('-u', '--user', metavar='USER',
            help='owning user name or ID')
        cgroup.add_argument('-g', '--group', metavar='GROUP',
            help='owning group name or ID')
        cgroup.set_defaults(func=create_cgroups, user=None, group=None)

    parser.set_defaults(**config.get_volttron_defaults())

    opts = parser.parse_args(argv[1:])
    expandall = lambda string: os.path.expanduser(os.path.expandvars(string))
    opts.volttron_home = expandall(os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = opts.volttron_home
    opts.control_socket = expandall(opts.control_socket)
    opts.aip = aip.AIPplatform(opts)
    opts.aip.setup()
    opts.stdout = sys.stdout
    opts.stderr = sys.stderr
    try:
        opts.func(parser, opts)
    except RemoteError as e:
        e.print_tb()


def _main():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == '__main__':
    _main()
