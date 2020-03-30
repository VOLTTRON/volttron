import pytest
import requests


@pytest.fixture
def web_bound_correctly(volttron_multi_messagebus):
    source, sink = volttron_multi_messagebus()

    assert sink.bind_web_address, "Sink should always have a web enabled"
    assert not source.bind_web_address, "Source should never have a web enabled"

    yield source, sink


def test_correct_number_of_instances(web_bound_correctly):

    source, sink = web_bound_correctly

    if source.messagebus == 'rmq':
        assert source.ssl_auth, "source must be ssl enabled for rmq"

    if sink.messagebus == 'rmq':
        assert sink.ssl_auth, "sink must be ssl enabled for rmq"


def test_correct_remote_ca_specified(web_bound_correctly):

    source, sink = web_bound_correctly

    if sink.messagebus == 'rmq':
        assert source.requests_ca_bundle
        with open(source.requests_ca_bundle) as f:
            requests_ca_content = f.read()

        data = sink.certsobj.ca_cert(public_bytes=True)
        assert data.decode('utf-8') in requests_ca_content
        if source.messagebus == 'zmq':
            assert data.decode('utf-8') == requests_ca_content

        if source.messagebus == 'rmq':
            assert data.decode('utf-8') != source.certsobj.ca_cert(public_bytes=True)


def test_can_connect_web_using_remote_platform_ca(web_bound_correctly):

    source, sink = web_bound_correctly

    # Note we are using the sources.requests_ca_bundle not the sinks ca
    # This way we know we are testing the transference from one to the other
    print("source requests_ca_bundle", source.requests_ca_bundle)
    if sink.messagebus == 'rmq':
        print("sink certs_filename", sink.certsobj.cert_file(sink.certsobj.root_ca_name))
    # these two lines enable debugging at httplib level (requests->urllib3->httplib)
    # you will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # the only thing missing will be the response.body which is not logged.
    from http.client import HTTPConnection
    HTTPConnection.debuglevel = 1
    resp = requests.get(sink.discovery_address, verify=source.requests_ca_bundle)

    assert resp.ok
    assert resp.headers['Content-Type'] == 'application/json'


def test_instance_config_matches_instance(web_bound_correctly):
    source, sink = web_bound_correctly

    def config_file_correct(instance):
        import os
        from configparser import ConfigParser

        config_file = os.path.join(instance.volttron_home, "config")
        assert os.path.isfile(config_file)
        parser = ConfigParser()
        # with open(config_file, 'rb') as cfg:
        parser.read(config_file)
        assert instance.instance_name == parser.get('volttron', 'instance-name')
        assert instance.vip_address == parser.get('volttron', 'vip-address')
        assert instance.messagebus == parser.get('volttron', 'message-bus')
        if instance.bind_web_address:
            assert instance.bind_web_address == parser.get('volttron', 'bind-web-address')
        if instance.volttron_central_address:
            assert instance.volttron_central_address == parser.get('volttron', 'volttron-central-address')

    config_file_correct(source)
    config_file_correct(sink)

