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
from pathlib import Path
import sys
import tempfile
import traceback
import uuid

import gevent
import yaml

from volttron.platform.vip.agent.results import AsyncResult
from volttron.platform import agent, config, jsonapi, get_home
from volttron.platform.agent.utils import execute_command
from volttron.platform.packaging import add_files_to_package, create_package

_log = logging.getLogger(__name__)

_stdout = sys.stdout
_stderr = sys.stderr





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


def install_agent_directory(opts, publickey=None, secretkey=None):
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

    assert opts.connection, "Connection must have been created to access this feature."

    # install_requirements(opts.install_path)

    wheelhouse = os.path.join(get_home(), "packaged")
    opts.package = create_package(opts.install_path, wheelhouse, opts.vip_identity)

    if not os.path.isfile(opts.package):
        _log.error("The wheel file for the agent was unable to be created.")
        sys.exit(-10)

    agent_uuid = None
    if not opts.vip_identity:
        agent_default_id_file = Path(opts.install_path).joinpath("IDENTITY")
        if agent_default_id_file.is_file():
            with open(str(agent_default_id_file)) as fin:
                opts.vip_identity = fin.read().strip()
    agent_uuid = None

    # Verify and load agent_config up from the opts.  agent_config will
    # be a yaml config file.
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

    _send_and_intialize_agent(opts, publickey, secretkey)
    

def _send_and_intialize_agent(opts, publickey, secretkey):
    
    agent_uuid = send_agent(opts, opts.package, opts.vip_identity,
                            publickey, secretkey, opts.force)

    if not agent_uuid:
        raise ValueError(f"Agent was not installed properly.")
    
    if isinstance(agent_uuid, AsyncResult):
        agent_uuid = agent_uuid.get()
    
    output_dict = dict(agent_uuid=agent_uuid)
    
    if opts.tag:
        _log.debug(f"Tagging agent {agent_uuid}, {opts.tag}")
        opts.connection.call('tag_agent', agent_uuid, opts.tag)
        output_dict['tag'] = opts.tag

    if opts.enable or opts.priority != -1:        
        output_dict['enabling'] = True
        if opts.priority == -1:
            opts.priority = '50'
        _log.debug(f"Prioritinzing agent {agent_uuid},{opts.priority}")
        output_dict['priority'] = opts.priority
        
        opts.connection.call('prioritize_agent', agent_uuid, str(opts.priority))

    
    try: 

        if opts.start:
            _log.debug(f"Staring agent {agent_uuid}")
            opts.connection.call('start_agent', agent_uuid)
            output_dict['starting'] = True
            
            _log.debug(f"Getting agent status {agent_uuid}")
            gevent.sleep(opts.agent_start_time)
            status = opts.connection.call('agent_status', agent_uuid)
            if status[0] is not None and status[1] is None:
                output_dict['started'] = True
                output_dict['pid'] = status[0]
            else:
                output_dict['started'] = False
            _log.debug(f"Status returned {status}")
    except Exception as e:
        _log.error(e)


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


def install_agent_vctl(opts, publickey=None, secretkey=None, callback=None):
    """
    The `install_agent_vctl` function is called from the volttron-ctl or vctl install
    sub-parser.
    """

    try:
        install_path = opts.install_path
    except AttributeError:
        install_path = opts.wheel

    if os.path.isdir(install_path):
        install_agent_directory(opts, publickey, secretkey)
        if opts.connection is not None:
            opts.connection.server.core.stop()
    else:
        opts.package = opts.install_path
        if not os.path.exists(opts.package):
            raise FileNotFoundError(f"Invalid file {opts.package}")
        _send_and_intialize_agent(opts, publickey, secretkey)
        
    # This is where we need to exit so the script doesn't continue after installation.
    sys.exit(0)


def _send_agent(connection, peer, path,
                vip_identity, publickey, secretkey, force):
    wheel = open(path, 'rb')
    _log.debug(f"Connecting to {peer} to install {path}")
    channel = connection.vip.channel(peer, 'agent_sender')

    def send():
        nonlocal wheel, channel
        sha512 = hashlib.sha512()
        try:
            # TODO: RMQ channel???
            # Note sending and receiving through a channel all communication
            # is binary for zmq (RMQ may be different for this functionality)
            #
            
            first = True
            op = None
            size = None
            while True:
                if first:
                    first = False
                    # Wait for peer to open compliment channel
                    resp = jsonapi.loadb(channel.recv())
                    _log.debug(f"Got first response {resp}")

                    if len(resp) > 1:
                        op, size = resp
                    else:
                        op = resp[0]
                    
                    if op != 'fetch':
                        raise ValueError(f'First channel response must be fetch but was {fetch}')

                if op == 'fetch':
                    chunk = wheel.read(size)
                    if chunk:
                        _log.debug(f"Op was fetch sending {size}")
                        sha512.update(chunk)
                        channel.send(chunk)
                    else:
                        _log.debug(f"Op was fetch sending complete")
                        channel.send(b'complete')
                        gevent.sleep(10)
                        break
                elif op == 'checksum':
                    _log.debug(f"sending checksum {sha512.hexdigest()}")
                    channel.send(sha512.digest())

                _log.debug("Waiting for next response")
                # wait for next response
                resp = jsonapi.loadb(channel.recv())

                if len(resp) > 1:
                    op, size = resp
                else:
                    op = resp[0]

        finally:
            _log.debug("Closing wheel and channel.")
            wheel.close()
            channel.close(linger=0)
            del channel

    _log.debug(f"calling install_agent on {peer} using channel {channel.name}")
    result = connection.vip.rpc.call(
        peer, 'install_agent', os.path.basename(path), channel.name,
        vip_identity, publickey, secretkey, force)
    
    task = gevent.spawn(send)
    result.rawlink(lambda glt: task.kill(block=False))
    _log.debug("Completed sending of agent across.")
    gevent.wait([result])
    _log.debug(f"After wait result is {result}")
    return result


def send_agent(opts, wheel_file, vip_identity, publickey, secretkey, force):
    connection = opts.connection
    #for wheel in opts.wheel:
    #uuid = _send_agent(connection.server, connection.peer, wheel_file).get()
    result = _send_agent(connection.server, connection.peer, wheel_file,
                         vip_identity, publickey, secretkey, force)

    _log.debug(f"Returning {result} from send_agent")
    return result
    

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
    install.set_defaults(func=install_agent_vctl, verify_agents=True)
