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

import os
import json
import logging
import pytest
import subprocess
import gevent

from volttron.platform import get_volttron_root, jsonapi, get_services_core
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM, CONFIGURATION_STORE
from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.agent_additions import add_volttron_central_platform, add_listener
from volttrontesting.utils.platformwrapper import start_wrapper_platform, PlatformWrapper

SQLITE_HISTORIAN_CONFIG = {
    "connection": {
        "type": "sqlite",
        "params": {
            "database": "{volttron_home}/data/platform.historian.sqlite"
        }
    }
}


STANDARD_GET_TIMEOUT = 30
_log = logging.getLogger(__name__)

pytest.skip("Needs to be updated based on 6.0 changes", allow_module_level=True)


@pytest.fixture(scope="module",
                params=[("zmq", False),
                        ("rmq", True)]
                )
def setup_platform(request):
    """
    Creates a single instance of VOLTTRON with a VOLTTRON Central Platform, a listener agent, and a sqlite historian
    that is a platform.historian.
    The VOLTTRON Central Platform agent is not registered with a VOLTTRON Central Platform.
    """
    vcp = PlatformWrapper(messagebus=request.param[0], ssl_auth=request.param[1])

    start_wrapper_platform(vcp, with_http=True, add_local_vc_address=True)

    assert vcp
    assert vcp.is_running()
    vcp_uuid = add_volttron_central_platform(vcp)
    print("VCP uuid: {}".format(vcp_uuid))
    # historian_config = SQLITE_HISTORIAN_CONFIG.copy()
    # historian_config['connection']['params']['database'] = vcp.volttron_home + "/data/platform.historian.sqlite"
    #
    # historian_uuid = add_sqlhistorian(vcp, config=historian_config, vip_identity='platform.historian')
    # listeneer_uuid = add_listener(vcp, vip_identity="platform.listener")

    assert vcp_uuid, "Invalid vcp uuid returned"
    assert vcp.is_agent_running(vcp_uuid), "vcp wasn't running!"

    # assert historian_uuid, "Invalid historian uuid returned"
    # assert vcp.is_agent_running(historian_uuid), "historian wasn't running!"
    #
    # assert listeneer_uuid, "Invalid listener uuid returned"
    # assert vcp.is_agent_running(listeneer_uuid), "listener wasn't running!"

    yield vcp

    print('Shutting down instance: {}'.format(vcp.volttron_home))
    if vcp.is_running():
        vcp.remove_all_agents()
        # Shutdown handles case where the platform hasn't started.
        vcp.shutdown_platform()


@pytest.fixture(scope="module")
def vc_agent(setup_platform):
    """
    Gets the a volttron central proxy agent to test with.
    The return value is a tuple with the 0th position the instances of the proxy vc agent.  The 1st position will be the
    identity of the vcp agent that vc should use as its identity for talking with the vcp instances.
    . note::

        Please note that the agent is merely a proxy (mock) type of vc agent.

    :param setup_platform:
    :return:
    """
    assert setup_platform.instance_name is not None
    agent = setup_platform.build_agent(identity='volttron.central')
    capabilities = [{'edit_config_store': {'identity': VOLTTRON_CENTRAL_PLATFORM}}]
    setup_platform.add_capabilities(agent.core.publickey, capabilities=capabilities)
    vcp_identity = None

    look_for_identity = setup_platform.instance_name + ".platform.agent"
    print("looking for identity: {}".format(look_for_identity))
    print("peerlist: {}".format(agent.vip.peerlist().get(timeout=STANDARD_GET_TIMEOUT)))
    for peer in agent.vip.peerlist().get(timeout=STANDARD_GET_TIMEOUT):
        # For vcp in this context there are two interfaces to the the connect.
        # the first is platform.agent and the second is <instancename>.platform.agent.
        if peer == look_for_identity:
            vcp_identity = peer
            break
    if vcp_identity is None:
        pytest.fail("vcp_identity was not connected to the instance.")

    yield agent, vcp_identity

    agent.core.stop(timeout=STANDARD_GET_TIMEOUT)


@pytest.mark.vcp
def test_list_agents(setup_platform, vc_agent, caplog):
    # split vc_agent into it's respective parts.
    vc, vcp_identity = vc_agent

    agent_list = vc.vip.rpc.call(vcp_identity, "list_agents").get(timeout=2)
    assert agent_list and len(agent_list) == 3
    listener_uuid = None
    try:
        listener_uuid = add_listener(setup_platform)
        agent_list = vc.vip.rpc.call(vcp_identity, "list_agents").get(timeout=2)
        assert agent_list and len(agent_list) == 4
    except Exception as e:
        _log.debug("EXCEPTION: {}".format(e.args))
    finally:
        if listener_uuid:
            setup_platform.remove_agent(listener_uuid)


@pytest.mark.vcp
def test_can_inspect_agent(setup_platform, vc_agent, caplog):
    # split vc_agent into it's respective parts.
    vc, vcp_identity = vc_agent

    output = vc.vip.rpc.call(vcp_identity, 'inspect').get(timeout=3)

    methods = output['methods']
    print("rpc methods are:")
    for method in methods:
        print(method)

    _log.debug('The methods are {}'.format(methods))
    assert 'list_agents' in methods
    assert 'start_agent' in methods
    assert 'stop_agent' in methods
    assert 'restart_agent' in methods
    assert 'agent_status' in methods
    assert 'get_devices' in methods
    # assert 'route_request' in methods
    # assert 'manage' in methods
    # assert 'unmanage' in methods
    assert 'get_health' in methods
    assert 'get_instance_uuid' in methods
    assert 'status_agents' in methods


@pytest.mark.vcp
def test_can_call_rpc_method(setup_platform, vc_agent):
    # split vc_agent into it's respective parts.
    vc, vcp_identity = vc_agent

    health = vc.vip.rpc.call(vcp_identity, 'get_health').get(timeout=STANDARD_GET_TIMEOUT)
    assert health['status'] == STATUS_GOOD


@pytest.mark.vcp
def test_can_get_version(setup_platform, vc_agent):
    # split vc_agent into it's respective parts.
    vc, vcp_identity = vc_agent

    script = "scripts/get_versions.py"
    python = "python"

    response = subprocess.check_output(args=[python, script], cwd=get_volttron_root(), universal_newlines=True)
    expected_version = None
    for line in response.split("\n"):
        agent, version = line.strip().split(',')
        if "VolttronCentralPlatform" in agent:
            expected_version = version
            break

    # Note this is using vcp because it has the version info not the vcp_identity
    version = vc.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'agent.version').get(timeout=STANDARD_GET_TIMEOUT)
    # version = setup_platform.call('agent.version', timeout=2)
    assert version is not None
    assert version == expected_version


@pytest.mark.vcp
def test_can_change_topic_map(setup_platform, vc_agent):
    vc, vcp_identity = vc_agent

    topic_map = vc.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'get_replace_map').get(timeout=STANDARD_GET_TIMEOUT)

    assert topic_map == {}

    replace_map = {
        "topic-replace-map": {
            "fudge": "ball"
        }
    }

    # now update the config store for vcp
    vc.vip.rpc.call(CONFIGURATION_STORE,
                    'manage_store',
                    VOLTTRON_CENTRAL_PLATFORM,
                    'config',
                    jsonapi.dumps(replace_map),
                    'json').get(timeout=STANDARD_GET_TIMEOUT)

    gevent.sleep(2)

    topic_map = vc.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'get_replace_map').get(timeout=STANDARD_GET_TIMEOUT)

    assert 'fudge' in topic_map
    assert topic_map['fudge'] == 'ball'

    replace_map = {
        "topic-replace-map": {
            "map2": "it"
        }
    }

    # now update the config store for vcp
    vc.vip.rpc.call(CONFIGURATION_STORE,
                    'manage_store',
                    VOLTTRON_CENTRAL_PLATFORM,
                    'config',
                    jsonapi.dumps(replace_map),
                    'json').get(timeout=STANDARD_GET_TIMEOUT)

    gevent.sleep(2)

    topic_map = vc.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'get_replace_map').get(timeout=STANDARD_GET_TIMEOUT)

    assert 'fudge' not in topic_map
    assert 'map2' in topic_map
    assert topic_map['map2'] == 'it'


@pytest.mark.vcp
def test_default_config(volttron_instance):
    """
    Test the default configuration file included with the agent
    """
    publish_agent = volttron_instance.build_agent(identity="test_agent")
    gevent.sleep(1)

    config_path = os.path.join(get_services_core("VolttronCentralPlatform"), "config")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)
    volttron_instance.install_agent(
        agent_dir=get_services_core("VolttronCentralPlatform"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")
    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD
