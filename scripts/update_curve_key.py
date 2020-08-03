# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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
