import os

import gevent
import pytest
import requests

from vctestutils import APITester
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL
from volttron.platform.keystore import KeyStore
from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.core_service_installs import add_volttron_central, \
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

    yield p

    p.shutdown_platform()


@pytest.mark.vc
@pytest.mark.skipif(os.environ.get("CI") is not None,
                    reason="On travis this is flaky, run from command line.")
def test_autoregister_external(vc_vcp_platforms):
    gevent.sleep(15)
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
@pytest.mark.timeout(300)
@pytest.mark.skipif("True", reason="4.1 to fix!")
def test_autoregister_local(both_with_vc_vcp):
    gevent.sleep(15)

    api = APITester(both_with_vc_vcp.jsonrpc_endpoint)

    platforms = api.list_platforms()
    assert len(platforms) == 1
    p = platforms[0]
    assert p['uuid']
    assert p['name'] == both_with_vc_vcp.vip_address
    assert isinstance(p['health'], dict)
    assert STATUS_GOOD == p['health']['status']


