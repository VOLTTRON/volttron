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

import sys
from volttron.platform.control.control_utils import _ask_yes_no
from requests.exceptions import HTTPError
from volttron.utils.rmq_mgmt import RabbitMQMgmt

_stdout = sys.stdout
_stderr = sys.stderr

rmq_mgmt = None

def add_vhost(opts):
    try:
        rmq_mgmt.create_vhost(opts.vhost)
    except HTTPError as e:
        _stdout.write("Error adding a Virtual Host: {} \n".format(opts.vhost))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def add_user(opts):
    rmq_mgmt.create_user(opts.user, opts.pwd)
    permissions = dict(configure="", read="", write="")
    read = _ask_yes_no("Do you want to set READ permission ")
    write = _ask_yes_no("Do you want to set WRITE permission ")
    configure = _ask_yes_no("Do you want to set CONFIGURE permission ")

    if read:
        permissions["read"] = ".*"
    if write:
        permissions["write"] = ".*"
    if configure:
        permissions["configure"] = ".*"
    try:
        rmq_mgmt.set_user_permissions(permissions, opts.user)
    except HTTPError as e:
        _stdout.write(
            "Error Setting User permissions : {} \n".format(opts.user))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def add_exchange(opts):
    if opts.type not in ["topic", "fanout", "direct"]:
        print(
            "Unknown exchange type. Valid exchange types are topic or fanout "
            "or direct"
        )
        return
    durable = _ask_yes_no("Do you want exchange to be durable ")
    auto_delete = _ask_yes_no("Do you want exchange to be auto deleted ")
    alternate = _ask_yes_no("Do you want alternate exchange ")

    properties = dict(durable=durable, type=opts.type, auto_delete=auto_delete)
    try:
        if alternate:
            alternate_exch = opts.name + "alternate"
            properties["alternate-exchange"] = alternate_exch
            # create alternate exchange
            new_props = dict(durable=durable, type="fanout",
                             auto_delete=auto_delete)
            rmq_mgmt.create_exchange(alternate_exch, new_props)
        rmq_mgmt.create_exchange(opts.name, properties)
    except HTTPError as e:
        _stdout.write("Error Adding Exchange : {} \n".format(opts.name))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def add_queue(opts):
    durable = _ask_yes_no("Do you want queue to be durable ")
    auto_delete = _ask_yes_no("Do you want queue to be auto deleted ")

    properties = dict(durable=durable, auto_delete=auto_delete)
    try:
        rmq_mgmt.create_queue(opts.name, properties)
    except HTTPError as e:
        _stdout.write("Error Adding Queue : {} \n".format(opts.name))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def list_vhosts(opts):
    try:
        vhosts = rmq_mgmt.get_virtualhosts()
        for item in vhosts:
            _stdout.write(item + "\n")
    except HTTPError as e:
        _stdout.write("No Virtual Hosts Found: {} \n")
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def list_users(opts):
    try:
        users = rmq_mgmt.get_users()
        for item in users:
            _stdout.write(item + "\n")
    except HTTPError as e:
        _stdout.write("No Users Found: {} \n")
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def list_user_properties(opts):
    try:
        props = rmq_mgmt.get_user_props(opts.user)
        for key, value in props.items():
            _stdout.write("{0}: {1} \n".format(key, value))
    except HTTPError as e:
        _stdout.write("No User Found: {} \n".format(opts.user))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def list_exchanges(opts):
    try:
        exchanges = rmq_mgmt.get_exchanges()
        for exch in exchanges:
            _stdout.write(exch + "\n")
    except HTTPError as e:
        _stdout.write("No exchanges found \n")
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def list_exchanges_with_properties(opts):
    exchanges = None
    try:
        exchanges = rmq_mgmt.get_exchanges_with_props()
    except HTTPError as e:
        _stdout.write("No exchanges found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        name_width = max(8, max(len(e["name"]) for e in exchanges))
        dur_width = len("DURABLE")
        auto_width = len("AUTO-DELETE")
        type_width = max(6, max(len(e["type"]) for e in exchanges))
        # args_width = max(6, max(len(e['type']) for e in exchanges))
        fmt = "{:{}} {:{}} {:{}} {:{}}\n"
        _stderr.write(
            fmt.format(
                "EXCHANGE",
                name_width,
                "TYPE",
                type_width,
                "DURABLE",
                dur_width,
                "AUTO-DELETE",
                auto_width,
            )
        )
        for exch in exchanges:
            _stdout.write(
                fmt.format(
                    exch["name"],
                    name_width,
                    exch["type"],
                    type_width,
                    str(exch["durable"]),
                    dur_width,
                    str(exch["auto_delete"]),
                    auto_width,
                )
            )
            # exch['messages'], args_width))
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in getting queue properties")


def list_queues(opts):
    queues = None
    try:
        queues = rmq_mgmt.get_queues()
    except HTTPError as e:
        _stdout.write("No queues found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    if queues:
        for q in queues:
            _stdout.write(q + "\n")


def list_queues_with_properties(opts):
    queues = None
    try:
        queues = rmq_mgmt.get_queues_with_props()
    except HTTPError as e:
        _stdout.write("No queues found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        name_width = max(5, max(len(q["name"]) for q in queues))
        dur_width = len("DURABLE")
        excl_width = len("EXCLUSIVE")
        auto_width = len("auto-delete")
        state_width = len("running")
        unack_width = len("MESSAGES")
        fmt = "{:{}} {:{}} {:{}} {:{}} {:{}} {:{}}\n"
        _stderr.write(
            fmt.format(
                "QUEUE",
                name_width,
                "STATE",
                state_width,
                "DURABLE",
                dur_width,
                "EXCLUSIVE",
                excl_width,
                "AUTO-DELETE",
                auto_width,
                "MESSAGES",
                unack_width,
            )
        )
        for q in queues:
            _stdout.write(
                fmt.format(
                    q["name"],
                    name_width,
                    str(q["state"]),
                    state_width,
                    str(q["durable"]),
                    dur_width,
                    str(q["exclusive"]),
                    excl_width,
                    str(q["auto_delete"]),
                    auto_width,
                    q["messages"],
                    unack_width,
                )
            )
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in getting queue properties")


def list_connections(opts):
    try:
        conn = rmq_mgmt.get_connections()
    except HTTPError as e:
        _stdout.write("No connections found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return


def list_fed_parameters(opts):
    parameters = None
    try:
        parameters = rmq_mgmt.get_parameter("federation-upstream")
    except HTTPError as e:
        _stdout.write("No Federation Parameters Found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        if parameters:
            name_width = max(5, max(len(p["name"]) for p in parameters))
            uri_width = max(3, max(len(p["value"]["uri"]) for p in parameters))
            fmt = "{:{}} {:{}}\n"
            _stderr.write(fmt.format("NAME", name_width, "URI", uri_width))
            for param in parameters:
                _stdout.write(
                    fmt.format(
                        param["name"], name_width, param["value"]["uri"],
                        uri_width
                    )
                )
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in federation parameters")


def list_shovel_parameters(opts):
    parameters = None
    try:
        parameters = rmq_mgmt.get_parameter("shovel")
    except HTTPError as e:
        _stdout.write("No Shovel Parameters Found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        if parameters:
            name_width = max(5, max(len(p["name"]) for p in parameters))
            src_uri_width = max(
                len("SOURCE ADDRESS"),
                max(len(p["value"]["src-uri"]) for p in parameters),
            )
            dest_uri_width = max(
                len("DESTINATION ADDRESS"),
                max(len(p["value"]["dest-uri"]) for p in parameters),
            )
            binding_key = max(
                len("BINDING KEY"),
                max(len(p["value"]["src-exchange-key"]) for p in parameters),
            )
            fmt = "{:{}}  {:{}}  {:{}}  {:{}}\n"
            _stderr.write(
                fmt.format(
                    "NAME",
                    name_width,
                    "SOURCE ADDRESS",
                    src_uri_width,
                    "DESTINATION ADDRESS",
                    dest_uri_width,
                    "BINDING KEY",
                    binding_key,
                )
            )
            for param in parameters:
                _stdout.write(
                    fmt.format(
                        param["name"],
                        name_width,
                        param["value"]["src-uri"],
                        src_uri_width,
                        param["value"]["dest-uri"],
                        dest_uri_width,
                        param["value"]["src-exchange-key"],
                        binding_key,
                    )
                )
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in getting shovel parameters")


def list_fed_links(opts):
    links = None
    try:
        links = rmq_mgmt.get_federation_links()
    except HTTPError as e:
        _stdout.write("No Federation links Found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        if links:
            name_width = max(5, max(len(lk["name"]) for lk in links))
            status_width = max(3, max(len(lk["status"]) for lk in links))
            fmt = "{:{}} {:{}}\n"
            _stderr.write(
                fmt.format("NAME", name_width, "STATUS", status_width))
            for link in links:
                _stdout.write(
                    fmt.format(link["name"], name_width, link["status"],
                               status_width)
                )
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in federation links")


def list_shovel_links(opts):
    links = None
    try:
        links = rmq_mgmt.get_shovel_links()
    except HTTPError as e:
        _stdout.write("No Shovel links Found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        if links:
            name_width = max(5, max(len(lk["name"]) for lk in links))
            status_width = max(3, max(len(lk["status"]) for lk in links))
            src_exchange_key_width = max(
                3, max(len(lk["src_exchange_key"]) for lk in links)
            )
            src_uri_width = max(3, max(len(lk["src_uri"]) for lk in links))
            dest_uri_width = max(3, max(len(lk["dest_uri"]) for lk in links))
            fmt = "{:{}}  {:{}}  {:{}}  {:{}}  {:{}}\n"
            _stderr.write(
                fmt.format(
                    "NAME",
                    name_width,
                    "STATUS",
                    status_width,
                    "SRC_URI",
                    src_uri_width,
                    "DEST_URI",
                    dest_uri_width,
                    "SRC_EXCHANGE_KEY",
                    src_exchange_key_width,
                )
            )
            for link in links:
                _stdout.write(
                    fmt.format(
                        link["name"],
                        name_width,
                        link["status"],
                        status_width,
                        link["src_uri"],
                        src_uri_width,
                        link["dest_uri"],
                        dest_uri_width,
                        link["src_exchange_key"],
                        src_exchange_key_width,
                    )
                )
    except (AttributeError, KeyError) as ex:
        _stdout.write(f"Error in shovel links as {ex}")


def list_bindings(opts):
    bindings = None
    try:
        bindings = rmq_mgmt.get_bindings(opts.exchange)
    except HTTPError as e:
        _stdout.write("No Bindings Found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return

    try:
        if bindings:
            src_width = max(5, max(len(b["source"]) for b in bindings))
            exch_width = len("EXCHANGE")
            dest_width = max(len("QUEUE"),
                             max(len(b["destination"]) for b in bindings))
            bindkey = len("BINDING KEY")
            rkey = max(10, max(len(b["routing_key"]) for b in bindings))
            fmt = "{:{}}  {:{}}  {:{}}\n"
            _stderr.write(
                fmt.format(
                    "EXCHANGE", exch_width, "QUEUE", dest_width, "BINDING KEY",
                    bindkey
                )
            )
            for b in bindings:
                _stdout.write(
                    fmt.format(
                        b["source"],
                        src_width,
                        b["destination"],
                        dest_width,
                        b["routing_key"],
                        rkey,
                    )
                )
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in getting bindings")


def list_policies(opts):
    policies = None
    try:
        policies = rmq_mgmt.get_policies()
    except HTTPError as e:
        _stdout.write("No Policies Found \n")
        return
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )
        return
    try:
        if policies:
            name_width = max(5, max(len(p["name"]) for p in policies))
            apply_width = max(8, max(len(p["apply-to"]) for p in policies))
            fmt = "{:{}} {:{}}\n"
            _stderr.write(
                fmt.format("NAME", name_width, "APPLY-TO", apply_width))
            for policy in policies:
                _stdout.write(
                    fmt.format(
                        policy["name"], name_width, policy["apply-to"],
                        apply_width
                    )
                )
    except (AttributeError, KeyError) as ex:
        _stdout.write("Error in getting policies")


def remove_vhosts(opts):
    try:
        for vhost in opts.vhost:
            rmq_mgmt.delete_vhost(vhost)
    except HTTPError as e:
        _stdout.write("No Vhost Found {} \n".format(opts.vhost))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def remove_users(opts):
    try:
        for user in opts.user:
            rmq_mgmt.delete_user(user)
    except HTTPError as e:
        _stdout.write("No User Found {} \n".format(opts.user))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def remove_exchanges(opts):
    try:
        for e in opts.exchanges:
            rmq_mgmt.delete_exchange(e)
    except HTTPError as e:
        _stdout.write("No Exchange Found {} \n".format(opts.exchanges))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def remove_queues(opts):
    try:
        for q in opts.queues:
            rmq_mgmt.delete_queue(q)
    except HTTPError as e:
        _stdout.write("No Queues Found {} \n".format(opts.queues))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def remove_fed_parameters(opts):
    try:
        for param in opts.parameters:
            delete_certs = _ask_yes_no(
                f"Do you wish to delete certificates as well for {param}?"
            )
            rmq_mgmt.delete_multiplatform_parameter(
                "federation-upstream", param, delete_certs=delete_certs
            )
    except HTTPError as e:
        _stdout.write(
            "No Federation Parameters Found {} \n".format(opts.parameters))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def remove_shovel_parameters(opts):
    try:
        for param in opts.parameters:
            delete_certs = _ask_yes_no(
                "Do you wish to delete certificates as well?")
            rmq_mgmt.delete_multiplatform_parameter(
                "shovel", param, delete_certs=delete_certs
            )
    except HTTPError as e:
        _stdout.write(
            "No Shovel Parameters Found {} \n".format(opts.parameters))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def remove_policies(opts):
    try:
        for policy in opts.policies:
            rmq_mgmt.delete_policy(policy)
    except HTTPError as e:
        _stdout.write("No Policies Found {} \n".format(opts.policies))
    except ConnectionError as e:
        _stdout.write(
            "Error making request to RabbitMQ Management interface.\n"
            "Check Connection Parameters: {} \n".format(e)
        )


def add_rabbitmq_parser(add_parser):
    global rmq_mgmt
    rmq_mgmt = RabbitMQMgmt()
    rabbitmq_cmds = add_parser("rabbitmq", help="manage rabbitmq")
    rabbitmq_subparsers = rabbitmq_cmds.add_subparsers(
        title="subcommands", metavar="", dest="store_commands"
    )
    rabbitmq_add_vhost = add_parser(
        "add-vhost", help="add a new virtual host",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_add_vhost.add_argument("vhost", help="Virtual host")
    rabbitmq_add_vhost.set_defaults(func=add_vhost)

    rabbitmq_add_user = add_parser(
        "add-user",
        help="Add a new user. User will have admin privileges i.e,"
                "configure, read and write",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_add_user.add_argument("user", help="user id")
    rabbitmq_add_user.add_argument("pwd", help="password")
    rabbitmq_add_user.set_defaults(func=add_user)

    rabbitmq_add_exchange = add_parser(
        "add-exchange", help="add a new exchange",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_add_exchange.add_argument("name", help="Name of the exchange")
    rabbitmq_add_exchange.add_argument(
        "type", help="Type of the exchange - fanout/direct/topic"
    )
    rabbitmq_add_exchange.set_defaults(func=add_exchange)

    rabbitmq_add_queue = add_parser(
        "add-queue", help="add a new queue", subparser=rabbitmq_subparsers
    )
    rabbitmq_add_queue.add_argument("name", help="Name of the queue")
    rabbitmq_add_queue.set_defaults(func=add_queue)
    # =====================================================================
    # List commands
    rabbitmq_list_vhosts = add_parser(
        "list-vhosts", help="List virtual hosts",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_list_vhosts.set_defaults(func=list_vhosts)

    rabbitmq_list_users = add_parser(
        "list-users", help="List users", subparser=rabbitmq_subparsers
    )
    rabbitmq_list_users.set_defaults(func=list_users)

    rabbitmq_list_user_properties = add_parser(
        "list-user-properties", help="List users",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_list_user_properties.add_argument("user",
                                                help="RabbitMQ user id")
    rabbitmq_list_user_properties.set_defaults(func=list_user_properties)

    rabbitmq_list_exchanges = add_parser(
        "list-exchanges", help="List exhanges",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_list_exchanges.set_defaults(func=list_exchanges)

    rabbitmq_list_exchanges_props = add_parser(
        "list-exchange-properties",
        help="list exchanges with properties",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_exchanges_props.set_defaults(
        func=list_exchanges_with_properties)

    rabbitmq_list_queues = add_parser(
        "list-queues", help="list all queues",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_list_queues.set_defaults(func=list_queues)
    rabbitmq_list_queues_props = add_parser(
        "list-queue-properties",
        help="list queues with properties",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_queues_props.set_defaults(
        func=list_queues_with_properties)

    rabbitmq_list_bindings = add_parser(
        "list-bindings",
        help="list all bindings with exchange",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_bindings.add_argument("exchange", help="Source exchange")
    rabbitmq_list_bindings.set_defaults(func=list_bindings)

    rabbitmq_list_fed_parameters = add_parser(
        "list-federation-parameters",
        help="list all federation parameters",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_fed_parameters.set_defaults(func=list_fed_parameters)

    rabbitmq_list_fed_links = add_parser(
        "list-federation-links",
        help="list all federation links",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_fed_links.set_defaults(func=list_fed_links)

    rabbitmq_list_shovel_links = add_parser(
        "list-shovel-links",
        help="list all Shovel links",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_shovel_links.set_defaults(func=list_shovel_links)

    rabbitmq_list_shovel_parameters = add_parser(
        "list-shovel-parameters",
        help="list all shovel parameters",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_list_shovel_parameters.set_defaults(
        func=list_shovel_parameters)

    rabbitmq_list_policies = add_parser(
        "list-policies", help="list all policies",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_list_policies.set_defaults(func=list_policies)
    # =====================================================================
    # Remove commands
    rabbitmq_remove_vhosts = add_parser(
        "remove-vhosts", help="Remove virtual host/s",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_remove_vhosts.add_argument("vhost", nargs="+",
                                        help="Virtual host")
    rabbitmq_remove_vhosts.set_defaults(func=remove_vhosts)

    rabbitmq_remove_users = add_parser(
        "remove-users", help="Remove virtual user/s",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_remove_users.add_argument("user", nargs="+",
                                        help="Virtual host")
    rabbitmq_remove_users.set_defaults(func=remove_users)

    rabbitmq_remove_exchanges = add_parser(
        "remove-exchanges", help="Remove exchange/s",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_remove_exchanges.add_argument(
        "exchanges", nargs="+", help="Remove exchanges/s"
    )
    rabbitmq_remove_exchanges.set_defaults(func=remove_exchanges)

    rabbitmq_remove_queues = add_parser(
        "remove-queues", help="Remove queue/s",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_remove_queues.add_argument("queues", nargs="+", help="Queue")
    rabbitmq_remove_queues.set_defaults(func=remove_queues)

    rabbitmq_remove_fed_parameters = add_parser(
        "remove-federation-links",
        help="Remove federation parameter",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_remove_fed_parameters.add_argument(
        "parameters", nargs="+", help="parameter name/s"
    )
    rabbitmq_remove_fed_parameters.set_defaults(func=remove_fed_parameters)

    rabbitmq_remove_shovel_parameters = add_parser(
        "remove-shovel-links",
        help="Remove shovel parameter",
        subparser=rabbitmq_subparsers,
    )
    rabbitmq_remove_shovel_parameters.add_argument(
        "parameters", nargs="+", help="parameter name/s"
    )
    rabbitmq_remove_shovel_parameters.set_defaults(
        func=remove_shovel_parameters)

    rabbitmq_remove_policies = add_parser(
        "remove-policies", help="Remove policy",
        subparser=rabbitmq_subparsers
    )
    rabbitmq_remove_policies.add_argument(
        "policies", nargs="+", help="policy name/s"
    )
    rabbitmq_remove_policies.set_defaults(func=remove_policies)
