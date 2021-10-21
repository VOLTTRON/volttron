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

import gevent

from volttron.platform.vip.agent.errors import Unreachable
from volttron.platform.jsonrpc import MethodNotFound


def print_rpc_list(peers, code=False):
    for peer in peers:
        print(f"{peer}")
        for method in peers[peer]:
            if code:
                print(f"\tself.vip.rpc.call({peer}, {method}).get()")
            else:
                print(f"\t{method}")


def print_rpc_methods(opts, peer_method_metadata, code=False):
    for peer in peer_method_metadata:
        if code is True:
            pass
        else:
            print(f"{peer}")
        for method in peer_method_metadata[peer]:
            params = peer_method_metadata[peer][method].get(
                "params", "No parameters for this method."
            )
            if code is True:
                if len(params) == 0:
                    print(f"self.vip.rpc.call({peer}, {method}).get()")
                else:
                    print(
                        f"self.vip.rpc.call({peer}, {method}, "
                        f"{[param for param in params]}).get()"
                    )
                continue
            else:
                print(f"\t{method}")
                if opts.verbose == True:
                    print("\tDocumentation:")
                    doc = (
                        peer_method_metadata[peer][method]
                            .get("doc", "No documentation for this method.")
                            .replace("\n", "\n\t\t")
                    )
                    print(f"\t\t{doc}\n")
            print("\tParameters:")
            if type(params) is str:
                print(f"\t\t{params}")
            else:
                for param in params:
                    print(f"\t\t{param}:\n\t\t\t{params[param]}")


def list_agents_rpc(opts):
    conn = opts.connection
    try:
        peers = sorted(conn.call("peerlist"))
    except Exception as e:
        print(e)
    if opts.by_vip == True or len(opts.pattern) == 1:
        peers = [peer for peer in peers if peer in opts.pattern]
    elif len(opts.pattern) > 1:
        peer = opts.pattern[0]
        methods = opts.pattern[1:]
        peer_method_metadata = {peer: {}}
        for method in methods:
            try:
                peer_method_metadata[peer][method] = conn.server.vip.rpc.call(
                    peer, f"{method}.inspect"
                ).get(timeout=4)
                authorized_capabilities = conn.server.vip.rpc.call(
                    peer, "auth.get_rpc_authorizations", method
                ).get(timeout=4)
                peer_method_metadata[peer][method][
                    "authorized_capabilities"
                ] = f"Authorized capabilities: {authorized_capabilities}"
            except gevent.Timeout:
                print(f"{peer} has timed out.")
            except Unreachable:
                print(f"{peer} is unreachable")
            except MethodNotFound as e:
                print(e)

        # _stdout.write(f"{peer_method_metadata}\n")
        print_rpc_methods(opts, peer_method_metadata)
        return
    peer_methods = {}
    for peer in peers:
        try:
            peer_methods[peer] = conn.server.vip.rpc.call(peer, "inspect").get(
                timeout=4
            )["methods"]
        except gevent.Timeout:
            print(f"{peer} has timed out")
        except Unreachable:
            print(f"{peer} is unreachable")
        except MethodNotFound as e:
            print(e)

    if opts.verbose is True:
        print_rpc_list(peer_methods)
        # for peer in peer_methods:
        #     _stdout.write(f"{peer}:{peer_methods[peer]}\n")
    else:
        for peer in peer_methods:
            peer_methods[peer] = [
                method for method in peer_methods[peer] if "." not in method
            ]
            # _stdout.write(f"{peer}:{peer_methods[peer]}\n")
        print_rpc_list(peer_methods)


def list_agent_rpc_code(opts):
    conn = opts.connection
    try:
        peers = sorted(conn.call("peerlist"))
    except Exception as e:
        print(e)
    if len(opts.pattern) == 1:
        peers = [peer for peer in peers if peer in opts.pattern]
    elif len(opts.pattern) > 1:
        peer = opts.pattern[0]
        methods = opts.pattern[1:]
        peer_method_metadata = {peer: {}}
        for method in methods:
            try:
                peer_method_metadata[peer][method] = conn.server.vip.rpc.call(
                    peer, f"{method}.inspect"
                ).get(timeout=4)
            except gevent.Timeout:
                print(f"{peer} has timed out.")
            except Unreachable:
                print(f"{peer} is unreachable")
            except MethodNotFound as e:
                print(e)

        # _stdout.write(f"{peer_method_metadata}\n")
        print_rpc_methods(opts, peer_method_metadata, code=True)
        return

    peer_methods = {}
    for peer in peers:
        try:
            peer_methods[peer] = conn.server.vip.rpc.call(peer, "inspect").get(
                timeout=4
            )["methods"]
        except gevent.Timeout:
            print(f"{peer} has timed out.")
        except Unreachable:
            print(f"{peer} is unreachable")
        except MethodNotFound as e:
            print(e)

    if opts.verbose is True:
        pass
    else:
        for peer in peer_methods:
            peer_methods[peer] = [
                method for method in peer_methods[peer] if "." not in method
            ]

    peer_method_metadata = {}
    for peer in peer_methods:
        peer_method_metadata[peer] = {}
        for method in peer_methods[peer]:
            try:
                peer_method_metadata[peer][method] = conn.server.vip.rpc.call(
                    peer, f"{method}.inspect"
                ).get(timeout=4)
            except gevent.Timeout:
                print(f"{peer} has timed out")
            except Unreachable:
                print(f"{peer} is unreachable")
            except MethodNotFound as e:
                print(e)
    print_rpc_methods(opts, peer_method_metadata, code=True)

def add_rpc_agent_parser(add_parser_fn):    
    rpc_ctl = add_parser_fn("rpc", help="rpc controls")

    rpc_subparsers = rpc_ctl.add_subparsers(
        title="subcommands", metavar="", dest="store_commands"
    )

    rpc_code = add_parser_fn(
        "code",
        subparser=rpc_subparsers,
        help="shows how to use rpc call in other agents",
    )

    rpc_code.add_argument(
        "pattern", nargs="*",
        help="Identity of agent, followed by method(s)" ""
    )
    rpc_code.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="list all subsystem rpc methods in addition to the agent's rpc "
             "methods",
    )

    rpc_code.set_defaults(func=list_agent_rpc_code, min_uuid_len=1)

    rpc_list = add_parser_fn(
        "list", subparser=rpc_subparsers,
        help="lists all agents and their rpc methods"
    )

    rpc_list.add_argument(
        "-i", "--vip", dest="by_vip", action="store_true",
        help="filter by vip identity"
    )

    rpc_list.add_argument("pattern", nargs="*", help="UUID or name of agent")

    rpc_list.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="list all subsystem rpc methods in addition to the agent's rpc "
             "methods. If a method "
             "is specified, display the doc-string associated with the "
             "method.",
    )

    rpc_list.set_defaults(func=list_agents_rpc, min_uuid_len=1)