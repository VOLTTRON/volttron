# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import argparse
import hashlib
import logging
import os
import sys
import tempfile
import traceback
import uuid

import gevent
import yaml

from volttron.platform import config, jsonapi, get_volttron_root, get_home
from volttron.platform.agent.utils import execute_command
from volttron.platform.packaging import add_files_to_package, create_package

_log = logging.getLogger(__name__)

_stdout = sys.stdout
_stderr = sys.stderr


def identity_exists(volttron_control, identity):
    env = os.environ.copy()
    cmds = [volttron_control, "status"]

    data = execute_command(cmds, env=env, logger=_log,
                           err_prefix="Error checking identity")
    for x in data.split("\n"):
        if x:
            line_split = x.split()
            if identity == line_split[2]:
                return line_split[0]
    return False


def install_requirements(agent_source):
    req_file = os.path.join(agent_source, "requirements.txt")

    if os.path.exists(req_file):
        _log.info(f"Installing requirements for agent from {req_file}.")
        cmds = ["pip", "install", "-r", req_file]
        try:
            execute_command(cmds, logger=_log,
                            err_prefix="Error installing requirements")
        except RuntimeError:
            sys.exit(1)


def install_agent_directory(opts):
    """
    The main installation method for installing the agent on the correct local
    platform instance.
    :param opts:
    :param package:
    :param agent_config:
    :return:
    """
    if not os.path.isfile(os.path.join(opts.install_path, "setup.py")):
        _log.error("Agent source must contain a setup.py file.")
        sys.exit(-10)

    install_requirements(opts.install_path)

    wheelhouse = os.path.join(get_home(), "packaged")
    opts.package = create_package(opts.install_path, wheelhouse, opts.vip_identity)

    if not os.path.isfile(opts.package):
        _log.error("The wheel file for the agent was unable to be created.")
        sys.exit(-10)

    agent_exists = False
    volttron_control = os.path.join(get_volttron_root(), "env/bin/vctl")
    if opts.vip_identity is not None:
        # if the identity exists the variable will have the agent uuid in it.
        agent_exists = identity_exists(volttron_control, opts.vip_identity)
        if agent_exists:
            if not opts.force:
                _log.error(
                    "identity already exists, but force wasn't specified.")
                sys.exit(-10)
            # Note we don't remove the agent here because if we do that will
            # not allow us to update without losing the keys.  The
            # install_agent method either installs or upgrades the agent.
    agent_config = opts.agent_config

    if agent_config is None:
        agent_config = {}

    # if not a dict then config should be a filename
    if not isinstance(agent_config, dict):
        config_file = agent_config
    else:
        cfg = tempfile.NamedTemporaryFile()
        with open(cfg.name, 'w') as fout:
            fout.write(yaml.safe_dump(agent_config))
        config_file = cfg.name

    try:
        with open(config_file) as fp:
            data = yaml.safe_load(fp)
    except:
        _log.error("Invalid yaml/json config file.")
        sys.exit(-10)

    # Configure the whl file before installing.
    add_files_to_package(opts.package, {'config_file': config_file})
    env = os.environ.copy()


    if agent_exists:
        cmds = [volttron_control, "--json", "upgrade", opts.vip_identity, opts.package]
    else:
        cmds = [volttron_control, "--json", "install", opts.package]

    if opts.tag:
        cmds.extend(["--tag", opts.tag])

    out = execute_command(cmds, env=env, logger=_log,
                          err_prefix="Error installing agent")

    parsed = out.split("\n")

    # If there is not an agent with that identity:
    # 'Could not find agent with VIP IDENTITY "BOO". Installing as new agent
    # Installed /home/volttron/.volttron/packaged/listeneragent-3.2-py2-none-any.whl as 6ccbf8dc-4929-4794-9c8e-3d8c6a121776 listeneragent-3.2'

    # The following is standard output of an agent that was previously installed
    # If the agent was not previously installed then only the second line
    # would have been output to standard out.
    #
    # Removing previous version of agent "foo"
    # Installed /home/volttron/.volttron/packaged/listeneragent-3.2-py2-none-any.whl as 81b811ff-02b5-482e-af01-63d2fd95195a listeneragent-3.2

    agent_uuid = None
    for l in parsed:
        if l.startswith('Installed'):
            agent_uuid = l.split(' ')[-2:-1][0]
    # if 'Could not' in parsed[0]:
    #     agent_uuid = parsed[1].split()[-2]
    # elif 'Removing' in parsed[0]:
    #     agent_uuid = parsed[1].split()[-2]
    # else:
    #     agent_uuid = parsed[0].split()[-2]

    output_dict = dict(agent_uuid=agent_uuid)

    if opts.start:
        cmds = [volttron_control, "start", agent_uuid]
        outputdata = execute_command(cmds, env=env, logger=_log,
                                     err_prefix="Error starting agent")

        # Expected output on standard out
        # Starting 83856b74-76dc-4bd9-8480-f62bd508aa9c listeneragent-3.2
        if 'Starting' in outputdata:
            output_dict['starting'] = True

    if opts.enable:
        cmds = [volttron_control, "enable", agent_uuid]

        if opts.priority != -1:
            cmds.extend(["--priority", str(opts.priority)])

        outputdata = execute_command(cmds, env=env, logger=_log,
                                     err_prefix="Error enabling agent")
        # Expected output from standard out
        # Enabling 6bcee29b-7af3-4361-a67f-7d3c9e986419 listeneragent-3.2 with priority 50
        if "Enabling" in outputdata:
            output_dict['enabling'] = True
            output_dict['priority'] = outputdata.split("\n")[0].split()[-1]

    if opts.start:
        # Pause for agent_start_time seconds before verifying that the agent
        gevent.sleep(opts.agent_start_time)

        cmds = [volttron_control, "status", agent_uuid]
        outputdata = execute_command(cmds, env=env, logger=_log,
                                     err_prefix="Error finding agent status")

        # 5 listeneragent-3.2 foo     running [10737]
        output_dict["started"] = "running" in outputdata
        if output_dict["started"]:
            pidpos = outputdata.index('[') + 1
            pidend = outputdata.index(']')
            output_dict['agent_pid'] = int(outputdata[pidpos: pidend])

    if opts.json:
        sys.stdout.write("%s\n" % jsonapi.dumps(output_dict, indent=4))
    if opts.csv:
        keylen = len(output_dict)
        keyline = ''
        valueline = ''
        keys = list(output_dict.keys())
        for k in range(keylen):
            if k < keylen - 1:
                keyline += "%s," % keys[k]
                valueline += "%s," % output_dict[keys[k]]
            else:
                keyline += "%s" % keys[k]
                valueline += "%s" % output_dict[keys[k]]
        sys.stdout.write("%s\n%s\n" % (keyline, valueline))


def install_agent(opts, publickey=None, secretkey=None, callback=None):
    try:
        install_path = opts.install_path
    except AttributeError:
        install_path = opts.wheel

    if os.path.isdir(install_path):
        install_agent_directory(opts)
        if opts.connection is not None:
            opts.connection.server.core.stop()
        sys.exit(0)
    filename = install_path
    tag = opts.tag
    vip_identity = opts.vip_identity
    if opts.vip_address.startswith('ipc://'):
        _log.info("Installing wheel locally without channel subsystem")
        filename = config.expandall(filename)
        agent_uuid = opts.connection.call('install_agent_local',
                                          filename,
                                          vip_identity=vip_identity,
                                          publickey=publickey,
                                          secretkey=secretkey)

        if tag:
            opts.connection.call('tag_agent', agent_uuid, tag)

    else:
        channel = None
        try:
            _log.debug('Creating channel for sending the agent.')
            channel_name = str(uuid.uuid4())
            channel = opts.connection.server.vip.channel('control',
                                                         channel_name)
            _log.debug('calling control install agent.')
            agent_uuid = opts.connection.call_no_get('install_agent',
                                                     filename,
                                                     channel_name,
                                                     vip_identity=vip_identity,
                                                     publickey=publickey,
                                                     secretkey=secretkey)

            _log.debug('Sending wheel to control')
            sha512 = hashlib.sha512()
            with open(filename, 'rb') as wheel_file_data:
                while True:
                    # get a request
                    with gevent.Timeout(60):
                        request, file_offset, chunk_size = channel.recv_multipart()
                    if request == b'checksum':
                        channel.send(sha512.digest())
                        break

                    assert request == b'fetch'

                    # send a chunk of the file
                    file_offset = int(file_offset)
                    chunk_size = int(chunk_size)
                    wheel_file_data.seek(file_offset)
                    data = wheel_file_data.read(chunk_size)
                    sha512.update(data)
                    channel.send(data)

            agent_uuid = agent_uuid.get(timeout=10)

        except Exception as exc:
            if opts.debug:
                traceback.print_exc()
            _stderr.write(
                '{}: error: {}: {}\n'.format(opts.command, exc, filename))
            return 10
        else:
            if tag:
                opts.connection.call('tag_agent',
                                     agent_uuid,
                                     tag)
        finally:
            _log.debug('closing channel')
            if channel:
                channel.close(linger=0)
                del channel

    name = opts.connection.call('agent_name', agent_uuid)
    _stdout.write('Installed {} as {} {}\n'.format(filename, agent_uuid, name))

    opts.connection.server.core.stop()

    # This is where we need to exit so the script doesn't continue after installation.
    sys.exit(0)


def add_install_agent_parser(add_parser_fn, has_restricted):
    install = add_parser_fn('install', help='install agent from wheel',
                            epilog='Optionally you may specify the --tag argument to tag the '
                                   'agent during install without requiring a separate call to '
                                   'the tag command. ')
    install.add_argument('install_path', help='path to agent wheel or directory for agent installation')
    install.add_argument('--tag', help='tag for the installed agent')
    install.add_argument('--vip-identity', help='VIP IDENTITY for the installed agent. '
                                                'Overrides any previously configured VIP IDENTITY.')
    install.add_argument('--agent-config', help="Agent configuration!")
    install.add_argument("-f", "--force", action='store_true',
                         help="agents are uninstalled by tag so force allows multiple agents to be removed at one go.")
    install.add_argument("--priority", default=-1, type=int,
                         help="priority of startup during instance startup")
    install.add_argument("--start", action='store_true',
                         help="start the agent during the script execution")
    install.add_argument("--enable", action='store_true',
                         help="enable the agent with default 50 priority unless --priority set")
    install.add_argument("--csv", action='store_true',
                         help="format the standard out output to csv")
    install.add_argument("--json", action="store_true",
                         help="format the standard out output to json")
    install.add_argument("-st", "--agent-start-time", default=5, type=int,
                         help="the amount of time to wait and verify that the agent has started up.")
    if has_restricted:
        install.add_argument('--verify', action='store_true',
                             dest='verify_agents',
                             help='verify agent integrity during install')
        install.add_argument('--no-verify', action='store_false',
                             dest='verify_agents',
                             help=argparse.SUPPRESS)
    install.set_defaults(func=install_agent, verify_agents=True)
