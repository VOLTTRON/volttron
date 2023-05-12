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
import collections
import itertools
import sys
import re
from volttron.platform import jsonapi
from volttron.platform.agent.utils import is_secure_mode

_stdout = sys.stdout
_stderr = sys.stderr


def _calc_min_uuid_length(agents):
    n = 0
    for agent1, agent2 in itertools.combinations(agents, 2):
        common_len = sum(1 for a, b in zip(agent1.uuid, agent2.uuid) if a == b)
        if common_len > n:
            n = common_len
    return n + 1


def _list_agents(aip):
    Agent = collections.namedtuple("Agent",
                                   "name tag uuid vip_identity agent_user")
    agent_list = []
    for uuid, name in aip.list_agents().items():
        agent_list.append(Agent(name, aip.agent_tag(uuid), uuid, aip.agent_identity(uuid), ""))
    return agent_list


def escape(pattern):
    strings = re.split(r"([*?])", pattern)
    if len(strings) == 1:
        return re.escape(pattern), False
    return (
        "".join(
            ".*"
            if s == "*"
            else "."
            if s == "?"
            else s
            if s in [r"\?", r"\*"]
            else re.escape(s)
            for s in strings
        ),
        True,
    )


def _print_two_columns(dict_, key_name, value_name):
    padding = 2
    key_lengths = [len(key) for key in dict_] + [len(key_name)]
    max_key_len = max(key_lengths) + padding
    _stdout.write(
        "{}{}{}\n".format(key_name, " " * (max_key_len - len(key_name)),
                          value_name)
    )
    _stdout.write(
        "{}{}{}\n".format(
            "-" * len(key_name),
            " " * (max_key_len - len(key_name)),
            "-" * len(value_name),
        )
    )
    for key in sorted(dict_):
        value = dict_[key]
        if isinstance(value, list):
            value = sorted(value)
        _stdout.write(
            "{}{}{}\n".format(key, " " * (max_key_len - len(key)), value))


def filter_agents(agents, patterns, opts):
    by_name, by_tag, by_uuid, by_all_tagged = opts.by_name, opts.by_tag, opts.by_uuid, opts.by_all_tagged
    for pattern in patterns:
        regex, _ = escape(pattern)
        filtered_agents = set()
        
        # if no option is selected, try matching based on uuid
        if not (by_uuid or by_name or by_tag or by_all_tagged):
            reobj = re.compile(regex)
            matches = [agent for agent in agents if reobj.match(agent.uuid)]
            if len(matches) == 1:
                filtered_agents.update(matches)
            # if no match is found based on uuid, try matching on agent name
            elif len(matches) == 0:
                matches = [agent for agent in agents if
                           reobj.match(agent.name)]
                if len(matches) >= 1:
                    filtered_agents.update(matches)
        else:
            reobj = re.compile(regex + "$")
            if by_uuid:
                filtered_agents.update(
                    agent for agent in agents if reobj.match(agent.uuid))
            if by_name:
                filtered_agents.update(
                    agent for agent in agents if reobj.match(agent.name))
            if by_tag:
                filtered_agents.update(
                    agent for agent in agents if reobj.match(agent.tag or ""))
            if by_all_tagged:
                filtered_agents.update(
                    agent for agent in agents if reobj.match(agent.tag))
        yield pattern, filtered_agents


def filter_agent(agents, pattern, opts):
    return next(filter_agents(agents, [pattern], opts))[1]


def get_filtered_agents(opts, agents=None):
    if opts.pattern:
        filtered = set()
        for pattern, match in filter_agents(agents, opts.pattern, opts):
            if not match:
                _stderr.write(
                    "{}: error: agent not found: {}\n".format(opts.command,
                                                              pattern)
                )
            filtered |= match
        agents = list(filtered)
    return agents


def _show_filtered_agents(opts, field_name, field_callback, agents=None):
    """Provides generic way to filter and display agent information.
    The agents will be filtered by the provided opts.pattern and the
    following fields will be displayed:
      * UUID (or part of the UUID)
      * agent name
      * VIP identiy
      * tag
      * field_name
    @param:Namespace:opts:
        Options from argparse
    @param:string:field_name:
        Name of field to display about agents
    @param:function:field_callback:
        Function that takes an Agent as an argument and returns data
        to display
    @param:list:agents:
        List of agents to filter and display
    """
    if not agents:
        agents = _list_agents(opts.aip)

    agents = get_filtered_agents(opts, agents)

    if not agents:
        if not opts.json:
            _stderr.write("No installed Agents found\n")
        else:
            _stdout.write(f"{jsonapi.dumps({}, indent=2)}\n")
        return
    agents = sorted(agents, key=lambda x: x.name)
    if not opts.min_uuid_len:
        n = 36
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    name_width = max(5, max(len(agent.name) for agent in agents))
    tag_width = max(3, max(len(agent.tag or "") for agent in agents))
    identity_width = max(3, max(
        len(agent.vip_identity or "") for agent in agents))
    fmt = "{} {:{}} {:{}} {:{}} {:>6}\n"

    if not opts.json:
        _stderr.write(
            fmt.format(
                " " * n,
                "AGENT",
                name_width,
                "IDENTITY",
                identity_width,
                "TAG",
                tag_width,
                field_name,
            )
        )
        for agent in agents:
            _stdout.write(
                fmt.format(
                    agent.uuid[:n],
                    agent.name,
                    name_width,
                    agent.vip_identity,
                    identity_width,
                    agent.tag or "",
                    tag_width,
                    field_callback(agent),
                )
            )
    else:
        json_obj = {}
        for agent in agents:
            json_obj[agent.vip_identity] = {
                "agent_uuid": agent.uuid,
                "name": agent.name,
                "identity": agent.vip_identity,
                "agent_tag": agent.tag or "",
                field_name: field_callback(agent),
            }
        _stdout.write(f"{jsonapi.dumps(json_obj, indent=2)}\n")


def _show_filtered_agents_status(opts, status_callback, health_callback,
                                 agents=None):
    """Provides generic way to filter and display agent information.

    The agents will be filtered by the provided opts.pattern and the
    following fields will be displayed:
      * UUID (or part of the UUID)
      * agent name
      * VIP identiy
      * tag
      * field_name

    @param:Namespace:opts:
        Options from argparse
    @param:string:field_name:
        Name of field to display about agents
    @param:function:field_callback:
        Function that takes an Agent as an argument and returns data
        to display
    @param:list:agents:
        List of agents to filter and display
    """
    if not agents:
        agents = _list_agents(opts.aip)

    # Find max before so the uuid of the agent is available
    # when a usre has filtered the list.
    if not opts.min_uuid_len:
        n = 36
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)

    agents = get_filtered_agents(opts, agents)

    if not agents:
        if not opts.json:
            _stderr.write("No installed Agents found\n")
        else:
            _stdout.write(f"{jsonapi.dumps({}, indent=2)}\n")
        return

    agents = sorted(agents, key=lambda x: x.name)
    if not opts.json:
        name_width = max(5, max(len(agent.name) for agent in agents))
        tag_width = max(3, max(len(agent.tag or "") for agent in agents))
        identity_width = max(3, max(
            len(agent.vip_identity or "") for agent in agents))
        if is_secure_mode():
            user_width = max(3, max(
                len(agent.agent_user or "") for agent in agents))
            fmt = "{} {:{}} {:{}} {:{}} {:{}} {:>6} {:>15}\n"
            _stderr.write(
                fmt.format(
                    "UUID",
                    "AGENT",
                    name_width,
                    "IDENTITY",
                    identity_width,
                    "TAG",
                    tag_width,
                    "AGENT_USER",
                    user_width,
                    "STATUS",
                    "HEALTH",
                )
            )
            fmt = "{} {:{}} {:{}} {:{}} {:{}} {:<15} {:<}\n"
            for agent in agents:
                status_str = status_callback(agent)
                agent_health_dict = health_callback(agent)
                _stdout.write(
                    fmt.format(
                        agent.uuid[:n],
                        agent.name,
                        name_width,
                        agent.vip_identity,
                        identity_width,
                        agent.tag or "",
                        tag_width,
                        agent.agent_user if status_str.startswith(
                            "running") else "",
                        user_width,
                        status_str,
                        health_callback(agent),
                    )
                )
        else:
            fmt = "{} {:{}} {:{}} {:{}} {:>6} {:>15}\n"
            _stderr.write(
                fmt.format(
                    "UUID",
                    "AGENT",
                    name_width,
                    "IDENTITY",
                    identity_width,
                    "TAG",
                    tag_width,
                    "STATUS",
                    "HEALTH",
                )
            )
            fmt = "{} {:{}} {:{}} {:{}} {:<15} {:<}\n"
            for agent in agents:
                _stdout.write(
                    fmt.format(
                        agent.uuid[:n],
                        agent.name,
                        name_width,
                        agent.vip_identity,
                        identity_width,
                        agent.tag or "",
                        tag_width,
                        status_callback(agent),
                        health_callback(agent),
                    )
                )
    else:
        json_obj = {}
        for agent in agents:
            json_obj[agent.vip_identity] = {
                "agent_uuid": agent.uuid,
                "name": agent.name,
                "identity": agent.vip_identity,
                "agent_tag": agent.tag or "",
                "status": status_callback(agent),
                "health": health_callback(agent),
            }
            if is_secure_mode():
                json_obj[agent.vip_identity]["agent_user"] = (
                    agent.agent_user
                    if json_obj[agent.vip_identity]["status"].startswith(
                        "running")
                    else ""
                )
        _stdout.write(f"{jsonapi.dumps(json_obj, indent=2)}\n")


def _ask_yes_no(question, default="yes"):
    yes = set(["yes", "ye", "y"])
    no = set(["no", "n"])
    y = "y"
    n = "n"
    if default in yes:
        y = "Y"
    elif default in no:
        n = "N"
    else:
        raise ValueError("invalid default answer: '%s'" % default)
    while True:
        choice = input("{} [{}/{}] ".format(question, y, n)).lower()
        if choice == "":
            choice = default
        if choice in yes:
            return True
        if choice in no:
            return False
        _stderr.write("Please respond with 'yes' or 'no'\n")
