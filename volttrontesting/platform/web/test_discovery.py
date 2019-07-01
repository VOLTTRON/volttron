import os

from volttron.platform.web import DiscoveryInfo


def test_discovery_endpoint(volttron_instance_web):
    """
    Test that the correct discovery information is returned
    :param volttron_instance_web:
    :return:
        """
    wrapper = volttron_instance_web
    if wrapper.messagebus == 'rmq':
        assert wrapper.bind_web_address.startswith('https')
        os.environ['REQUESTS_CA_BUNDLE'] = wrapper.requests_ca_bundle
    else:
        assert wrapper.bind_web_address.startswith('http')

    info = DiscoveryInfo.request_discovery_info(wrapper.bind_web_address)

    assert wrapper.bind_web_address == info.discovery_address
    assert wrapper.serverkey == info.serverkey
    assert wrapper.messagebus == info.messagebus_type
    assert wrapper.instance_name == info.instance_name
    assert wrapper.vip_address == info.vip_address
    if wrapper.messagebus == 'rmq':
        ca_cert = wrapper.certsobj.ca_cert(public_bytes=True)
        assert ca_cert == info.rmq_ca_cert
