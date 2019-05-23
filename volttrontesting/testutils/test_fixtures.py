
from volttrontesting.fixtures.volttron_platform_fixtures import volttron_instance_web


def test_web_setup_properly(volttron_instance_web):
    instance = volttron_instance_web

    assert instance.is_running()
    assert instance.bind_web_address == instance.volttron_central_address



