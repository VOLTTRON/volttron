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
import shutil
from pathlib import Path

from volttron.platform import get_home
from volttron.platform.aip import AIPplatform
from volttron.platform.auth import AuthFile
from volttron.platform.instance_setup import fail_if_instance_running
from volttron.platform.keystore import KeyStore


def get_aip():
    """Get AIPplatform to interface with agent directories in vhome"""

    vhome = get_home()
    options = type("Options", (), dict(volttron_home=vhome))
    aip = AIPplatform(options)
    return aip


def get_agent_path(agent_dir_path, agent_dir_suffix):
    """
    Stand-alone method based off of agent_name method from AIPplatform.
    Gets the path to the agent file of the specified directory if it exists.
    """
    for agent_name in agent_dir_path.iterdir():
        try:
            for agent_subdir in agent_name.iterdir():
                agent_dir = agent_name.joinpath(
                    agent_subdir.stem + f".{agent_dir_suffix}")
                if agent_dir.exists():
                    return agent_dir
        # Ignore files that are not directories
        except NotADirectoryError:
            pass

    raise KeyError(agent_dir_path.stem)


def upgrade_old_agents(aip):
    """
    Moves any keystore.json from agent-data to dist-info.
    Only applies to agents in auth file.
    """

    vhome = Path(aip.env.volttron_home)
    agent_map = aip.get_agent_identity_to_uuid_mapping()

    auth_file = AuthFile()
    install_dir = vhome.joinpath("agents")
    for agent in agent_map:
        agent_path = install_dir.joinpath(agent_map[agent])
        try:
            agent_data = get_agent_path(agent_path, 'agent-data')
        # Skip if no agent-data exists
        except KeyError as err:
            print(f"agent-data not found for {err}")
            continue

        keystore_path = agent_data.joinpath('keystore.json')
        try:
            dist_info = get_agent_path(agent_path, 'dist-info')
        # Skip if no dist-info exists
        except KeyError as err:
            print(f"dist-info not found for {err}")
            continue
        keystore_dest_path = dist_info.joinpath('keystore.json')

        if keystore_path.exists():
            agent_keystore = KeyStore(keystore_path)
            for entry in auth_file.read()[0]:
                # Only move if agent exists in auth file
                if entry.credentials == agent_keystore.public:
                    shutil.move(str(keystore_path), str(keystore_dest_path))
                    break
    return



def get_identity_credentials(aip):
    """Returns a dictionary containing a mapping from publickey to identity"""

    agent_map = aip.get_agent_identity_to_uuid_mapping()
    agent_credential_map = {}
    for agent in agent_map:
        agent_credential = aip.get_agent_keystore(agent_map[agent]).public
        agent_credential_map[agent_credential] = agent
    return agent_credential_map


def set_auth_identities(agent_credential_map):
    """Updates auth entries' identity field in auth file based on existing agents"""

    auth_file = AuthFile()
    entries, deny_entries, groups, roles = auth_file.read()
    for entry in entries:
        for credential in agent_credential_map:
            if entry.credentials == credential:
                entry.identity = agent_credential_map[credential]
    auth_file._write(entries, deny_entries, groups, roles)
    return


def main():
    """Upgrade auth file to function with dynamic rpc authorizations"""
    vhome = Path(get_home())
    install_dir = vhome.joinpath("agents")
    if not install_dir.exists():
        print("No installed agents for auth update.")
        return
    fail_if_instance_running()
    aip = get_aip()
    upgrade_old_agents(aip)
    identity_map = get_identity_credentials(aip)
    set_auth_identities(identity_map)
    print("Auth File Update Complete!")


def _main():
    """ Wrapper for main function"""

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    _main()
