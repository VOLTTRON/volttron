import pytest


@pytest.mark.dev
def test_correct_number_of_instances(volttron_multi_messagebus):

    source, sink = volttron_multi_messagebus

    assert sink.bind_web_address, "Sink should always have a web enabled"
    assert not source.bind_web_address, "Source should never have a web enabled"

    if source.messagebus == 'rmq':
        assert source.ssl_auth, "source must be ssl enabled for rmq"

    if sink.messagebus == 'rmq':
        assert sink.ssl_auth, "sink must be ssl enabled for rmq"


@pytest.mark.dev
def test_correct_remote_ca_specified(volttron_multi_messagebus):

    source, sink = volttron_multi_messagebus

    if sink.messagebus == 'rmq':
        assert source.requests_ca_bundle
        with open(source.requests_ca_bundle) as f:
            requests_ca_content = f.read()

        data = sink.certsobj.ca_cert(pem_encoded=True)
        assert data in requests_ca_content
        if source.messagebus == 'zmq':
            assert data == requests_ca_content

        if source.messagebus == 'rmq':
            assert data != source.certsobj.ca_cert(pem_encoded=True)
