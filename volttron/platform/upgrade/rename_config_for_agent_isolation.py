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
import os.path
import sys

from volttron.platform.instance_setup import fail_if_instance_running
from volttron.platform import get_home


def rename_config():
    """Check if configuration 'secure-agent-users' configuration exists and if so rename to
       agent-isolation-mode"""
    config_path = os.path.join(get_home(), "config")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            data = f.read()
        data = data.replace('secure-agent-users', 'agent-isolation-mode')
        with open(config_path, 'w') as f:
            f.write(data)


def main():
    """Check if configuration 'secure-agent-users' configuration exists and if so rename to
       agent-isolation-mode"""
    fail_if_instance_running()
    rename_config()
    print("Checked for secure-agent-users configuration")


def _main():
    """ Wrapper for main function"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    _main()
