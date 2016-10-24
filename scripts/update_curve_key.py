# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
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
        print e
        return

    keystore_path = os.path.join(os.path.dirname(curve_key_path), 'keystore')
    
    if os.path.exists(keystore_path) and not no_warn:
        response = raw_input("{} already exists. "
                "Overwrite? [y/N]: ".format(keystore_path))
        if not response.lower().startswith('y'):
            print "Key update aborted."
            return

    keystore = KeyStore(keystore_path)
    keystore.public = public
    keystore.secret = secret
    print "Keys from {} have been transfered to {}".format(curve_key_path, 
            keystore.filename)


if __name__ == "__main__":
    parser = ArgumentParser(description="Update curve.key file (from "
            "VOLTTRON 3.5rc1) to key-store file (VOLTRON 4.0)")
    
    parser.add_argument('curve_key', metavar='curve-key-file',
            help='Path to curve.key file (usually $VOLTTRON_HOME/curve.key)')

    parser.add_argument('--no-warn', action='store_true',
            help='Do not show warning if keystore already exists')

    args = parser.parse_args()
    update_curve_key(args.curve_key, args.no_warn)
