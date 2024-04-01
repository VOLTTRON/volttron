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

from volttron.platform.agent import utils
from volttron.platform.auth.certs import Certs

def create_ssl_keypair(opts):
    fq_identity = utils.get_fq_identity(opts.identity)
    certs = Certs()
    certs.create_signed_cert_files(fq_identity)


def export_pkcs12_from_identity(opts):
    fq_identity = utils.get_fq_identity(opts.identity)

    certs = Certs()
    certs.export_pkcs12(fq_identity, opts.outfile)

def add_certs_parser(add_parser_fn):
    cert_cmds = add_parser_fn("certs", help="manage certificate creation")

    certs_subparsers = cert_cmds.add_subparsers(
        title="subcommands", metavar="", dest="store_commands"
    )

    create_ssl_keypair_cmd = add_parser_fn(
        "create-ssl-keypair", subparser=certs_subparsers,
        help="create a ssl keypair."
    )

    create_ssl_keypair_cmd.add_argument(
        "identity",
        help="Create a private key and cert for the given identity signed by "
             "the root ca of this platform.",
    )
    create_ssl_keypair_cmd.set_defaults(func=create_ssl_keypair)

    export_pkcs12 = add_parser_fn(
        "export-pkcs12",
        subparser=certs_subparsers,
        help="create a PKCS12 encoded file containing private and public key "
             "from an agent. "
             "this function is useful to create a java key store using a p12 "
             "file.",
    )
    export_pkcs12.add_argument("identity",
                               help="identity of the agent to export")
    export_pkcs12.add_argument("outfile",
                               help="file to write the PKCS12 file to")
    export_pkcs12.set_defaults(func=export_pkcs12_from_identity)
