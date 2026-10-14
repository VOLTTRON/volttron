# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
"""Pub/sub delivery carries the publisher's authenticated user, a publish from
another platform reaches only subscribers that asked for other platforms, a
protected topic is refused for a user the router does not know, the router
drops messages with an empty sender, and an agent acts on pub/sub messages
only when the router sent them. Fake sockets record what is sent."""

import logging
from types import SimpleNamespace

import gevent
import pytest
import zmq
from mock import MagicMock

from volttron.platform import main as platform_main
from volttron.platform.vip import router as router_module
from volttron.platform.vip.agent.subsystems import pubsub as agent_pubsub
from volttron.platform.vip.agent.subsystems.pubsub import PubSub
from volttron.platform.vip.pubsubservice import PubSubService
from volttron.platform.vip.router import ORIGIN_INPROC, ORIGIN_NETWORK
from volttron.utils.frame_serialization import deserialize_frames

PROTO = "VIP1"
TOPIC = "devices/campus/unit"
PROTECTED = "devices/locked"
BODY = dict(bus="", headers={}, message="payload")


class RecordingSocket:
    def __init__(self):
        self.identity = b""
        self.sent = []

    def send_multipart(self, frames, flags=0, copy=True):
        self.sent.append(deserialize_frames(list(frames)))


def publishes(sock):
    """The publish frames delivered to subscribers, as [recipient, sender,
    proto, user, id, subsystem, op, topic, body]."""
    return [f for f in sock.sent if len(f) > 6 and f[5] == "pubsub"
            and f[6] == "publish"]


def recipients(sock):
    return sorted(f[0] for f in publishes(sock))


def errors_to(sock, peer):
    return [f for f in sock.sent if f[0] == peer and len(f) > 5
            and f[5] == "error"]


def make_service(protected=None, capabilities=None):
    sock = RecordingSocket()
    routing = MagicMock()
    service = PubSubService(sock, protected or {}, routing)
    service._user_capabilities = dict(capabilities or {})
    return service, sock, routing


def local_publish(service, sender, frame_user, user, topic=TOPIC):
    frames = [sender, "", PROTO, frame_user, "m1", "pubsub", "publish", topic,
              dict(BODY)]
    return service.handle_subsystem(frames, user)


def external_publish(service, user, topic=TOPIC, sender="victim"):
    body = dict(BODY, sender=sender)
    frames = ["instance.b.1", "", PROTO, user, "m1", "pubsub",
              "external_publish", topic, body]
    return service.handle_subsystem(frames, user)


def test_a_delivered_local_publish_carries_the_publishers_user():
    service, sock, _ = make_service()
    service._add_peer_subscription("sub.a", "", "devices")
    local_publish(service, "agent.a", frame_user="forged", user="u1")
    delivered = publishes(sock)
    assert [f[0] for f in delivered] == ["sub.a"]
    assert delivered[0][3] == "u1"
    assert delivered[0][8]["sender"] == "agent.a"


def test_a_delivered_local_publish_carries_the_users_of_each_publisher():
    service, sock, _ = make_service()
    service._add_peer_subscription("sub.a", "", "devices")
    local_publish(service, "agent.a", frame_user="u1", user="u1")
    local_publish(service, "agent.b", frame_user="u1", user="u2")
    assert [f[3] for f in publishes(sock)] == ["u1", "u2"]


def test_a_publish_from_another_platform_carries_no_user():
    service, sock, _ = make_service()
    service._add_peer_subscription("sub.all", "", "devices", platform="all")
    external_publish(service, user="platform")
    delivered = publishes(sock)
    assert [f[0] for f in delivered] == ["sub.all"]
    assert delivered[0][3] == ""
    assert delivered[0][1] == ""
    assert delivered[0][8]["sender"] == "victim"
    assert delivered[0][8]["message"] == "payload"


def test_a_publish_from_another_platform_reaches_only_all_subscribers():
    service, sock, _ = make_service()
    service._add_peer_subscription("sub.all", "", "devices", platform="all")
    service._add_peer_subscription("sub.int", "", "other", platform="internal")
    external_publish(service, user="platform")
    assert recipients(sock) == ["sub.all"]


def test_all_and_internal_subscribers_on_one_prefix_split_a_remote_publish():
    service, sock, _ = make_service()
    service._add_peer_subscription("sub.all", "", "devices", platform="all")
    service._add_peer_subscription("sub.int", "", "devices", platform="internal")
    external_publish(service, user="platform")
    assert recipients(sock) == ["sub.all"]


def test_an_internal_subscriber_alone_gets_no_remote_publish():
    service, sock, routing = make_service()
    service._add_peer_subscription("sub.int", "", "devices", platform="internal")
    external_publish(service, user="platform")
    assert publishes(sock) == []
    routing.send_external.assert_called_once()
    assert routing.send_external.call_args[0][0] == "instance.b.1"


def test_a_local_publish_still_reaches_all_and_internal_subscribers():
    service, sock, _ = make_service()
    service._add_peer_subscription("sub.all", "", "alpha", platform="all")
    service._add_peer_subscription("sub.int", "", "beta", platform="internal")
    local_publish(service, "agent.a", frame_user="u1", user="u1",
                  topic="alpha/x")
    local_publish(service, "agent.a", frame_user="u1", user="u1",
                  topic="beta/x")
    assert recipients(sock) == ["sub.all", "sub.int"]


@pytest.mark.parametrize("user", ["ghost", ""])
def test_a_protected_topic_is_refused_for_a_user_the_router_does_not_know(user):
    service, sock, _ = make_service(
        protected={"write-protect": [{"topic": PROTECTED,
                                      "capabilities": ["c"]}]},
        capabilities={"holder": ["c"]})
    service._add_peer_subscription("sub.a", "", "devices")
    local_publish(service, "agent.a", frame_user=user, user=user,
                  topic=PROTECTED)
    assert publishes(sock) == []
    assert len(errors_to(sock, "agent.a")) == 1


def test_a_protected_topic_is_refused_for_a_user_without_the_capability():
    service, sock, _ = make_service(
        protected={"write-protect": [{"topic": PROTECTED,
                                      "capabilities": ["c"]}]},
        capabilities={"weak": ["other"]})
    service._add_peer_subscription("sub.a", "", "devices")
    local_publish(service, "agent.a", frame_user="weak", user="weak",
                  topic=PROTECTED)
    assert publishes(sock) == []
    assert len(errors_to(sock, "agent.a")) == 1


def test_a_protected_topic_is_delivered_for_a_user_with_the_capability():
    service, sock, _ = make_service(
        protected={"write-protect": [{"topic": PROTECTED,
                                      "capabilities": ["c"]}]},
        capabilities={"holder": ["c"]})
    service._add_peer_subscription("sub.a", "", "devices")
    local_publish(service, "agent.a", frame_user="holder", user="holder",
                  topic=PROTECTED)
    assert recipients(sock) == ["sub.a"]
    assert errors_to(sock, "agent.a") == []


def test_a_protected_topic_is_refused_for_an_unknown_remote_user():
    service, sock, routing = make_service(
        protected={"write-protect": [{"topic": PROTECTED,
                                      "capabilities": ["c"]}]},
        capabilities={"holder": ["c"]})
    service._add_peer_subscription("sub.all", "", "devices", platform="all")
    external_publish(service, user="ghost", topic=PROTECTED)
    assert publishes(sock) == []
    routing.send_external.assert_called_once()


# The router drops a message whose sender is empty on either socket.

class RouterSocket:
    def __init__(self, identity):
        self.identity = identity
        self.sent = []

    def send_multipart(self, frames, flags=0, copy=True):
        self.sent.append(deserialize_frames(list(frames)))


class _RouterWithoutServices(platform_main.Router):
    """The real routing with the services replaced: no message reaches a
    subsystem handler."""

    def handle_subsystem(self, frames, user_id):
        return False

    def _add_pubsub_peers(self, peer):
        pass

    def _drop_pubsub_peers(self, peer):
        pass


@pytest.fixture
def router():
    context = zmq.Context()
    built = _RouterWithoutServices("ipc://@pubsub-sender-test", context=context,
                                 enable_auth=True, service_notifier=None)
    built.socket = RouterSocket(b"net-id")
    built.inproc_socket = RouterSocket(b"inproc-id")
    yield built
    context.term()


@pytest.mark.parametrize("origin", [ORIGIN_INPROC, ORIGIN_NETWORK])
def test_a_message_with_an_empty_sender_is_dropped(router, origin):
    router.route(["", "", PROTO, "", "m1", "ping"], origin)
    assert router.socket.sent == []
    assert router.inproc_socket.sent == []
    assert "" not in router._peers
    assert "" not in router._identity_sockets


def test_a_message_with_a_sender_is_still_routed(router):
    router.route(["agent.x", "", PROTO, "", "m1", "ping"], ORIGIN_INPROC)
    assert len(router.inproc_socket.sent) == 1
    assert "agent.x" in router._peers


def test_an_empty_sender_is_logged_once(router, caplog):
    caplog.set_level(logging.WARNING, logger=router_module.__name__)
    for _ in range(3):
        router.route(["", "", PROTO, "", "m1", "ping"], ORIGIN_NETWORK)
    warnings = [r for r in caplog.records
                if r.name == router_module.__name__ and "sender is empty" in
                r.getMessage()]
    assert len(warnings) == 1


# The agent acts on pub/sub messages only when the router sent them.

@pytest.fixture
def agent_pubsub_subsystem():
    core = MagicMock()
    subsystem = PubSub(core, MagicMock(), MagicMock(), MagicMock())
    subsystem.seen = []
    subsystem._add_subscription(
        "devices", lambda *args: subsystem.seen.append(args), "")
    yield subsystem


def deliver(subsystem, peer, args, msg_id=""):
    message = SimpleNamespace(peer=peer, user="", id=msg_id,
                              subsystem="pubsub", args=args)
    subsystem._handle_subsystem(message)
    while not subsystem._event_queue.empty():
        gevent.joinall([subsystem._process_incoming_message(
            subsystem._event_queue.get())])


def publish_args():
    return ["publish", TOPIC, dict(sender="victim", bus="", headers={},
                                   message="m")]


def test_the_router_publish_reaches_the_callback(agent_pubsub_subsystem):
    deliver(agent_pubsub_subsystem, "", publish_args())
    assert len(agent_pubsub_subsystem.seen) == 1
    assert agent_pubsub_subsystem.seen[0][1] == "victim"


def test_a_publish_from_another_peer_reaches_no_callback(agent_pubsub_subsystem):
    deliver(agent_pubsub_subsystem, "agent.x", publish_args())
    assert agent_pubsub_subsystem.seen == []


def test_the_router_resolves_a_pending_request(agent_pubsub_subsystem):
    result = next(agent_pubsub_subsystem._results)
    deliver(agent_pubsub_subsystem, "", ["request_response", 5], result.ident)
    assert result.ready()
    assert result.get() == 5


def test_a_request_response_from_another_peer_resolves_nothing(
        agent_pubsub_subsystem):
    result = next(agent_pubsub_subsystem._results)
    deliver(agent_pubsub_subsystem, "agent.x", ["request_response", 5],
            result.ident)
    assert not result.ready()
    assert result.ident in agent_pubsub_subsystem._results


def test_the_router_resolves_a_pending_list(agent_pubsub_subsystem):
    result = next(agent_pubsub_subsystem._results)
    deliver(agent_pubsub_subsystem, "", ["list_response", [["", "t", True]]],
            result.ident)
    assert result.get() == [["", "t", True]]


def test_a_list_response_from_another_peer_resolves_nothing(
        agent_pubsub_subsystem):
    result = next(agent_pubsub_subsystem._results)
    deliver(agent_pubsub_subsystem, "agent.x", ["list_response", []],
            result.ident)
    assert not result.ready()
    assert result.ident in agent_pubsub_subsystem._results


def test_a_message_from_another_peer_is_logged_once_per_peer(
        agent_pubsub_subsystem, caplog):
    caplog.set_level(logging.WARNING, logger=agent_pubsub.__name__)
    for peer in ["agent.x", "agent.x", "agent.y"]:
        deliver(agent_pubsub_subsystem, peer, publish_args())
    logged = [r.getMessage() for r in caplog.records
              if r.name == agent_pubsub.__name__]
    assert len(logged) == 2
    assert "agent.x" in logged[0] and "agent.y" in logged[1]


def test_dropped_message_warnings_stop_after_a_bounded_number_of_peers(
        agent_pubsub_subsystem, caplog):
    caplog.set_level(logging.WARNING, logger=agent_pubsub.__name__)
    limit = agent_pubsub._MAX_LOGGED_PEERS
    for number in range(limit + 10):
        deliver(agent_pubsub_subsystem, "agent.%d" % number, publish_args())
    logged = [r.getMessage() for r in caplog.records
              if r.name == agent_pubsub.__name__]
    assert len(logged) == limit + 1
    assert "suppressed" in logged[-1]
