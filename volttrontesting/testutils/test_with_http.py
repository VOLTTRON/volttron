import pytest
import requests

from volttrontesting.utils.platformwrapper import start_wrapper_platform


def setup_instance(wrapper):
    if not wrapper.is_running():
        start_wrapper_platform(wrapper, with_http=True, with_tcp=True)


@pytest.mark.wrapper
def test_can_start_webserver(get_volttron_instances):
    wrapper = get_volttron_instances(1, False)
    setup_instance(wrapper)
    assert requests.get(wrapper.discovery_address).ok