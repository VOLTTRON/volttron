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

from argparse import ArgumentParser
import os

from volttron.platform.keystore import KeyStore
from volttron.platform.vip.socket import encode_key


def read_curve_key(infile):
    key = infile.read(80)
    publickey = key[:40]
    secretkey = key[40:]
    return encode_key(publickey), encode_key(secretkey)


def update_curve_key(curve_key_path, no_warn=False):
    try:
        with open(curve_key_path, 'r') as curve_file:
            public, secret = read_curve_key(curve_file)
    except IOError as e:
        print(e)
        return

    keystore_path = os.path.join(os.path.dirname(curve_key_path), 'keystore')

    if os.path.exists(keystore_path) and not no_warn:
        response = input("{} already exists. "
                "Overwrite? [y/N]: ".format(keystore_path))
        if not response.lower().startswith('y'):
            print("Key update aborted.")
            return

    keystore = KeyStore(keystore_path, public, secret)
    print("Keys from {} have been transfered to {}".format(curve_key_path,
                                                           keystore.filename))


if __name__ == "__main__":
    parser = ArgumentParser(description="Update curve.key file (from "
            "VOLTTRON 3.5rc1) to key-store file (VOLTRON 4.0)")

    parser.add_argument('curve_key', metavar='curve-key-file',
            help='Path to curve.key file (usually $VOLTTRON_HOME/curve.key)')

    parser.add_argument('--no-warn', action='store_true',
            help='Do not show warning if keystore already exists')

    args = parser.parse_args()
    update_curve_key(args.curve_key, args.no_warn)
