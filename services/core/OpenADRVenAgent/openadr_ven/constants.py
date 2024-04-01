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

# key names for processing config file for OpenADR VEN agent
VEN_NAME = "ven_name"
VTN_URL = "vtn_url"
DEBUG = "debug"
CERT = "cert_path"
KEY = "key_path"
PASSPHRASE = "passphrase"
VTN_FINGERPRINT = "vtn_fingerprint"
SHOW_FINGERPRINT = "show_fingerprint"
CA_FILE = "ca_file"
VEN_ID = "ven_id"
DISABLE_SIGNATURE = "disable_signature"
REQUIRED_KEYS = [VEN_NAME, VTN_URL]
