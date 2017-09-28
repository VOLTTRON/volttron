import os

import gevent
import pytest

from vctestutils import APITester
from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.agent_additions import add_volttron_central, \
    add_volttron_central_platform
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform


@pytest.fixture(params=["use-serverkey-publickey", "use-http"])
def vc_vcp_platforms(request):
    vc = PlatformWrapper()
    vcp = PlatformWrapper()

    # VC is setup to allow all connections
    vc.allow_all_connections()
    start_wrapper_platform(vc, with_http=True)

    if request.param == 'use-http':
        start_wrapper_platform(vcp,
                               volttron_central_address=vc.bind_web_address)
    else:
        start_wrapper_platform(vcp, volttron_central_address=vc.vip_address,
                               volttron_central_serverkey=vc.serverkey)

    vcp_uuid = add_volttron_central_platform(vcp)
    vc_uuid = add_volttron_central(vc)

    # Give the agents a chance to do stuff. Can take up to 10 seconds to
    # reconnect with vc.
    gevent.sleep(10)

    yield vc, vcp

    vc.shutdown_platform()
    vcp.shutdown_platform()


@pytest.mark.vc
@pytest.fixture(params=[
    ('vc-first', 'local'),
    ('vc-first', 'http'),
    ('vcp-first', 'local'),
    ('vcp-first', 'http')
])
def both_with_vc_vcp(request):
    """
    Adds the volttron-central-address and volttron-central-serverkey to the
    main instance configuration file before starting the platform
    """
    p = PlatformWrapper()

    if request.param[1] == 'local':
        start_wrapper_platform(p, with_http=True, add_local_vc_address=True)
    else:
        start_wrapper_platform(p, with_http=True)

    if request.param[0] == 'vcp-first':
        vcp_uuid = add_volttron_central_platform(p)
        vc_uuid = add_volttron_central(p)
    else:
        vc_uuid = add_volttron_central(p)
        vcp_uuid = add_volttron_central_platform(p)

    # Give the agents a chance to do stuff. note might take up to 10 sec
    # if the vcp is started first.
    gevent.sleep(10)
    yield p

    p.shutdown_platform()


@pytest.mark.vc
def test_autoregister_external(vc_vcp_platforms):

    vc, vcp = vc_vcp_platforms

    api = APITester(vc.jsonrpc_endpoint)

    platforms = api.list_platforms()
    assert len(platforms) == 1
    p = platforms[0]
    assert p['uuid']
    assert p['name'] == vcp.vip_address
    assert vcp.vip_address != vc.vip_address
    assert isinstance(p['health'], dict)
    assert STATUS_GOOD == p['health']['status']


@pytest.mark.vc
@pytest.mark.skipif(os.environ.get("CI") is not None,
                    reason="Flaky on travis-ci for some reason")
def test_autoregister_local(both_with_vc_vcp):

    api = APITester(both_with_vc_vcp.jsonrpc_endpoint)

    platforms = api.list_platforms()
    assert len(platforms) == 1
    p = platforms[0]
    assert p['uuid']
    assert p['name'] == both_with_vc_vcp.vip_address
    assert isinstance(p['health'], dict)
    assert STATUS_GOOD == p['health']['status']

