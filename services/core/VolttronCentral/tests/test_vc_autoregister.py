import os

import gevent
import pytest

import volttron.platform.agent.json as jsonapi
from volttron.platform.agent.known_identities import (CONFIGURATION_STORE,
                                                      VOLTTRON_CENTRAL_PLATFORM)
from volttrontesting.utils.agent_additions import (add_volttron_central,
                                                   add_volttron_central_platform)

from vctestutils import APITester


@pytest.fixture(scope="module")
def multi_messagebus_vc_vcp(volttron_multi_messagebus):
    vcp_instance, vc_instance = volttron_multi_messagebus
    assert vcp_instance.instance_name != vc_instance.instance_name
    vc_instance.allow_all_connections()
    if vc_instance.messagebus == 'rmq':
        os.environ['REQUESTS_CA_BUNDLE'] = vc_instance.requests_ca_bundle
        vc_instance.enable_auto_csr()
        vc_instance.web_admin_api.create_web_admin('admin', 'admin')
    vcp_uuid = add_volttron_central_platform(vcp_instance)
    vc_uuid = add_volttron_central(vc_instance)

    assert vcp_uuid
    assert vc_uuid

    print("VC LIST AGENTS: {}".format(vc_instance.list_agents()))
    print("VCP LIST AGENTS: {}".format(vcp_instance.list_agents()))

    # Update vcp_config store to add the volttron-central-address from vc to the
    # config store
    config = jsonapi.dumps({'volttron-central-address': vc_instance.bind_web_address})

    vcp_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                            "manage_store",
                                            VOLTTRON_CENTRAL_PLATFORM,
                                            "config",
                                            config,
                                            "json").get()
    # "manage_store", opts.identity, opts.name, file_contents, config_type = opts.config_type

    yield vcp_instance, vc_instance

    vcp_instance.remove_agent(vcp_uuid)
    vc_instance.remove_agent(vc_uuid)


def test_able_to_register(multi_messagebus_vc_vcp):
    gevent.sleep(10)
    vcp_instance, vc_instance = multi_messagebus_vc_vcp

    apitester = APITester(vc_instance)

    platforms = apitester.list_platforms()

    assert len(platforms) == 1
    platform = platforms[0]

    assert platform['name'] == vcp_instance.instance_name

