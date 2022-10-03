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