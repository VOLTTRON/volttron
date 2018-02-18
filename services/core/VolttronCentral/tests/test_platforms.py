import pytest
from mock import MagicMock
from volttroncentral.platforms import PlatformHandler, Platforms
from volttroncentral.agent import VolttronCentralAgent


def test_when_platform_added_disconnected():
    vc = MagicMock()
    platforms = Platforms(vc=vc)
    assert platforms
    assert len(platforms.get_platform_keys()) == 0
    assert len(platforms.get_platform_list(None, None)) == 0

    new_platform_vip = "vcp-test_platform"
    platforms.add_platform(new_platform_vip)
    assert len(platforms.get_platform_keys()) == 1
    assert len(platforms.get_platform_list(None, None)) == 1

    platform = platforms.get_platform(new_platform_vip)
    assert isinstance(platform, PlatformHandler)
    assert platform.vip_identity == new_platform_vip

    platforms.disconnect_platform(new_platform_vip)
    assert len(platforms.get_platform_list(None, None)) == 0
    assert len(platforms.get_platform_keys()) == 0


def test_platform_added_during_handle_platform_connection():

    scaneventmock = MagicMock()
    platformsmock = MagicMock()

    vc = VolttronCentralAgent()
    vc._platform_scan_event = scaneventmock
    vc._platforms = platformsmock

    vip_id = "vcp-platform1"
    vc._handle_platform_connection(vip_id)

    assert platformsmock.add_platform.called


def test_platform_scan():

    vipmock = MagicMock()
    peerlistmock = MagicMock()
    peerlistmock.return_value.get.return_value = ["vcp-1", "vcp-2"]
    vipmock.peerlist = peerlistmock
    coremock = MagicMock()

    vc = VolttronCentralAgent()
    vc.vip = vipmock
    vc.core = coremock

    # scanning of platform test starts here.
    vc._scan_platform_connect_disconnect()
    assert len(vc._platforms.get_platform_keys()) == 2
    assert "vcp-1" in vc._platforms.get_platform_keys()
    assert "vcp-2" in vc._platforms.get_platform_keys()

    assert len(vc._platforms.get_platform_list(None, None)) == 2

