from volttrontesting.utils.webapi import WebAPI

import pytest
import gevent
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL, \
    VOLTTRON_CENTRAL_PLATFORM

from volttrontesting.utils.core_service_installs import (
    add_volttron_central, add_volttron_central_platform)
from volttrontesting.utils.platformwrapper import start_wrapper_platform


@pytest.fixture(scope="module", params=['vc_first', 'vcp_first'])
def setup_first(request, get_volttron_instances):
    wrapper = get_volttron_instances(1, False)

    request.addfinalizer(wrapper.shutdown_platform)

    if get_volttron_instances.param != 'encrypted':
        pytest.skip("Only encrypted available for this test")

    start_wrapper_platform(wrapper, with_http=True)
    if request.param == 'vc_first':
        vc_uuid = add_volttron_central(wrapper)
        vcp_uuid = add_volttron_central_platform(wrapper)
    else:
        vcp_uuid = add_volttron_central_platform(wrapper)
        vc_uuid = add_volttron_central(wrapper)

    # Sleep to guarantee that the registration has happened and all the
    # agent startup is complete.
    gevent.sleep(5)

    assert vcp_uuid and vc_uuid
    return wrapper


def test_agentlist(setup_first):
    wrapper = setup_first

    try:
        cn_vcp = wrapper.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)
        assert len(cn_vcp.call('list_agents')) == 2
    finally:
        cn_vcp.kill()


def test_discovered(setup_first):
    wrapper = setup_first

    webapi = WebAPI(wrapper.bind_web_address)
    platforms = webapi.call('list_platforms')
    assert len(platforms) == 1
    p1 = platforms[0]
    expected_keys = ("name", "uuid", "health")
    for k in expected_keys:
        assert k in p1, "Key: {} not found in platform return value".format(k)
        assert p1[k], "Key: {} on platform was not valid".format(k)

    assert wrapper.vip_address == p1['name']

    health = p1["health"]
    expected_keys = ("status", "context", "last_updated")
    for k in expected_keys:
        assert k in health, \
            "Key: {} not found on heaalth return value".format(k)

    assert health['last_updated']
    assert 'GOOD' == health['status']
    assert None is health['context']

