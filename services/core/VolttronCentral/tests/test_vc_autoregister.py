import os

import gevent
import pytest

import volttron.platform.jsonapi as jsonapi
from volttron.platform.agent.known_identities import (CONFIGURATION_STORE,
                                                      VOLTTRON_CENTRAL_PLATFORM)
from volttrontesting.utils.agent_additions import (add_volttron_central,
                                                   add_volttron_central_platform)
from vctestutils import APITester



@pytest.fixture(scope="module")
def multi_messagebus_vc_vcp(volttron_multi_messagebus):
    vcp_instance, vc_instance = volttron_multi_messagebus()
    assert vcp_instance.instance_name != vc_instance.instance_name
    # Handles both connections to zmq as well as connections to rmq bus.
    vc_instance.allow_all_connections()

    vcp_uuid = add_volttron_central_platform(vcp_instance)
    vc_uuid = add_volttron_central(vc_instance)

    assert vcp_uuid
    assert vc_uuid

    print("VC LIST AGENTS: {}".format(vc_instance.list_agents()))
    print("VCP LIST AGENTS: {}".format(vcp_instance.list_agents()))

    # Update vcp_config store to add the volttron-central-address from vc to the
    # config store
    config = jsonapi.dumps({'volttron-central-address': vc_instance.bind_web_address})
    capabilities = {'edit_config_store': {'identity': VOLTTRON_CENTRAL_PLATFORM}}
    vcp_instance.add_capabilities(vcp_instance.dynamic_agent.core.publickey, capabilities)
    vcp_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                            "manage_store",
                                            VOLTTRON_CENTRAL_PLATFORM,
                                            "config",
                                            config,
                                            "json").get()
    # "manage_store", opts.identity, opts.name, file_contents, config_type = opts.config_type

    yield vcp_instance, vc_instance, vcp_uuid

    vcp_instance.remove_agent(vcp_uuid)
    vc_instance.remove_agent(vc_uuid)

@pytest.mark.timeout(360)
def test_able_to_register_unregister(multi_messagebus_vc_vcp):
    vcp_instance, vc_instance, vcp_uuid = multi_messagebus_vc_vcp

    apitester = APITester(vc_instance)

    platforms = apitester.list_platforms()
    assert vc_instance.is_running()
    assert vcp_instance.is_running()
    gevent.sleep(7)
    assert len(platforms) == 1
    platform = platforms[0]

    assert platform['name'] == vcp_instance.instance_name

    vcp_instance.stop_agent(vcp_uuid)

    gevent.sleep(7)
    assert not vcp_instance.is_agent_running(vcp_uuid)
#    print(vc_instance.dynamic_agent.vip.peerlist().get(timeout=10))
    platforms = apitester.list_platforms()
    assert len(platforms) == 0
