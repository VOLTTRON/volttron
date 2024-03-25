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

# Monkeypatch for gevent
from volttron.utils import monkey_patch

monkey_patch()

import argparse
import collections
import logging
import logging.config
import logging.handlers
import os
import sys
from datetime import datetime, timedelta

import gevent
import gevent.event

from volttron.platform import aip as aipmod
from volttron.platform import config, get_address, get_home, is_rabbitmq_available, jsonapi
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import PLATFORM_HEALTH
from volttron.platform.agent.utils import is_secure_mode, wait_for_volttron_shutdown
from volttron.platform.control.control_auth import add_auth_parser
from volttron.platform.control.control_certs import add_certs_parser
from volttron.platform.control.control_config import add_config_store_parser
from volttron.platform.control.control_connection import ControlConnection
from volttron.platform.control.control_rmq import add_rabbitmq_parser
from volttron.platform.control.control_rpc import add_rpc_agent_parser
from volttron.platform.control.control_utils import (
    _list_agents, _show_filtered_agents, _show_filtered_agents_status,
    filter_agent, filter_agents, get_filtered_agents)
from volttron.platform.control.install_agents import InstallRuntimeError, add_install_agent_parser
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.vip.agent.errors import Unreachable, VIPError

# noinspection PyUnresolvedReferences

if is_rabbitmq_available():
    from volttron.utils.rmq_config_params import RMQConfig
    from volttron.utils.rmq_setup import check_rabbit_status

try:
    import volttron.restricted
except ImportError:
    HAVE_RESTRICTED = False
else:
    from volttron.restricted import cgroups

    HAVE_RESTRICTED = True

_stdout = sys.stdout
_stderr = sys.stderr

# will be volttron.platform.main or main.py instead of __main__
_log = logging.getLogger(
    os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__)
# Allows server side logging.
# _log.setLevel(logging.DEBUG)

message_bus = utils.get_messagebus()
rmq_mgmt = None

CHUNK_SIZE = 4096


def log_to_file(file,
                level=logging.WARNING,
                handler_class=logging.StreamHandler):
    """Direct log output to a file (or something like one)."""
    handler = handler_class(file)
    handler.setLevel(level)
    handler.setFormatter(
        utils.AgentFormatter(
            "%(asctime)s %(composite_name)s %(levelname)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


Agent = collections.namedtuple("Agent",
                               "name tag uuid vip_identity agent_user")


# TODO: Remove AIP
def tag_agent(opts):
    agents = filter_agent(_list_agents(opts.aip), opts.agent, opts)
    if len(agents) != 1:
        if agents:
            msg = "multiple agents selected"
        else:
            msg = "agent not found"
        _stderr.write("{}: error: {}: {}\n".format(opts.command, msg,
                                                   opts.agent))
        return 10
    (agent, ) = agents
    if opts.tag:
        _stdout.write("Tagging {} {}\n".format(agent.uuid, agent.name))
        opts.aip.tag_agent(agent.uuid, opts.tag)
    elif opts.remove:
        if agent.tag is not None:
            _stdout.write("Removing tag for {} {}\n".format(
                agent.uuid, agent.name))
            opts.aip.tag_agent(agent.uuid, None)
    else:
        if agent.tag is not None:
            _stdout.writelines([agent.tag, "\n"])


def remove_agent(opts, remove_auth=True):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write("{}: error: agent not found: {}\n".format(
                opts.command, pattern))
        elif len(match) > 1 and not opts.force:
            _stderr.write(
                "{}: error: pattern returned multiple agents: {}\n".format(
                    opts.command, pattern))
            _stderr.write(
                "Use -f or --force to force removal of multiple agents.\n")
            return 10
        for agent in match:
            _stdout.write("Removing {} {}\n".format(agent.uuid, agent.name))
            opts.connection.call("remove_agent",
                                 agent.uuid,
                                 remove_auth=remove_auth)


# TODO: Remove AIP
def list_agents(opts):

    def get_priority(agent):
        return opts.aip.agent_priority(agent.uuid) or ""

    _show_filtered_agents(opts, "PRI", get_priority)


def list_peers(opts):
    conn = opts.connection
    peers = sorted(conn.call("peerlist"))
    for peer in peers:
        sys.stdout.write("{}\n".format(peer))


# the following global variables are used to update the cache so
# that we don't ask the platform too many times for the data
# associated with health.
health_cache_timeout_date = None
health_cache_timeout = 5
health_cache = {}


def update_health_cache(opts):
    global health_cache_timeout_date

    t_now = datetime.now()
    do_update = True
    # Make sure we update if we don't have any health dicts, or if the cache
    # has timed out.
    if (health_cache_timeout_date is not None
            and t_now < health_cache_timeout_date and health_cache):
        do_update = False

    if do_update:
        health_cache.clear()
        if opts.connection.server:
            health_cache.update(
                opts.connection.server.vip.rpc.call(
                    PLATFORM_HEALTH, "get_platform_health").get(timeout=4))
            health_cache_timeout_date = datetime.now() + timedelta(
                seconds=health_cache_timeout)


# TODO: Remove AIP
def status_agents(opts):
    agents = {}
    for agent in _list_agents(opts.aip):
        agents[agent.uuid] = agent
    # agents = {agent.uuid: agent for agent in _list_agents(opts.aip)}
    status = {}
    for details in opts.connection.call("status_agents", get_agent_user=True):
        if is_secure_mode():
            (uuid, name, agent_user, stat, identity) = details
        else:
            (uuid, name, stat, identity) = details
            agent_user = ""
        try:
            agent = agents[uuid]
            agents[uuid] = agent._replace(agent_user=agent_user)
        except KeyError:
            Agent = collections.namedtuple(
                "Agent", "name tag uuid vip_identity "
                "agent_user")
            agents[uuid] = agent = Agent(name,
                                         None,
                                         uuid,
                                         vip_identity=identity,
                                         agent_user=agent_user)
        status[uuid] = stat
    agents = list(agents.values())

    def get_status(agent):
        try:
            pid, stat = status[agent.uuid]
        except KeyError:
            pid = stat = None

        if stat is not None:
            return str(stat)
        if pid:
            return "running [{}]".format(pid)
        return ""

    def get_health(agent):
        update_health_cache(opts)

        try:
            health_dict = health_cache.get(agent.vip_identity)

            if health_dict:
                if opts.json:
                    return health_dict
                else:
                    return health_dict.get("message", "")
            else:
                return ""
        except (VIPError, gevent.Timeout):
            return ""

    _show_filtered_agents_status(opts, get_status, get_health, agents)


#TODO: Remove AIP
def agent_health(opts):
    agents = {agent.uuid: agent for agent in _list_agents(opts.aip)}.values()
    agents = get_filtered_agents(opts, agents)
    if not agents:
        if not opts.json:
            _stderr.write("No installed Agents found\n")
        else:
            _stdout.write(f"{jsonapi.dumps({}, indent=2)}\n")
        return
    agent = agents.pop()
    update_health_cache(opts)

    data = health_cache.get(agent.vip_identity)

    if not data:
        if not opts.json:
            _stdout.write(f"No health associated with {agent.vip_identity}\n")
        else:
            _stdout.write(f"{jsonapi.dumps({}, indent=2)}\n")
    else:
        _stdout.write(f"{jsonapi.dumps(data, indent=4)}\n")


def clear_status(opts):
    opts.connection.call("clear_status", opts.clear_all)


# TODO: Remove AIP
def enable_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write("{}: error: agent not found: {}\n".format(
                opts.command, pattern))
        for agent in match:
            _stdout.write("Enabling {} {} with priority {}\n".format(
                agent.uuid, agent.name, opts.priority))
            opts.aip.prioritize_agent(agent.uuid, opts.priority)


def disable_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write("{}: error: agent not found: {}\n".format(
                opts.command, pattern))
        for agent in match:
            priority = opts.aip.agent_priority(agent.uuid)
            if priority is not None:
                _stdout.write("Disabling {} {}\n".format(
                    agent.uuid, agent.name))
                opts.aip.prioritize_agent(agent.uuid, None)


def start_agent(opts):
    act_on_agent("start_agent", opts)


def stop_agent(opts):
    act_on_agent("stop_agent", opts)


def restart_agent(opts):
    stop_agent(opts)
    start_agent(opts)


def act_on_agent(action, opts):
    call = opts.connection.call
    agents = _list_agents(opts.aip)
    pattern_to_use = opts.pattern

    if not opts.by_all_tagged and not opts.pattern:
        raise ValueError("Missing search pattern.")

    if opts.by_all_tagged and not agents:
        return

    # when all-tagged option is used, prefilter agents that are tagged and set search pattern to *
    if opts.by_all_tagged and not opts.pattern:
        agents, pattern_to_use = [a for a in agents if a.tag is not None], '*'

    # filter agents and update regex pattern
    for pattern, filtered_agents in filter_agents(agents, pattern_to_use,
                                                  opts):
        if not filtered_agents:
            _stderr.write(
                f"Agents NOT found using 'vctl {opts.command}' on pattern: {pattern}\n"
            )
        for agent in filtered_agents:
            pid, status = call("agent_status", agent.uuid)
            _call_action_on_agent(agent, pid, status, call, action)


def _call_action_on_agent(agent, pid, status, call, action):
    if action == "start_agent":
        if pid is None or status is not None:
            _stdout.write(f"Starting {agent.uuid} {agent.name}\n")
            call(action, agent.uuid)
            return

    if action == "stop_agent":
        if pid and status is None:
            _stdout.write(f"Stopping {agent.uuid} {agent.name}\n")
            call(action, agent.uuid)
            return


def run_agent(opts):
    call = opts.connection.call
    for directory in opts.directory:
        call("run_agent", directory)


def shutdown_agents(opts):
    if "rmq" == utils.get_messagebus():
        if not check_rabbit_status():
            rmq_cfg = RMQConfig()
            wait_period = (rmq_cfg.reconnect_delay()
                           if rmq_cfg.reconnect_delay() < 60 else 60)
            _stderr.write(
                "RabbitMQ server is not running.\n"
                "Waiting for {} seconds for possible reconnection and to "
                "perform normal shutdown\n".format(wait_period))
            gevent.sleep(wait_period)
            if not check_rabbit_status():
                _stderr.write(
                    "RabbitMQ server is still not running.\nShutting down "
                    "the platform forcefully\n")
                opts.aip.brute_force_platform_shutdown()
                return
    opts.connection.call("shutdown")
    _log.debug("Calling stop_platform")
    if opts.platform:
        opts.connection.notify("stop_platform")
        wait_for_volttron_shutdown(get_home(), 60)


def create_cgroups(opts):
    try:
        cgroups.setup(user=opts.user, group=opts.group)
    except ValueError as exc:
        _stderr.write("{}: error: {}\n".format(opts.command, exc))
        return os.EX_NOUSER


def _send_agent(connection, peer, path):
    wheel = open(path, "rb")
    channel = connection.vip.channel(peer)

    def send():
        try:
            # Wait for peer to open compliment channel
            channel.recv()
            while True:
                data = wheel.read(8192)
                channel.send(data)
                if not data:
                    break
            # Wait for peer to signal all data received
            channel.recv()
        finally:
            wheel.close()
            channel.close(linger=0)

    result = connection.vip.rpc.call(peer, "install_agent",
                                     os.path.basename(path), channel.name)
    task = gevent.spawn(send)
    result.rawlink(lambda glt: task.kill(block=False))
    _log.debug(f"Result is {result}")
    return result


def send_agent(opts):
    connection = opts.connection
    for wheel in opts.wheel:
        uuid = _send_agent(connection.server, connection.peer, wheel).get()
        return uuid


def do_stats(opts):
    call = opts.connection.call
    if opts.op == "status":
        _stdout.write("%sabled\n" % ("en" if call("stats.enabled") else "dis"))
    elif opts.op in ["dump", "pprint"]:
        stats = call("stats.get")
        if opts.op == "pprint":
            import pprint

            pprint.pprint(stats, _stdout)
        else:
            _stdout.writelines([str(stats), "\n"])
    else:
        call("stats." + opts.op)
        _stdout.write("%sabled\n" % ("en" if call("stats.enabled") else "dis"))


def priority(value):
    n = int(value)
    if not 0 <= n < 100:
        raise ValueError("invalid priority (0 <= n < 100): {}".format(n))
    return "{:02}".format(n)


def get_keys(opts):
    """Gets keys from keystore and known-hosts store"""
    hosts = KnownHostsStore()
    serverkey = hosts.serverkey(opts.vip_address)
    key_store = KeyStore()
    publickey = key_store.public
    secretkey = key_store.secret
    return {
        "publickey": publickey,
        "secretkey": secretkey,
        "serverkey": serverkey
    }


def main():
    # Refuse to run as root
    if not getattr(os, "getuid", lambda: -1)():
        sys.stderr.write("%s: error: refusing to run as root to prevent "
                         "potential damage.\n" % os.path.basename(sys.argv[0]))
        sys.exit(77)

    volttron_home = get_home()

    os.environ["VOLTTRON_HOME"] = volttron_home

    global_args = config.ArgumentParser(description="global options",
                                        add_help=False)
    global_args.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        action="parse_config",
        ignore_unknown=True,
        sections=[None, "global", "volttron-ctl"],
        help="read configuration from FILE",
    )
    global_args.add_argument(
        "--debug",
        action="store_true",
        help="show tracebacks for errors rather than a brief message",
    )
    global_args.add_argument(
        "-t",
        "--timeout",
        type=float,
        metavar="SECS",
        help="timeout in seconds for remote calls (default: %(default)g)",
    )
    global_args.add_argument(
        "--msgdebug", help="route all messages to an agent while debugging")
    global_args.add_argument(
        "--vip-address",
        metavar="ZMQADDR",
        help="ZeroMQ URL to bind for VIP connections",
    )

    global_args.set_defaults(
        vip_address=get_address(),
        timeout=60,
    )

    filterable = config.ArgumentParser(add_help=False)
    filterable.add_argument(
        "--name",
        dest="by_name",
        action="store_true",
        help="filter/search by agent name",
    )
    filterable.add_argument("--tag",
                            dest="by_tag",
                            action="store_true",
                            help="filter/search by tag name")
    filterable.add_argument("--all-tagged",
                            dest="by_all_tagged",
                            action="store_true",
                            help="filter/search by all tagged agents")
    filterable.add_argument(
        "--uuid",
        dest="by_uuid",
        action="store_true",
        help="filter/search by UUID (default)",
    )
    filterable.set_defaults(by_name=False,
                            by_tag=False,
                            by_all_tagged=False,
                            by_uuid=False)

    parser = config.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        add_help=False,
        description="Manage and control VOLTTRON agents.",
        usage="%(prog)s command [OPTIONS] ...",
        argument_default=argparse.SUPPRESS,
        parents=[global_args],
    )
    parser.add_argument(
        "-l",
        "--log",
        metavar="FILE",
        default=None,
        help="send log output to FILE instead of stderr",
    )
    parser.add_argument(
        "-L",
        "--log-config",
        metavar="FILE",
        help="read logging configuration from FILE",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="add_const",
        const=10,
        dest="verboseness",
        help="decrease logger verboseness; may be used multiple times",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="add_const",
        const=-10,
        dest="verboseness",
        help="increase logger verboseness; may be used multiple times",
    )
    parser.add_argument(
        "--verboseness",
        type=int,
        metavar="LEVEL",
        default=logging.WARNING,
        help="set logger verboseness",
    )
    parser.add_argument("--show-config",
                        action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--json",
                        action="store_true",
                        default=False,
                        help="format output to json")

    parser.add_help_argument()
    parser.set_defaults(
        log_config=None,
        volttron_home=volttron_home,
    )

    top_level_subparsers = parser.add_subparsers(title="commands",
                                                 metavar="",
                                                 dest="command")

    def add_parser(*args, **kwargs) -> argparse.ArgumentParser:
        parents = kwargs.get("parents", [])
        parents.append(global_args)
        kwargs["parents"] = parents
        subparser = kwargs.pop("subparser", top_level_subparsers)
        return subparser.add_parser(*args, **kwargs)

    # ====================================================
    # install agent parser
    # ====================================================
    add_install_agent_parser(add_parser, HAVE_RESTRICTED)

    tag = add_parser("tag",
                     parents=[filterable],
                     help="set, show, or remove agent tag")
    tag.add_argument("agent", help="UUID or name of agent")
    group = tag.add_mutually_exclusive_group()
    group.add_argument("tag", nargs="?", const=None, help="tag to give agent")
    group.add_argument("-r",
                       "--remove",
                       action="store_true",
                       help="remove tag")
    tag.set_defaults(func=tag_agent, tag=None, remove=False)

    remove = add_parser("remove", parents=[filterable], help="remove agent")
    remove.add_argument("pattern", nargs="+", help="UUID or name of agent")
    remove.add_argument("-f",
                        "--force",
                        action="store_true",
                        help="force removal of multiple agents")
    remove.set_defaults(func=remove_agent, force=False)

    peers = add_parser("peerlist",
                       help="list the peers connected to the platform")
    peers.set_defaults(func=list_peers)

    list_ = add_parser("list",
                       parents=[filterable],
                       help="list installed agent")
    list_.add_argument("pattern", nargs="*", help="UUID or name of agent")
    list_.add_argument(
        "-n",
        dest="min_uuid_len",
        type=int,
        metavar="N",
        help="show at least N characters of UUID (0 to show all)",
    )
    list_.set_defaults(func=list_agents, min_uuid_len=1)

    status = add_parser("status",
                        parents=[filterable],
                        help="show status of agents")
    status.add_argument("pattern", nargs="*", help="UUID or name of agent")
    status.add_argument(
        "-n",
        dest="min_uuid_len",
        type=int,
        metavar="N",
        help="show at least N characters of UUID (0 to show all)",
    )
    status.set_defaults(func=status_agents, min_uuid_len=1)

    health = add_parser("health",
                        parents=[filterable],
                        help="show agent health as JSON")
    health.add_argument("pattern", nargs=1, help="UUID or name of agent")
    health.set_defaults(func=agent_health, min_uuid_len=1)

    clear = add_parser("clear", help="clear status of defunct agents")
    clear.add_argument(
        "-a",
        "--all",
        dest="clear_all",
        action="store_true",
        help="clear the status of all agents",
    )
    clear.set_defaults(func=clear_status, clear_all=False)

    enable = add_parser("enable",
                        parents=[filterable],
                        help="enable agent to start automatically")
    enable.add_argument("pattern", nargs="+", help="UUID or name of agent")
    enable.add_argument("-p",
                        "--priority",
                        type=priority,
                        help="2-digit priority from 00 to 99")
    enable.set_defaults(func=enable_agent, priority="50")

    disable = add_parser("disable",
                         parents=[filterable],
                         help="prevent agent from start automatically")
    disable.add_argument("pattern", nargs="+", help="UUID or name of agent")
    disable.set_defaults(func=disable_agent)

    start = add_parser("start",
                       parents=[filterable],
                       help="start installed agent")
    start.add_argument("pattern",
                       nargs="*",
                       help="UUID or name of agent",
                       default='')
    if HAVE_RESTRICTED:
        start.add_argument(
            "--verify",
            action="store_true",
            dest="verify_agents",
            help="verify agent integrity during start",
        )
        start.add_argument(
            "--no-verify",
            action="store_false",
            dest="verify_agents",
            help=argparse.SUPPRESS,
        )
    start.set_defaults(func=start_agent)

    stop = add_parser("stop", parents=[filterable], help="stop agent")
    stop.add_argument("pattern",
                      nargs="*",
                      help="UUID or name of agent",
                      default='')
    stop.set_defaults(func=stop_agent)

    restart = add_parser("restart", parents=[filterable], help="restart agent")
    restart.add_argument("pattern",
                         nargs="*",
                         help="UUID or name of agent",
                         default='')
    restart.set_defaults(func=restart_agent)

    run = add_parser("run", help="start any agent by path")
    run.add_argument("directory", nargs="+", help="path to agent directory")
    if HAVE_RESTRICTED:
        run.add_argument(
            "--verify",
            action="store_true",
            dest="verify_agents",
            help="verify agent integrity during run",
        )
        run.add_argument(
            "--no-verify",
            action="store_false",
            dest="verify_agents",
            help=argparse.SUPPRESS,
        )
    run.set_defaults(func=run_agent)

    # ====================================================
    # rpc commands
    # ====================================================
    add_rpc_agent_parser(add_parser)

    # ====================================================
    # certs commands
    # ====================================================
    add_certs_parser(add_parser)

    # ====================================================
    # auth commands
    # ====================================================
    add_auth_parser(add_parser, filterable)

    # ====================================================
    # config commands
    # ====================================================
    add_config_store_parser(add_parser)

    shutdown = add_parser("shutdown", help="stop all agents")
    shutdown.add_argument("--platform",
                          action="store_true",
                          help="also stop the platform process")
    shutdown.set_defaults(func=shutdown_agents, platform=False)

    send = add_parser("send", help="send agent and start on a remote platform")
    send.add_argument("wheel", nargs="+", help="agent package to send")
    send.set_defaults(func=send_agent)

    stats = add_parser("stats",
                       help="manage router message statistics tracking")
    op = stats.add_argument(
        "op",
        choices=["status", "enable", "disable", "dump", "pprint"],
        nargs="?")
    stats.set_defaults(func=do_stats, op="status")

    # ==============================================================================
    global message_bus, rmq_mgmt

    if message_bus == "rmq":
        # ====================================================
        # rabbitmq commands
        # ====================================================
        add_rabbitmq_parser(add_parser)

    # ===============================================================================================
    if HAVE_RESTRICTED:
        cgroup = add_parser(
            "create-cgroups",
            help="setup VOLTTRON control group for restricted execution",
        )
        cgroup.add_argument("-u",
                            "--user",
                            metavar="USER",
                            help="owning user name or ID")
        cgroup.add_argument("-g",
                            "--group",
                            metavar="GROUP",
                            help="owning group name or ID")
        cgroup.set_defaults(func=create_cgroups, user=None, group=None)

    # Parse and expand options
    args = sys.argv[1:]

    # TODO: for auth some of the commands will work when volttron is down and
    # some will error (example vctl auth serverkey). Do check inside auth
    # function
    # Below vctl commands can work even when volttron is not up. For others
    # volttron need to be up.
    if len(args) > 0:
        if args[0] not in ("list", "tag", "auth", "rabbitmq", "certs"):
            # check pid file
            if not utils.is_volttron_running(volttron_home):
                _stderr.write("VOLTTRON is not running. This command "
                              "requires VOLTTRON platform to be running\n")
                return 10

    conf = os.path.join(volttron_home, "config")
    if os.path.exists(conf) and "SKIP_VOLTTRON_CONFIG" not in os.environ:
        args = ["--config", conf] + args
    opts = parser.parse_args(args)

    if opts.log:
        opts.log = config.expandall(opts.log)
    if opts.log_config:
        opts.log_config = config.expandall(opts.log_config)
    opts.vip_address = config.expandall(opts.vip_address)
    if getattr(opts, "show_config", False):
        for name, value in sorted(vars(opts).items()):
            print(name, repr(value))
        return

    # Configure logging
    level = max(1, opts.verboseness)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == "-":
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(opts.log,
                    level,
                    handler_class=logging.handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        logging.config.fileConfig(opts.log_config)

    if not hasattr(opts, "func"):
        parser.print_help()
        sys.exit(0)

    opts.aip = aipmod.AIPplatform(opts)
    opts.aip.setup()

    opts.connection = None
    if utils.is_volttron_running(volttron_home):
        opts.connection = ControlConnection(opts.vip_address)

    try:
        with gevent.Timeout(opts.timeout):
            return opts.func(opts)
    except gevent.Timeout:
        _stderr.write("{}: operation timed out\n".format(opts.command))
        return 75
    except RemoteError as exc:
        print_tb = exc.print_tb
        error = exc.message
    # except AttributeError as exc:
    #     _stderr.write(
    #         "Invalid command: '{}' or command requires additional arguments\n".format(
    #             opts.command
    #         )
    #     )
    #     parser.print_help()
    #     return 1
    # raised during install if wheel not found.
    except FileNotFoundError as exc:
        _stderr.write(f"{exc.args[0]}\n")
        return 1
    except SystemExit as exc:
        # Handles if sys.exit is called from within a function if not 0
        # then we know there was an error and processing will continue
        # else we return 0 from here.  This has the added effect of
        # allowing us to cascade short circuit calls.
        if exc.args[0] != 0:
            error = exc
        else:
            return 0
    except InstallRuntimeError as exrt:
        if opts.debug:
            _log.exception(exrt)
        _stderr.write(f"{exrt.args[0]}\n")
        return 1
    finally:
        # make sure the connection to the server is closed when this scriopt is about to exit.
        if opts.connection:
            try:
                opts.connection.kill()
            except Unreachable:
                # its ok for this to fail at this point it might not even be valid.
                pass
            finally:
                opts.connection = None

    _stderr.write("{}: error: {}\n".format(opts.command, error))
    return 20


def _main():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    _main()
