import pytest
import requests
import gevent

from volttrontesting.utils.platformwrapper import start_wrapper_platform
from volttrontesting.utils.skip_if import skip_if_not_encrypted


@pytest.mark.wrapper
def test_can_start_webserver(get_volttron_instances):
    wrapper = get_volttron_instances(1, False)

    skip_if_not_encrypted(get_volttron_instances.param == 'encrypted')
    start_wrapper_platform(wrapper, with_http=True, with_tcp=True)

    gevent.sleep(0.5)
    assert requests.get(wrapper.discovery_address).ok