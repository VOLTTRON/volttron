from volttrontesting.fixtures.volttron_platform_fixtures import volttron_multi_messagebus


def test_correct_number_of_instances(volttron_multi_messagebus):

    source, sink = volttron_multi_messagebus

    assert sink.bind_web_address, "Sink should always have a web enabled"
    assert not source.bind_web_address, "Source should never have a web enabled"

    if source.messagebus == 'rmq':
        assert source.ssl_auth, "source must be ssl enabled for rmq"

    if sink.messagebus == 'rmq':
        assert sink.ssl_auth, "sink must be ssl enabled for rmq"
