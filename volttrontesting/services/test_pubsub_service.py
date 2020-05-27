from volttron.platform.vip.pubsubservice import PubSubService, ProtectedPubSubTopics
from mock import Mock, MagicMock
import pytest


@pytest.fixture(params=[
                    dict(has_external_routing=True),
                    dict(has_external_routing=False)
                ])
def pubsub_service(request):
    mock_socket = Mock()
    mock_protected_topics = MagicMock()
    mock_routing_service = None
    if request.param['has_external_routing']:
        mock_routing_service = Mock()

    service = PubSubService(socket=mock_socket,
                            protected_topics=mock_protected_topics,
                            routing_service=mock_routing_service)

    parameters = dict(socket=mock_socket, protected_topics=mock_protected_topics,
                      routing_service=mock_routing_service, has_external_routing=request.param['has_external_routing'])

    yield parameters, service


def test_pubsub_routing_setup(pubsub_service):
    parameters, service = pubsub_service
    assert isinstance(service, PubSubService)
    if parameters['has_external_routing']:
        assert parameters["routing_service"] is not None
    else:
        assert parameters["routing_service"] is None


def test_handle_subsystem_not_enough_frames(pubsub_service):

    parameters, service = pubsub_service

    # Expectation currently is there are 7 frames available.
    result = service.handle_subsystem([])
    assert not result

    result = service.handle_subsystem(None)
    assert not result


def test_returns_empty_list_when_subsystem_not_specified(pubsub_service):

    parameters, service = pubsub_service
    frames = [None for x in range(7)]
    assert 7 == len(frames)
    frames[6] = "not_pubsub"
    result = service.handle_subsystem(frames)
    assert [] == result
