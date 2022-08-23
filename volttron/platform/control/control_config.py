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
import os
import sys
import tempfile
import subprocess
from volttron.platform import jsonapi

from volttron.platform.agent.known_identities import CONFIGURATION_STORE
from volttron.platform.jsonrpc import RemoteError


_stdout = sys.stdout
_stderr = sys.stderr

def add_config_to_store(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call

    file_contents = opts.infile.read()

    call(
        "manage_store",
        opts.identity,
        opts.name,
        file_contents,
        config_type=opts.config_type,
    )


def delete_config_from_store(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call
    if opts.delete_store:
        call("manage_delete_store", opts.identity)
        return

    if opts.name is None:
        _stderr.write(
            "ERROR: must specify a configuration when not deleting entire "
            "store\n"
        )
        return

    call("manage_delete_config", opts.identity, opts.name)


def list_store(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call
    results = []
    if opts.identity is None:
        results = call("manage_list_stores")
    else:
        results = call("manage_list_configs", opts.identity)

    for item in results:
        _stdout.write(item + "\n")


def get_config(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call
    results = call("manage_get", opts.identity, opts.name, raw=opts.raw)

    if opts.raw:
        _stdout.write(results)
    else:
        if isinstance(results, str):
            _stdout.write(results)
        else:
            _stdout.write(jsonapi.dumps(results, indent=2))
            _stdout.write("\n")


def edit_config(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call

    if opts.new_config:
        config_type = opts.config_type
        raw_data = ""
    else:
        try:
            results = call("manage_get_metadata", opts.identity, opts.name)
            config_type = results["type"]
            raw_data = results["data"]
        except RemoteError as e:
            if "No configuration file" not in e.message:
                raise
            config_type = opts.config_type
            raw_data = ""

    # Write raw data to temp file
    # This will not work on Windows, FYI
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="r+") as f:
        f.write(raw_data)
        f.flush()

        success = True
        try:
            # do not use utils.execute_command as we don't want set stdout to
            #  subprocess.PIPE
            subprocess.check_call([opts.editor, f.name])
        except subprocess.CalledProcessError as e:
            _stderr.write(
                "Editor returned with code {}. Changes not "
                "committed.\n".format(
                    e.returncode
                )
            )
            success = False

        if not success:
            return

        f.seek(0)
        new_raw_data = f.read()

        if new_raw_data == raw_data:
            _stderr.write("No changes detected.\n")
            return

        call(
            "manage_store",
            opts.identity,
            opts.name,
            new_raw_data,
            config_type=config_type,
        )


def add_config_store_parser(add_parser_fn):
    config_store = add_parser_fn("config",
                              help="manage the platform configuration store")

    config_store_subparsers = config_store.add_subparsers(
        title="subcommands", metavar="", dest="store_commands"
    )

    config_store_store = add_parser_fn(
        "store", help="store a configuration",
        subparser=config_store_subparsers
    )

    config_store_store.add_argument("identity",
                                    help="VIP IDENTITY of the store")
    config_store_store.add_argument(
        "name", help="name used to reference the configuration by in the store"
    )
    config_store_store.add_argument(
        "infile",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="file containing the contents of the configuration",
    )
    config_store_store.add_argument(
        "--raw",
        const="raw",
        dest="config_type",
        action="store_const",
        help="interpret the input file as raw data",
    )
    config_store_store.add_argument(
        "--json",
        const="json",
        dest="config_type",
        action="store_const",
        help="interpret the input file as json",
    )
    config_store_store.add_argument(
        "--csv",
        const="csv",
        dest="config_type",
        action="store_const",
        help="interpret the input file as csv",
    )

    config_store_store.set_defaults(func=add_config_to_store,
                                    config_type="json")

    config_store_edit = add_parser_fn(
        "edit",
        help="edit a configuration. (nano by default, respects EDITOR env "
             "variable)",
        subparser=config_store_subparsers,
    )

    config_store_edit.add_argument("identity",
                                   help="VIP IDENTITY of the store")
    config_store_edit.add_argument(
        "name", help="name used to reference the configuration by in the store"
    )
    config_store_edit.add_argument(
        "--editor",
        dest="editor",
        help="Set the editor to use to change the file. Defaults to nano if "
             "EDITOR is not set",
        default=os.getenv("EDITOR", "nano"),
    )
    config_store_edit.add_argument(
        "--raw",
        const="raw",
        dest="config_type",
        action="store_const",
        help="Interpret the configuration as raw data. If the file already "
             "exists this is ignored.",
    )
    config_store_edit.add_argument(
        "--json",
        const="json",
        dest="config_type",
        action="store_const",
        help="Interpret the configuration as json. If the file already "
             "exists this is ignored.",
    )
    config_store_edit.add_argument(
        "--csv",
        const="csv",
        dest="config_type",
        action="store_const",
        help="Interpret the configuration as csv. If the file already exists "
             "this is ignored.",
    )
    config_store_edit.add_argument(
        "--new",
        dest="new_config",
        action="store_true",
        help="Ignore any existing configuration and creates new empty file."
             " Configuration is not written if left empty. Type defaults to "
             "JSON.",
    )

    config_store_edit.set_defaults(func=edit_config, config_type="json")

    config_store_delete = add_parser_fn(
        "delete", help="delete a configuration",
        subparser=config_store_subparsers
    )
    config_store_delete.add_argument("identity",
                                     help="VIP IDENTITY of the store")
    config_store_delete.add_argument(
        "name",
        nargs="?",
        help="name used to reference the configuration by in the store",
    )
    config_store_delete.add_argument(
        "--all",
        dest="delete_store",
        action="store_true",
        help="delete all configurations in the store",
    )

    config_store_delete.set_defaults(func=delete_config_from_store)

    config_store_list = add_parser_fn(
        "list",
        help="list stores or configurations in a store",
        subparser=config_store_subparsers,
    )

    config_store_list.add_argument(
        "identity", nargs="?", help="VIP IDENTITY of the store to list"
    )

    config_store_list.set_defaults(func=list_store)

    config_store_get = add_parser_fn(
        "get",
        help="get the contents of a configuration",
        subparser=config_store_subparsers,
    )

    config_store_get.add_argument("identity", help="VIP IDENTITY of the store")
    config_store_get.add_argument(
        "name", help="name used to reference the configuration by in the store"
    )
    config_store_get.add_argument(
        "--raw", action="store_true", help="get the configuration as raw data"
    )
    config_store_get.set_defaults(func=get_config)
