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

import sys
from gevent import monkey as curious_george
curious_george.patch_all(thread=False, select=False)

from . import update_auth_file
from . import move_sqlite_files
from . import rename_config_for_agent_isolation


def main():
    # Upgrade auth file to function with dynamic rpc authorizations
    update_auth_file.main()
    print("")
    # Moves backup cache of historian (backup.sqlite files) into corresponding agent-data directory so that
    # historian agents other than sqlitehistorian, can be upgraded to latest version using
    # vctl install --force without losing cache data. vctl install --force will backup and restore
    # contents of <agent-install-dir>/<agentname-version>/<agentname-version>.agent-data directory
    # If using sqlite historian manually backup and restore sqlite historian's db before upgrading to historian version
    # 4.0.0 or later
    move_sqlite_files.main()
    print("")
    # In VOLTTRON 8.2 - secure-agent-user config has been renamed to agent-isolation-mode
    rename_config_for_agent_isolation.main()

def _main():
    """ Wrapper for main function"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == "__main__":
    _main()
