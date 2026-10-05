"""Only the agent that registered a websocket can replace, remove or send on it,
and removing an agent's routes also removes its websockets."""

from unittest.mock import MagicMock

import pytest

from volttrontesting.platform.web.conftest import set_caller

ENDPOINT = '/probe/ws'


@pytest.fixture()
def owned(web_service):
    """a's websocket with one connected client."""
    set_caller(web_service, 'a')
    web_service.register_websocket(ENDPOINT)
    client = MagicMock()
    web_service.appContainer.endpoint_clients[ENDPOINT].add(('a', client))
    return web_service, client


def test_another_agent_cannot_replace_a_websocket(owned):
    service, client = owned
    set_caller(service, 'b')
    with pytest.raises(PermissionError):
        service.register_websocket(ENDPOINT)
    assert service.appContainer._wsregistry[ENDPOINT] == 'a'
    assert service.appContainer.endpoint_clients[ENDPOINT] == {('a', client)}


def test_another_agent_cannot_remove_a_websocket(owned):
    service, client = owned
    set_caller(service, 'b')
    with pytest.raises(PermissionError):
        service.unregister_websocket(ENDPOINT)
    assert service.appContainer._wsregistry[ENDPOINT] == 'a'
    assert client.close.call_count == 0


def test_another_agent_cannot_send_on_a_websocket(owned):
    service, client = owned
    set_caller(service, 'b')
    with pytest.raises(PermissionError):
        service.websocket_send(ENDPOINT, 'from b')
    assert client.send.call_count == 0


def test_owner_sends_to_its_clients(owned):
    service, client = owned
    service.websocket_send(ENDPOINT, 'from a')
    client.send.assert_called_once_with('from a')


def test_owner_may_register_its_websocket_again(owned):
    service, client = owned
    service.register_websocket(ENDPOINT)
    assert service.appContainer._wsregistry[ENDPOINT] == 'a'
    assert service.appContainer.endpoint_clients[ENDPOINT] == {('a', client)}


def test_owner_removes_its_websocket(owned):
    service, client = owned
    service.unregister_websocket(ENDPOINT)
    client.close.assert_called_once()
    assert ENDPOINT not in service.appContainer._wsregistry
    assert ENDPOINT not in service.appContainer.endpoint_clients


def test_removing_an_unknown_websocket_does_nothing(owned):
    service, client = owned
    service.unregister_websocket('iam/token')
    assert service.appContainer._wsregistry == {ENDPOINT: 'a'}
    assert client.close.call_count == 0


def test_sending_on_an_unknown_websocket_sends_nothing(owned):
    service, client = owned
    service.websocket_send('/probe/other', 'from a')
    assert client.send.call_count == 0


def test_user_must_be_the_peer_to_remove_or_send(owned):
    service, client = owned
    set_caller(service, 'a', peer='b')
    with pytest.raises(PermissionError):
        service.unregister_websocket(ENDPOINT)
    with pytest.raises(PermissionError):
        service.websocket_send(ENDPOINT, 'from b')
    with pytest.raises(PermissionError):
        service.unregister_all_agent_routes()
    assert service.appContainer._wsregistry == {ENDPOINT: 'a'}
    assert client.close.call_count == 0
    assert client.send.call_count == 0


def test_unregister_all_removes_only_the_callers_websockets(owned):
    service, client = owned
    set_caller(service, 'b')
    service.register_websocket('/other/ws')
    other_client = MagicMock()
    service.appContainer.endpoint_clients['/other/ws'].add(('b', other_client))

    set_caller(service, 'a')
    service.unregister_all_agent_routes()

    assert service.appContainer._wsregistry == {'/other/ws': 'b'}
    client.close.assert_called_once()
    assert other_client.close.call_count == 0
