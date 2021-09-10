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
import os
import sys
import shutil
from pathlib import Path
from gevent import monkey as curious_george
curious_george.patch_all(thread=False, select=False)

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


def get_agent_name(agent_dir_path):
    """
    Stand-alone method based off of agent_name method from AIPplatform.
    Gets the name of an agent from it's file path location.
    """

    for agent_name in agent_dir_path.iterdir():
        if agent_name.match(".dist-info"):
            return agent_name.stem

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

        agent_name = get_agent_name(agent_path)
        agent_data = agent_path.joinpath(agent_name,
                                         agent_name + '.agent-data')
        keystore_path = agent_data.joinpath('keystore.json')
        dist_info = agent_path.joinpath(agent_name,
                                        agent_name + '.dist-info')
        keystore_dest_path = dist_info.joinpath('keystore.json')

        if keystore_path.exists():
            agent_keystore = KeyStore(keystore_path)
            for entry in auth_file.read()[0]:
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
