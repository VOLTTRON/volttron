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

import logging
import os
import sys
import collections

from volttron.platform import get_home, jsonapi

from volttron.platform.agent.known_identities import AUTH
from volttron.platform.auth import AuthEntry, AuthException
from volttron.platform.control.control_utils import _ask_yes_no, _print_two_columns, _show_filtered_agents
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.vip.agent.subsystems.query import Query

_log = logging.getLogger(__name__)

_stdout = sys.stdout
_stderr = sys.stderr


def gen_keypair(opts):
    keypair = KeyStore.generate_keypair_dict()
    _stdout.write("{}\n".format(jsonapi.dumps(keypair, indent=2)))


def add_server_key(opts):
    store = KnownHostsStore()
    store.add(opts.host, opts.serverkey)
    _stdout.write("server key written to {}\n".format(store.filename))


def list_known_hosts(opts):
    store = KnownHostsStore()
    entries = store.load()
    if entries:
        _print_two_columns(entries, "HOST", "CURVE KEY")
    else:
        _stdout.write("No entries in {}\n".format(store.filename))


def remove_known_host(opts):
    store = KnownHostsStore()
    store.remove(opts.host)
    _stdout.write(
        'host "{}" removed from {}\n'.format(opts.host, store.filename))

def show_serverkey(opts):
    """
    write serverkey to standard out.

    return 0 if success, 1 if false
    """
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return 1
    q = Query(conn.server.core)
    pk = q.query("serverkey").get(timeout=2)
    del q
    if pk is not None:
        _stdout.write("%s\n" % pk)
        return 0

    return 1


def list_remotes(opts):
    """Lists remote certs and credentials.
    Can be filters using the '--status' option, specifying
    pending, approved, or denied.
    The output printed includes:
        user id of a ZMQ credential, or the common name of a CSR
        remote address of the credential or csr
        status of the credential or cert (either APPROVED, DENIED, or PENDING)

    """
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return

    output_view = []
    # try:
    #     pending_csrs = conn.server.vip.rpc.call(AUTH, "get_pending_csrs").get(
    #         timeout=4)
    #     for csr in pending_csrs:
    #         output_view.append(
    #             {
    #                 "entry": {
    #                     "user_id": csr["identity"],
    #                     "address": csr["remote_ip_address"],
    #                 },
    #                 "status": csr["status"],
    #             }
    #         )
    # except TimeoutError:
    #     print("Certs timed out")
    try:
        approved_certs = conn.server.vip.rpc.call(
            AUTH, "get_approved_authorizations"
        ).get(timeout=4)
        for value in approved_certs:
            output_view.append({"entry": value, "status": "APPROVED"})
    except TimeoutError:
        print("Approved credentials timed out")
    try:
        denied_certs = conn.server.vip.rpc.call(AUTH,
                                                "get_denied_authorizations").get(
            timeout=4
        )
        for value in denied_certs:
            output_view.append({"entry": value, "status": "DENIED"})
    except TimeoutError:
        print("Denied credentials timed out")
    try:
        pending_certs = conn.server.vip.rpc.call(AUTH,
                                                 "get_pending_authorizations").get(
            timeout=4
        )
        for value in pending_certs:
            output_view.append({"entry": value, "status": "PENDING"})
    except TimeoutError:
        print("Pending credentials timed out")

    if not output_view:
        print("No remote certificates or credentials")
        return

    if opts.status == "approved":
        output_view = [
            output for output in output_view if output["status"] == "APPROVED"
        ]

    elif opts.status == "denied":
        output_view = [output for output in output_view if
                       output["status"] == "DENIED"]

    elif opts.status == "pending":
        output_view = [
            output for output in output_view if output["status"] == "PENDING"
        ]

    elif opts.status is not None:
        _stdout.write(
            "Invalid parameter. Please use 'approved', 'denied', 'pending', "
            "or leave blank to list all.\n"
        )
        return

    if len(output_view) == 0:
        print(f"No {opts.status} remote certificates or credentials")
        return
    for output in output_view:
        output["entry"] = {"user_id" if k == "identity" else "address" if "remote_ip_address" else k:v for k,v in output["entry"].items()}
        for value in output["entry"]:
            if not output["entry"][value]:
                output["entry"][value] = "-"
    userid_width = max(
        5, max(len(str(output["entry"]["user_id"])) for output in output_view)
    )
    address_width = max(
        5, max(len(str(output["entry"]["address"])) for output in output_view)
    )
    status_width = max(5, max(
        len(str(output["status"])) for output in output_view))
    fmt = "{:{}} {:{}} {:{}}\n"
    _stderr.write(
        fmt.format(
            "USER_ID", userid_width, "ADDRESS", address_width, "STATUS",
            status_width
        )
    )
    fmt = "{:{}} {:{}} {:{}}\n"
    for output in output_view:
        _stdout.write(
            fmt.format(
                output["entry"]["user_id"],
                userid_width,
                output["entry"]["address"],
                address_width,
                output["status"],
                status_width,
            )
        )


def approve_remote(opts):
    """Approves either a pending CSR or ZMQ credential.
    The platform must be running for this command to succeed.
    :param opts.user_id: The ZMQ credential user_id or pending CSR common name
    :type opts.user_id: str
    """
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    conn.server.vip.rpc.call(AUTH, "approve_authorization",
                             opts.user_id).get(
        timeout=4
    )


def deny_remote(opts):
    """Denies either a pending CSR or ZMQ credential.
    The platform must be running for this command to succeed.
    :param opts.user_id: The ZMQ credential user_id or pending CSR common name
    :type opts.user_id: str
    """
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    conn.server.vip.rpc.call(AUTH, "deny_authorization",
                             opts.user_id).get(
        timeout=4
    )


def delete_remote(opts):
    """Deletes either a pending CSR or ZMQ credential.
    The platform must be running for this command to succeed.
    :param opts.user_id: The ZMQ credential user_id or pending CSR common name
    :type opts.user_id: str
    """
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    conn.server.vip.rpc.call(AUTH, "delete_authorization",
                             opts.user_id).get(
        timeout=4
    )


def get_agent_publickey(opts):
    def get_key(agent):
        return opts.aip.get_agent_keystore(agent.uuid).public

    _show_filtered_agents(opts, "PUBLICKEY", get_key)


def list_auth(opts, indices=None):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return

    entries = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()[
        "allow_list"]
    print_out = []
    if entries:
        for index, entry in enumerate(entries):
            if indices is None or index in indices:
                _stdout.write("\nINDEX: {}\n".format(index))
                _stdout.write("{}\n".format(jsonapi.dumps(entry, indent=2)))
    else:
        _stdout.write(
            "No entries in {}\n".format(os.path.join(get_home(), "auth.json"))
        )


def _ask_for_auth_fields(
    domain=None,
    address=None,
    user_id=None,
    identity=None,
    capabilities=None,
    roles=None,
    groups=None,
    mechanism="CURVE",
    credentials=None,
    comments=None,
    enabled=True,
    **kwargs,
):
    """Prompts user for Auth Entry fields."""

    class Asker(object):
        def __init__(self):
            self._fields = collections.OrderedDict()

        def add(
            self,
            name,
            default=None,
            note=None,
            callback=lambda x: x,
            validate=lambda x, y: (True, ""),
        ):
            self._fields[name] = {
                "note": note,
                "default": default,
                "callback": callback,
                "validate": validate,
            }

        def ask(self):
            for name in self._fields:
                note = self._fields[name]["note"]
                default = self._fields[name]["default"]
                callback = self._fields[name]["callback"]
                validate = self._fields[name]["validate"]
                if isinstance(default, list):
                    default_str = "{}".format(",".join(default))
                elif default is None:
                    default_str = ""
                else:
                    default_str = default
                note = "({}) ".format(note) if note else ""
                question = "{} {}[{}]: ".format(name, note, default_str)
                valid = False
                while not valid:
                    response = input(question).strip()
                    if response == "":
                        response = default
                    if response == "clear":
                        if _ask_yes_no("Do you want to clear this field?"):
                            response = None
                    valid, msg = validate(response, self._fields)
                    if not valid:
                        _stderr.write("{}\n".format(msg))

                self._fields[name]["response"] = callback(response)
            return {k: self._fields[k]["response"] for k in self._fields}

    def to_true_or_false(response):
        if isinstance(response, str):
            return {"true": True, "false": False}[response.lower()]
        return response

    def is_true_or_false(x, fields):
        if x is not None:
            if isinstance(x, bool) or x.lower() in ["true", "false"]:
                return True, None
        return False, "Please enter True or False"

    def valid_creds(creds, fields):
        try:
            mechanism = fields["mechanism"]["response"]
            AuthEntry.valid_credentials(creds, mechanism=mechanism)
        except AuthException as e:
            return False, str(e)
        return True, None

    def valid_mech(mech, fields):
        try:
            AuthEntry.valid_mechanism(mech)
        except AuthException as e:
            return False, str(e)
        return True, None

    asker = Asker()
    asker.add("domain", domain)
    asker.add("address", address)
    asker.add("user_id", user_id)
    asker.add("identity", identity)
    asker.add(
        "capabilities",
        capabilities,
        "delimit multiple entries with comma",
        _parse_capabilities,
    )
    asker.add("roles", roles, "delimit multiple entries with comma",
              _comma_split)
    asker.add("groups", groups, "delimit multiple entries with comma",
              _comma_split)
    asker.add("mechanism", mechanism, validate=valid_mech)
    asker.add("credentials", credentials, validate=valid_creds)
    asker.add("comments", comments)
    asker.add("enabled", enabled, callback=to_true_or_false,
              validate=is_true_or_false)

    return asker.ask()


def _comma_split(line):
    if not isinstance(line, str):
        return line
    line = line.strip()
    if not line:
        return []
    return [word.strip() for word in line.split(",")]


def _parse_capabilities(line):
    if not isinstance(line, str):
        return line
    line = line.strip()
    try:
        result = jsonapi.loads(line.replace("'", '"'))
    except Exception as e:
        result = _comma_split(line)
    return result


def add_auth(opts):
    """Add authorization entry.

    If all options are None, then use interactive 'wizard.'
    """
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return

    fields = {
        "domain": opts.domain,
        "address": opts.address,
        "mechanism": opts.mechanism,
        "credentials": opts.credentials,
        "user_id": opts.user_id,
        "identity": opts.user_id,
        "groups": _comma_split(opts.groups),
        "roles": _comma_split(opts.roles),
        "capabilities": _parse_capabilities(opts.capabilities),
        "rpc_method_authorizations": None,
        "comments": opts.comments,
    }

    if any(fields.values()):
        # Remove unspecified options so the default parameters are used
        fields = {k: v for k, v in fields.items() if v}
        fields["enabled"] = not opts.disabled
        entry = fields
    else:
        # No options were specified, use interactive wizard
        responses = _ask_for_auth_fields()
        responses["rpc_method_authorizations"] = None
        entry = responses

    if opts.add_known_host:
        if entry["address"] is None:
            raise ValueError(
                "host (--address) is required when " "--add-known-host is "
                "specified"
            )
        if entry["credentials"] is None:
            raise ValueError(
                "serverkey (--credentials) is required when "
                "--add-known-host is specified"
            )
        opts.host = entry["address"]
        opts.serverkey = entry["credentials"]
        add_server_key(opts)

    try:
        conn.server.vip.rpc.call(AUTH, "auth_file.add", entry).get(timeout=4)
        _stdout.write("added entry {}\n".format(entry))
    except AuthException as err:
        _stderr.write("ERROR: %s\n" % str(err))


def remove_auth(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    entry_count = len(
        conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["allow_list"]
    )

    for i in opts.indices:
        if i < 0 or i >= entry_count:
            _stderr.write("ERROR: invalid index {}\n".format(i))
            return

    _stdout.write("This action will delete the following:\n")
    list_auth(opts, opts.indices)
    if not _ask_yes_no("Do you wish to delete?"):
        return
    try:
        conn.server.vip.rpc.call(AUTH, "auth_file.remove_by_indices",
                                 opts.indices)
        if len(opts.indices) > 1:
            msg = "removed entries at indices {}".format(opts.indices)
        else:
            msg = msg = "removed entry at index {}".format(opts.indices)
        _stdout.write(msg + "\n")
    except AuthException as err:
        _stderr.write("ERROR: %s\n" % str(err))


def update_auth(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return

    entries = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()[
        "allow_list"]
    try:
        if opts.index < 0:
            raise IndexError
        entry = entries[opts.index]
        _stdout.write('(For any field type "clear" to clear the value.)\n')
        response = _ask_for_auth_fields(**entry)
        response["rpc_method_authorizations"] = None
        updated_entry = response
        conn.server.vip.rpc.call(
            AUTH, "auth_file.update_by_index", updated_entry, opts.index
        )
        _stdout.write("updated entry at index {}\n".format(opts.index))
    except IndexError:
        _stderr.write("ERROR: invalid index %s\n" % opts.index)
    except AuthException as err:
        _stderr.write("ERROR: %s\n" % str(err))


def add_role(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return

    roles = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["roles"]
    if opts.role in roles:
        _stderr.write('role "{}" already exists\n'.format(opts.role))
        return
    roles[opts.role] = list(set(opts.capabilities))
    conn.server.vip.rpc.call(AUTH, "auth_file.set_roles", roles)
    _stdout.write('added role "{}"\n'.format(opts.role))


def list_roles(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    roles = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["roles"]
    _print_two_columns(roles, "ROLE", "CAPABILITIES")


def update_role(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    roles = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["roles"]
    if opts.role not in roles:
        _stderr.write('role "{}" does not exist\n'.format(opts.role))
        return
    caps = roles[opts.role]
    if opts.remove:
        roles[opts.role] = list(set(caps) - set(opts.capabilities))
    else:
        roles[opts.role] = list(set(caps) | set(opts.capabilities))
    conn.server.vip.rpc.call(AUTH, "auth_file.set_roles", roles)
    _stdout.write('updated role "{}"\n'.format(opts.role))


def remove_role(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    roles = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["roles"]
    if opts.role not in roles:
        _stderr.write('role "{}" does not exist\n'.format(opts.role))
        return
    del roles[opts.role]
    conn.server.vip.rpc.call(AUTH, "auth_file.set_roles", roles)
    _stdout.write('removed role "{}"\n'.format(opts.role))


def add_group(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    groups = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["groups"]
    if opts.group in groups:
        _stderr.write('group "{}" already exists\n'.format(opts.group))
        return
    groups[opts.group] = list(set(opts.roles))
    conn.server.vip.rpc.call(AUTH, "auth_file.set_groups", groups)
    _stdout.write('added group "{}"\n'.format(opts.group))


def list_groups(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    groups = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["groups"]
    _print_two_columns(groups, "GROUPS", "ROLES")


def update_group(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    groups = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["groups"]
    if opts.group not in groups:
        _stderr.write('group "{}" does not exist\n'.format(opts.group))
        return
    roles = groups[opts.group]
    if opts.remove:
        groups[opts.group] = list(set(roles) - set(opts.roles))
    else:
        groups[opts.group] = list(set(roles) | set(opts.roles))
    conn.server.vip.rpc.call(AUTH, "auth_file.set_groups", groups)
    _stdout.write('updated group "{}"\n'.format(opts.group))


def remove_group(opts):
    conn = opts.connection
    if not conn:
        _stderr.write(
            "VOLTTRON is not running. This command "
            "requires VOLTTRON platform to be running\n"
        )
        return
    groups = conn.server.vip.rpc.call(AUTH, "auth_file.read").get()["groups"]
    if opts.group not in groups:
        _stderr.write('group "{}" does not exist\n'.format(opts.group))
        return
    del groups[opts.group]
    conn.server.vip.rpc.call(AUTH, "auth_file.set_groups", groups)
    _stdout.write('removed group "{}"\n'.format(opts.group))


def add_agent_rpc_authorizations(opts):
    """
    Adds authorizations to method in auth entry in auth file.

    :param opts: Contains command line pattern and connection
    :return: None
    """
    conn = opts.connection
    agent_id = ".".join(opts.pattern[0].split(".")[:-1])
    agent_method = opts.pattern[0].split(".")[-1]
    if len(opts.pattern) < 2:
        _log.error(
            "Missing authorizations for method. "
            "Should be in the format agent_id.method "
            "authorized_capability1 authorized_capability2 ..."
        )
        return
    added_auths = [x for x in opts.pattern[1:]]
    try:
        conn.server.vip.rpc.call(
            AUTH, "add_rpc_authorizations", agent_id, agent_method, added_auths
        ).get(timeout=4)
    except TimeoutError:
        _log.error(
            f"Adding RPC authorizations {added_auths} for {agent_id}'s "
            f"method {agent_method} timed out"
        )
    except Exception as e:
        _log.error(
            f"{e}) \nCommand format should be agent_id.method "
            f"authorized_capability1 authorized_capability2 ..."
        )
    return


def remove_agent_rpc_authorizations(opts):
    """
    Removes authorizations to method in auth entry in auth file.

    :param opts: Contains command line pattern and connection
    :return: None
    """
    conn = opts.connection
    agent_id = ".".join(opts.pattern[0].split(".")[:-1])
    agent_method = opts.pattern[0].split(".")[-1]
    if len(opts.pattern) < 2:
        _log.error(
            "Missing authorizations for method. "
            "Should be in the format agent_id.method "
            "authorized_capability1 authorized_capability2 ..."
        )
        return
    removed_auths = [x for x in opts.pattern[1:]]
    try:
        conn.server.vip.rpc.call(
            AUTH,
            "delete_rpc_authorizations",
            agent_id,
            agent_method,
            removed_auths,
        ).get(timeout=4)
    except TimeoutError:
        _log.error(
            f"Adding RPC authorizations {removed_auths} for {agent_id}'s "
            f"method {agent_method} timed out"
        )
    except Exception as e:
        _log.error(
            f"{e}) \nCommand format should be agent_id.method "
            f"authorized_capability1 authorized_capability2 ..."
        )
    return


def add_auth_parser(add_parser_fn, filterable):
    auth_cmds = add_parser_fn(
        "auth", help="manage authorization entries and encryption keys"
    )

    auth_subparsers = auth_cmds.add_subparsers(
        title="subcommands", metavar="", dest="store_commands"
    )

    auth_add = add_parser_fn(
        "add", help="add new authentication record", subparser=auth_subparsers
    )
    auth_add.add_argument("--domain", default=None)
    auth_add.add_argument("--address", default=None)
    auth_add.add_argument("--mechanism", default=None)
    auth_add.add_argument("--credentials", default=None)
    auth_add.add_argument("--user_id", default=None)
    auth_add.add_argument("--identity", default=None)
    auth_add.add_argument(
        "--groups", default=None, help="delimit multiple entries with comma"
    )
    auth_add.add_argument(
        "--roles", default=None, help="delimit multiple entries with comma"
    )
    auth_add.add_argument(
        "--capabilities", default=None,
        help="delimit multiple entries with comma"
    )
    auth_add.add_argument("--comments", default=None)
    auth_add.add_argument("--disabled", action="store_true")
    auth_add.add_argument(
        "--add-known-host", action="store_true",
        help="adds entry in known host"
    )
    auth_add.set_defaults(func=add_auth)

    auth_add_group = add_parser_fn(
        "add-group",
        subparser=auth_subparsers,
        help="associate a group name with a set of roles",
    )
    auth_add_group.add_argument("group", metavar="GROUP", help="name of group")
    auth_add_group.add_argument(
        "roles", metavar="ROLE", nargs="*",
        help="roles to associate with the group"
    )
    auth_add_group.set_defaults(func=add_group)

    auth_add_known_host = add_parser_fn(
        "add-known-host",
        subparser=auth_subparsers,
        help="add server public key to known-hosts file",
    )
    auth_add_known_host.add_argument(
        "--host", required=True,
        help="hostname or IP address with optional port"
    )
    auth_add_known_host.add_argument("--serverkey", required=True)
    auth_add_known_host.set_defaults(func=add_server_key)

    auth_add_role = add_parser_fn(
        "add-role",
        subparser=auth_subparsers,
        help="associate a role name with a set of capabilities",
    )
    auth_add_role.add_argument("role", metavar="ROLE", help="name of role")
    auth_add_role.add_argument(
        "capabilities",
        metavar="CAPABILITY",
        nargs="*",
        help="capabilities to associate with the role",
    )
    auth_add_role.set_defaults(func=add_role)

    auth_keypair = add_parser_fn(
        "keypair",
        subparser=auth_subparsers,
        help="generate CurveMQ keys for encrypting VIP connections",
    )
    auth_keypair.set_defaults(func=gen_keypair)

    auth_list = add_parser_fn(
        "list", help="list authentication records", subparser=auth_subparsers
    )
    auth_list.set_defaults(func=list_auth)

    auth_list_groups = add_parser_fn(
        "list-groups",
        subparser=auth_subparsers,
        help="show list of group names and their sets of roles",
    )
    auth_list_groups.set_defaults(func=list_groups)

    auth_list_known_host = add_parser_fn(
        "list-known-hosts",
        subparser=auth_subparsers,
        help="list entries from known-hosts file",
    )
    auth_list_known_host.set_defaults(func=list_known_hosts)

    auth_list_roles = add_parser_fn(
        "list-roles",
        subparser=auth_subparsers,
        help="show list of role names and their sets of capabilities",
    )
    auth_list_roles.set_defaults(func=list_roles)

    auth_publickey = add_parser_fn(
        "publickey",
        parents=[filterable],
        subparser=auth_subparsers,
        help="show public key for each agent",
    )
    auth_publickey.add_argument("pattern", nargs="*",
                                help="UUID or name of agent")
    auth_publickey.add_argument(
        "-n",
        dest="min_uuid_len",
        type=int,
        metavar="N",
        help="show at least N characters of UUID (0 to show all)",
    )
    auth_publickey.set_defaults(func=get_agent_publickey, min_uuid_len=1)

    auth_remove = add_parser_fn(
        "remove",
        subparser=auth_subparsers,
        help="removes one or more authentication records by indices",
    )
    auth_remove.add_argument(
        "indices", nargs="+", type=int,
        help="index or indices of record(s) to remove"
    )
    auth_remove.set_defaults(func=remove_auth)

    auth_remove_group = add_parser_fn(
        "remove-group",
        subparser=auth_subparsers,
        help="disassociate a group name from a set of roles",
    )
    auth_remove_group.add_argument("group", help="name of group")
    auth_remove_group.set_defaults(func=remove_group)

    auth_remove_known_host = add_parser_fn(
        "remove-known-host",
        subparser=auth_subparsers,
        help="remove entry from known-hosts file",
    )
    auth_remove_known_host.add_argument(
        "host", metavar="HOST",
        help="hostname or IP address with optional port"
    )
    auth_remove_known_host.set_defaults(func=remove_known_host)

    auth_remove_role = add_parser_fn(
        "remove-role",
        subparser=auth_subparsers,
        help="disassociate a role name from a set of capabilities",
    )
    auth_remove_role.add_argument("role", help="name of role")
    auth_remove_role.set_defaults(func=remove_role)

    auth_serverkey = add_parser_fn(
        "serverkey",
        subparser=auth_subparsers,
        help="show the serverkey for the instance",
    )
    auth_serverkey.set_defaults(func=show_serverkey)

    auth_update = add_parser_fn(
        "update",
        subparser=auth_subparsers,
        help="updates one authentication record by index",
    )
    auth_update.add_argument("index", type=int,
                             help="index of record to update")
    auth_update.set_defaults(func=update_auth)

    auth_update_group = add_parser_fn(
        "update-group",
        subparser=auth_subparsers,
        help="update group to include (or remove) given roles",
    )
    auth_update_group.add_argument("group", metavar="GROUP",
                                   help="name of group")
    auth_update_group.add_argument(
        "roles",
        nargs="*",
        metavar="ROLE",
        help="roles to append to (or remove from) the group",
    )
    auth_update_group.add_argument(
        "--remove", action="store_true",
        help="remove (rather than append) given roles"
    )
    auth_update_group.set_defaults(func=update_group)

    auth_update_role = add_parser_fn(
        "update-role",
        subparser=auth_subparsers,
        help="update role to include (or remove) given capabilities",
    )
    auth_update_role.add_argument("role", metavar="ROLE", help="name of role")
    auth_update_role.add_argument(
        "capabilities",
        nargs="*",
        metavar="CAPABILITY",
        help="capabilities to append to (or remove from) the role",
    )
    auth_update_role.add_argument(
        "--remove",
        action="store_true",
        help="remove (rather than append) given capabilities",
    )
    auth_update_role.set_defaults(func=update_role)

    auth_remote = add_parser_fn(
        "remote",
        subparser=auth_subparsers,
        help="manage pending RMQ certs and ZMQ credentials",
    )
    auth_remote_subparsers = auth_remote.add_subparsers(
        title="remote subcommands", metavar="", dest="store_commands"
    )

    auth_remote_list_cmd = add_parser_fn(
        "list",
        subparser=auth_remote_subparsers,
        help="lists approved, denied, and pending certs and credentials",
    )
    auth_remote_list_cmd.add_argument(
        "--status", help="Specify approved, denied, or pending"
    )
    auth_remote_list_cmd.set_defaults(func=list_remotes)

    auth_remote_approve_cmd = add_parser_fn(
        "approve",
        subparser=auth_remote_subparsers,
        help="approves pending or denied remote connection",
    )
    auth_remote_approve_cmd.add_argument(
        "user_id",
        help="user_id or identity of pending credential or cert to approve"
    )
    auth_remote_approve_cmd.set_defaults(func=approve_remote)

    auth_remote_deny_cmd = add_parser_fn(
        "deny",
        subparser=auth_remote_subparsers,
        help="denies pending or denied remote connection",
    )
    auth_remote_deny_cmd.add_argument(
        "user_id",
        help="user_id or identity of pending credential or cert to deny"
    )
    auth_remote_deny_cmd.set_defaults(func=deny_remote)

    auth_remote_delete_cmd = add_parser_fn(
        "delete",
        subparser=auth_remote_subparsers,
        help="approves pending or denied remote connection",
    )
    auth_remote_delete_cmd.add_argument(
        "user_id",
        help="user_id or identity of pending credential or cert to delete"
    )
    auth_remote_delete_cmd.set_defaults(func=delete_remote)

    auth_rpc = add_parser_fn(
        "rpc", subparser=auth_subparsers,
        help="Manage rpc method authorizations"
    )

    auth_rpc_subparsers = auth_rpc.add_subparsers(
        title="subcommands", metavar="", dest="store_commands"
    )
    auth_rpc_add = add_parser_fn(
        "add", subparser=auth_rpc_subparsers,
        help="adds rpc method authorizations"
    )

    auth_rpc_add.add_argument(
        "pattern",
        nargs="*",
        help="Identity of agent and method, followed "
             "by capabilities. "
             "Should be in the format: "
             "agent_id.method authorized_capability1 "
             "authorized_capability2 ...",
    )
    auth_rpc_add.set_defaults(func=add_agent_rpc_authorizations,
                              min_uuid_len=1)

    auth_rpc_remove = add_parser_fn(
        "remove",
        subparser=auth_rpc_subparsers,
        help="removes rpc method authorizations",
    )

    auth_rpc_remove.add_argument(
        "pattern",
        nargs="*",
        help="Identity of agent and method, "
             "followed by capabilities. "
             "Should be in the format: "
             "agent_id.method "
             "authorized_capability1 "
             "authorized_capability2 ...",
    )
    auth_rpc_remove.set_defaults(func=remove_agent_rpc_authorizations,
                                 min_uuid_len=1)
