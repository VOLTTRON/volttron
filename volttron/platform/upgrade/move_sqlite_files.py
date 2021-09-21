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

import sys
import shutil
from pathlib import Path
import glob
import re
from gevent import monkey as curious_george
curious_george.patch_all(thread=False, select=False)

from volttron.platform import get_home
from volttron.platform.aip import AIPplatform
from volttron.platform.instance_setup import fail_if_instance_running


def get_aip():
    """Get AIPplatform to interface with agent directories in vhome"""

    vhome = get_home()
    options = type("Options", (), dict(volttron_home=vhome))
    aip = AIPplatform(options)
    return aip


def move_historian_cache_files(aip):
    """
    Moves any keystore.json from agent-data to dist-info.
    Only applies to agents in auth file.
    """

    vhome = Path(aip.env.volttron_home)
    install_dir = vhome.joinpath("agents")
    # pattern example - (/vhome/agents/uuid/agentname-version/)(backup.sqlite)
    # pattern example - (vhome/agents/uuid/agentname-version/)(data/subdir/sqlitehistoriandb.sqlite)
    pattern = "(" + str(install_dir) + "/[^/]*/[^/]*/)(.*)"
    re_pattern = re.compile(pattern)
    # Look for all .sqlite files in installed agents
    print(f"Attempting to move backup.sqlite files in {install_dir} into corresponding agent-data directory")
    # currently this is only used for backup.sqlite
    # In 9.0 we could use the same code for *.sqlite files
    # for example ones created by sqlitetagging, topic watcher, weather etc. when we make agent-data folder default
    # agent write directory for all core agents
    glob_path = str(install_dir.joinpath("**/backup.sqlite"))
    for sqlite_file in glob.glob(glob_path, recursive=True):
        result = re_pattern.match(sqlite_file).groups()
        agent_dir = result[0]  # <volttron home>/agents/uuid/<agent name-version>
        source_file = result[1].split('/', 1)[0]  # file or directory name to be moved to agent-data folder
        source_path = str(Path(agent_dir).joinpath(source_file))
        dest_dir = aip.get_agent_data_dir(agent_path=agent_dir)
        if source_path != dest_dir:
            # if file is not already in agent-data dir
            result = shutil.move(source_path, dest_dir)

            # print from uuid dir name so that it is easy to read
            print_src = source_path.split(str(install_dir)+"/")[1]
            print_dest = result.split(str(install_dir) + "/")[1]
            print(f"Moved {print_src} to {print_dest}")


def main():
    """Upgrade auth file to function with dynamic rpc authorizations"""

    fail_if_instance_running()
    aip = get_aip()
    move_historian_cache_files(aip)
    print("Moving historian backup files complete. "
          "You can now safely upgrade historian agents other than SQLITE Historian with vctl install --force. "
          "If using using SQLite historian please back up and restore sqlite historian's db manually")


def _main():
    """ Wrapper for main function"""

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    _main()
