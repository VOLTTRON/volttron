import os

import gevent
import pytest
import requests

from vctestutils import APITester
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL
from volttron.platform.keystore import KeyStore
from volttrontesting.utils.core_service_installs import add_volttron_central, \
    add_volttron_central_platform
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform


@pytest.fixture(params=['vc-first', 'vcp-first'])
def vc_with_vcp_tcp(request):
    """
    Adds the volttron-central-address and volttron-central-serverkey to the
    main instance configuration file before starting the platform
    """
    p = PlatformWrapper()
    start_wrapper_platform(p, with_http=True, add_local_vc_address=True)

    if request.param == 'vcp-first':
        vcp_uuid = add_volttron_central_platform(p)
        vc_uuid = add_volttron_central(p)
    else:
        vc_uuid = add_volttron_central(p)
        vcp_uuid = add_volttron_central_platform(p)

    yield p

    p.shutdown_platform()


@pytest.fixture(params=['vc-first', 'vcp-first'])
def vc_with_vcp_ipc(request):
    """

    """
    p = PlatformWrapper()
    start_wrapper_platform(p, with_http=True)

    if request.param == 'vcp-first':
        vcp_uuid = add_volttron_central_platform(p)
        vc_uuid = add_volttron_central(p)
    else:
        vc_uuid = add_volttron_central(p)
        vcp_uuid = add_volttron_central_platform(p)

    yield p

    p.shutdown_platform()


def test_autoregister_local(vc_with_vcp_ipc):
    gevent.sleep(10)

    api = APITester(vc_with_vcp_ipc.jsonrpc_endpoint)

    platforms = api.list_platforms()
    assert platforms.ok
    results = platforms.json().get('result', None)
    assert len(results) == 1


def test_autoregister_local_tcp_serverkey(vc_with_vcp_tcp):
    gevent.sleep(10)

    api = APITester(vc_with_vcp_tcp.jsonrpc_endpoint)

    platforms = api.list_platforms()
    assert platforms.ok
    results = platforms.json().get('result', None)
    assert len(results) == 1

