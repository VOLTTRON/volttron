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
from volttron.platform.vip import pubsubservice
from volttron.platform.vip.pubsubservice import (MAX_PLATFORM_MAP_PAIRS,
                                                 PubSubService)
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


def deliver(subsystem, peer, args, msg_id="", user=""):
    message = SimpleNamespace(peer=peer, user=user, id=msg_id,
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


# A subscriber callback can read the user the router delivered the publish for.

@pytest.fixture
def user_seen(agent_pubsub_subsystem):
    seen = []
    agent_pubsub_subsystem._add_subscription(
        "users", lambda *args: seen.append(
            (args[1], agent_pubsub_subsystem.delivered_user())), "")
    return seen


def user_args(sender="victim"):
    return ["publish", "users/x", dict(sender=sender, bus="", headers={},
                                       message="m")]


def test_a_callback_reads_the_user_of_the_delivered_publish(
        agent_pubsub_subsystem, user_seen):
    deliver(agent_pubsub_subsystem, "", user_args("victim"), user="attacker")
    assert user_seen == [("victim", "attacker")]


def test_each_delivery_reads_its_own_user(agent_pubsub_subsystem, user_seen):
    deliver(agent_pubsub_subsystem, "", user_args("a"), user="user.a")
    deliver(agent_pubsub_subsystem, "", user_args("b"), user="user.b")
    assert user_seen == [("a", "user.a"), ("b", "user.b")]


def test_overlapping_deliveries_each_read_their_own_user(
        agent_pubsub_subsystem):
    subsystem = agent_pubsub_subsystem
    seen = []

    def slow(peer, sender, bus, topic, headers, message):
        gevent.sleep(0.05 if sender == "first" else 0)
        seen.append((sender, subsystem.delivered_user()))

    subsystem._add_subscription("slow", slow, "")
    greenlets = []
    for sender, user in [("first", "user.1"), ("second", "user.2")]:
        msg = SimpleNamespace(
            peer="", user=user, id="", subsystem="pubsub",
            args=["publish", "slow/x", dict(sender=sender, bus="", headers={},
                                            message="m")])
        greenlets.append(subsystem._process_incoming_message(msg))
    gevent.joinall(greenlets)
    assert sorted(seen) == [("first", "user.1"), ("second", "user.2")]


def test_no_user_is_readable_outside_a_delivery(agent_pubsub_subsystem,
                                                user_seen):
    assert agent_pubsub_subsystem.delivered_user() is None
    deliver(agent_pubsub_subsystem, "", user_args(), user="attacker")
    assert agent_pubsub_subsystem.delivered_user() is None


def test_a_dropped_message_sets_no_user(agent_pubsub_subsystem, user_seen):
    deliver(agent_pubsub_subsystem, "agent.x", user_args(), user="attacker")
    assert user_seen == []
    assert agent_pubsub_subsystem.delivered_user() is None


# External publishes and lists are accepted only from a connection whose user
# the auth service mapped to a platform, and a list may name only that platform.

PUBSUB_LOGGER = "volttron.platform.vip.pubsubservice"
ROUTER_LOGGER = router_module.__name__
MAPPED = {"peer.b": ["inst-b"]}


class _ServicedRouter(platform_main.Router):
    """The real router and pub/sub service on a recording socket."""

    def _add_pubsub_peers(self, peer):
        pass

    def _drop_pubsub_peers(self, peer):
        pass


class Serviced:
    def __init__(self, enable_auth=True, protected=None):
        self.context = zmq.Context()
        self.router = _ServicedRouter(
            "ipc://@pubsub-map-test", context=self.context,
            enable_auth=enable_auth, service_notifier=None)
        self.sock = RecordingSocket()
        self.router._sender = router_module.RouterSender(self.router)
        self.routing = MagicMock()
        self.service = PubSubService(
            self.sock, protected or {}, self.routing, enable_auth=enable_auth)
        self.router.pubsub = self.service

    def send(self, op, user, *payload, sender="instance.b.1"):
        frames = [sender, "", PROTO, user, "m1", "pubsub", op, *payload]
        return self.router.handle_subsystem(frames, user)

    def publish(self, user, topic=TOPIC):
        return self.send("external_publish", user, topic,
                         dict(BODY, sender="victim"))

    def lists(self, user, payload):
        return self.send("external_list", user, payload)

    def update(self, platforms, capabilities=None, **extra):
        body = dict(capabilities=capabilities or {}, **extra)
        if platforms is not None:
            body["platforms"] = platforms
        frames = ["platform.auth", "", PROTO, "platform.auth", "m1", "pubsub",
                  "auth_update", body]
        return self.router.handle_subsystem(frames, "platform.auth")

    def stored(self):
        return dict(self.service._ext_subscriptions)

    def close(self):
        self.context.term()


@pytest.fixture
def local_name(monkeypatch):
    monkeypatch.setattr("volttron.platform.vip.pubsubservice."
                        "get_platform_instance_name", lambda: "inst-a")


@pytest.fixture
def serviced(local_name):
    built = Serviced()
    built.update(MAPPED)
    built.service._add_peer_subscription("sub.all", "", "devices",
                                         platform="all")
    yield built
    built.close()


def refusals(caplog, name=ROUTER_LOGGER):
    return [r.getMessage() for r in caplog.records
            if r.name == name and r.getMessage().startswith("Refused")]


@pytest.mark.parametrize("user", ["ghost", "", "platform", "control.connection"])
def test_an_external_publish_from_an_unmapped_user_is_refused_and_logged_once(
        serviced, caplog, user):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        for _ in range(3):
            serviced.publish(user)
    assert publishes(serviced.sock) == []
    messages = refusals(caplog)
    assert len(messages) == 1
    assert "pubsub external_publish" in messages[0]


def test_an_external_publish_from_a_mapped_user_is_delivered(
        serviced, caplog):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        serviced.publish("peer.b")
    assert recipients(serviced.sock) == ["sub.all"]
    assert refusals(caplog) == []


@pytest.mark.parametrize("user", ["ghost", "", "platform"])
def test_an_external_list_from_an_unmapped_user_stores_nothing(
        serviced, caplog, user):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        result = serviced.lists(user, {"inst-b": ["devices/"]})
    assert not result
    assert serviced.stored() == {}
    assert len(refusals(caplog)) == 1


def test_a_mapped_user_stores_the_list_for_its_own_platform(serviced):
    serviced.lists("peer.b", {"inst-b": ["devices/", ""]})
    assert serviced.stored() == {"inst-b": ["devices/", ""]}


def test_a_mapped_user_may_store_the_empty_prefix_for_its_own_platform(
        serviced):
    serviced.lists("peer.b", {"inst-b": [""]})
    assert serviced.stored() == {"inst-b": [""]}


def test_a_list_naming_another_platform_is_refused_whole_with_its_own_reason(
        serviced, caplog):
    serviced.lists("peer.b", {"inst-b": ["devices/"]})
    with caplog.at_level(logging.WARNING, logger=PUBSUB_LOGGER):
        result = serviced.lists("peer.b", {"inst-c": [""]})
    assert result[-1] is False
    assert serviced.stored() == {"inst-b": ["devices/"]}
    assert serviced.service._bad_external_lists == 1
    (line,) = [r.getMessage() for r in caplog.records
               if r.name == PUBSUB_LOGGER and r.levelno == logging.WARNING
               and "Refused" in r.getMessage()]
    assert "not mapped" in line
    assert "size limits" not in line and "not a dict" not in line
    assert "inst-c" not in line


def test_a_list_naming_two_platforms_is_refused_whole(serviced):
    serviced.lists("peer.b", {"inst-b": ["a/"], "inst-c": ["b/"]})
    assert serviced.stored() == {}
    assert serviced.service._bad_external_lists == 1


def test_a_refused_foreign_name_does_not_use_up_the_stored_total(serviced):
    for number in range(300):
        serviced.lists("peer.b", {"ghost%d" % number: []})
    serviced.lists("peer.b", {"inst-b": ["devices/"]})
    assert serviced.stored() == {"inst-b": ["devices/"]}


def test_a_malformed_list_from_a_mapped_user_keeps_the_size_reason(
        serviced, caplog):
    with caplog.at_level(logging.WARNING, logger=PUBSUB_LOGGER):
        serviced.lists("peer.b", ["inst-b"])
    (line,) = [r.getMessage() for r in caplog.records
               if r.name == PUBSUB_LOGGER and "Refused" in r.getMessage()]
    assert "not a dict" in line


# The map arrives in the auth service's update and is stored whole.

@pytest.mark.parametrize("bad", [
    None, [], ["peer.b"], {"peer.b": "inst-b"}, {"peer.b": [1]},
    {"peer.b": {"inst-b": 1}}, {"peer.b": ["inst-b"], "other": None}, "x", 5,
], ids=repr)
def test_an_update_without_a_usable_map_empties_it_and_logs_one_error(
        serviced, caplog, bad):
    with caplog.at_level(logging.ERROR, logger=PUBSUB_LOGGER):
        serviced.update(bad)
    errors = [r for r in caplog.records
              if r.name == PUBSUB_LOGGER and r.levelno == logging.ERROR]
    assert len(errors) == 1
    serviced.lists("peer.b", {"inst-b": ["devices/"]})
    serviced.publish("peer.b")
    assert serviced.stored() == {}
    assert publishes(serviced.sock) == []


def test_an_update_with_a_usable_map_logs_no_error(serviced, caplog):
    with caplog.at_level(logging.ERROR, logger=PUBSUB_LOGGER):
        serviced.update({"peer.c": ["inst-c"]})
    assert [r for r in caplog.records if r.name == PUBSUB_LOGGER] == []
    serviced.lists("peer.c", {"inst-c": ["x/"]})
    assert serviced.stored() == {"inst-c": ["x/"]}
    serviced.lists("peer.b", {"inst-b": ["x/"]})
    assert serviced.stored() == {"inst-c": ["x/"]}


def test_the_empty_user_is_refused_even_if_a_map_names_it(serviced):
    serviced.update({"": ["inst-b"]})
    serviced.publish("")
    serviced.lists("", {"inst-b": ["devices/"]})
    assert publishes(serviced.sock) == []
    assert serviced.stored() == {}


def test_an_update_keeps_the_capabilities_it_carries(serviced):
    serviced.update(MAPPED, capabilities={"holder": ["c"]})
    assert serviced.service._user_capabilities == {"holder": ["c"]}


def test_the_map_is_empty_until_the_first_update(local_name):
    fresh = Serviced()
    try:
        fresh.lists("peer.b", {"inst-b": ["devices/"]})
        assert fresh.stored() == {}
    finally:
        fresh.close()


def test_a_platform_no_longer_mapped_loses_its_stored_list(serviced):
    serviced.update({"peer.b": ["inst-b"], "peer.c": ["inst-c"]})
    serviced.lists("peer.b", {"inst-b": ["b/"]})
    serviced.lists("peer.c", {"inst-c": ["c/"]})
    serviced.update({"peer.b": ["inst-b"]})
    assert serviced.stored() == {"inst-b": ["b/"]}


def test_a_name_that_moves_to_another_user_loses_its_stored_list(serviced):
    serviced.update({"peer.b": ["inst-b"], "peer.c": ["inst-c"]})
    serviced.lists("peer.b", {"inst-b": ["b/"]})
    serviced.lists("peer.c", {"inst-c": ["c/"]})
    serviced.update({"peer.b2": ["inst-b"], "peer.c": ["inst-c"]})
    assert serviced.stored() == {"inst-c": ["c/"]}
    serviced.lists("peer.b", {"inst-b": ["old/"]})
    assert serviced.stored() == {"inst-c": ["c/"]}
    serviced.lists("peer.b2", {"inst-b": ["new/"]})
    assert serviced.stored()["inst-b"] == ["new/"]


BAD_MAPS = [
    None, [], ["peer.b"], {"peer.b": "inst-b"}, {"peer.b": [1]},
    {"peer.b": {"inst-b": 1}}, {"peer.b": ["inst-b"], "other": None}, "x", 5,
]


@pytest.mark.parametrize("bad", BAD_MAPS, ids=repr)
def test_a_refused_map_deletes_the_stored_list_of_a_mapped_platform(
        serviced, bad):
    serviced.lists("peer.b", {"inst-b": ["devices/"]})
    assert serviced.stored() == {"inst-b": ["devices/"]}
    serviced.update(bad)
    assert serviced.stored() == {}


def dropped_warnings(caplog):
    return [r.getMessage() for r in caplog.records
            if r.name == PUBSUB_LOGGER and r.levelno == logging.WARNING
            and "dropping external subscriptions" in r.getMessage()]


def test_a_deleted_list_is_logged_as_one_warning_naming_the_platform(
        serviced, caplog):
    serviced.update({"peer.b": ["inst-b"], "peer.c": ["inst-c"]})
    serviced.lists("peer.b", {"inst-b": ["b/"]})
    serviced.lists("peer.c", {"inst-c": ["c/"]})
    with caplog.at_level(logging.WARNING, logger=PUBSUB_LOGGER):
        serviced.update({"peer.b": ["inst-b"]})
        serviced.update({"peer.b": ["inst-b"]})
    (line,) = dropped_warnings(caplog)
    assert "inst-c" in line and "inst-b" not in line
    assert "returns when the peer reconnects" in line


def test_a_refused_map_logs_a_warning_for_each_deleted_list(serviced, caplog):
    serviced.lists("peer.b", {"inst-b": ["b/"]})
    with caplog.at_level(logging.WARNING, logger=PUBSUB_LOGGER):
        serviced.update(None)
    (line,) = dropped_warnings(caplog)
    assert "inst-b" in line


def test_a_map_that_keeps_every_list_logs_no_deletion_warning(
        serviced, caplog):
    serviced.lists("peer.b", {"inst-b": ["b/"]})
    with caplog.at_level(logging.WARNING, logger=PUBSUB_LOGGER):
        serviced.update(MAPPED)
    assert dropped_warnings(caplog) == []


def test_the_owner_of_a_list_is_the_user_that_wrote_it_last(serviced):
    serviced.update({"peer.b": ["inst-b"], "peer.b2": ["inst-b"]})
    serviced.lists("peer.b", {"inst-b": ["first/"]})
    serviced.lists("peer.b2", {"inst-b": ["second/"]})
    assert serviced.stored() == {"inst-b": ["second/"]}
    serviced.update({"peer.b": ["inst-b"]})
    assert serviced.stored() == {}


def test_an_unchanged_map_keeps_every_stored_list(serviced):
    serviced.lists("peer.b", {"inst-b": ["b/"]})
    serviced.update(MAPPED)
    assert serviced.stored() == {"inst-b": ["b/"]}


# With authentication disabled there is no auth service, so none of the above
# applies and external pub/sub behaves as before.

@pytest.fixture
def open_serviced(local_name):
    built = Serviced(enable_auth=False)
    built.service._add_peer_subscription("sub.all", "", "devices",
                                         platform="all")
    yield built
    built.close()


@pytest.mark.parametrize("user", ["", "ghost"])
def test_with_auth_off_an_external_publish_from_any_user_is_delivered(
        open_serviced, caplog, user):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        open_serviced.publish(user)
    assert recipients(open_serviced.sock) == ["sub.all"]
    assert refusals(caplog) == []


def test_with_auth_off_a_list_from_any_user_is_stored_for_any_name(
        open_serviced):
    open_serviced.lists("ghost", {"inst-b": ["a/"], "inst-c": [""]})
    assert open_serviced.stored() == {"inst-b": ["a/"], "inst-c": [""]}


def test_with_auth_off_the_empty_map_deletes_no_stored_list(open_serviced):
    open_serviced.lists("ghost", {"inst-b": ["a/"]})
    open_serviced.update(None)
    open_serviced.update({})
    assert open_serviced.stored() == {"inst-b": ["a/"]}


def test_with_auth_off_a_protected_topic_is_open_as_before(local_name):
    # main.py builds the service with no protected topics when auth is off.
    built = Serviced(enable_auth=False, protected={})
    try:
        built.service._add_peer_subscription("sub.a", "", "devices")
        local_publish(built.service, "agent.a", frame_user="ghost",
                      user="ghost", topic=PROTECTED)
        assert recipients(built.sock) == ["sub.a"]
        assert errors_to(built.sock, "agent.a") == []
    finally:
        built.close()


# The map has its own bound, no higher than the total the router stores.

def pairs(count):
    """A map of `count` users, each speaking for one platform."""
    return {"peer.%d" % n: ["inst-%d" % n] for n in range(count)}


def test_the_map_bound_is_no_higher_than_the_stored_total_bound():
    assert MAX_PLATFORM_MAP_PAIRS <= pubsubservice._MAX_STORED_EXTERNAL_PLATFORMS


def test_a_map_with_one_pair_too_many_is_emptied_with_one_error(
        serviced, caplog):
    with caplog.at_level(logging.ERROR, logger=PUBSUB_LOGGER):
        serviced.update(pairs(MAX_PLATFORM_MAP_PAIRS + 1))
    errors = [r.getMessage() for r in caplog.records
              if r.name == PUBSUB_LOGGER and r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "more than %d user and platform pairs" % MAX_PLATFORM_MAP_PAIRS \
        in errors[0]
    serviced.lists("peer.0", {"inst-0": ["devices/"]})
    assert serviced.stored() == {}


def test_a_map_counts_pairs_not_users(serviced, caplog):
    wide = {"peer.0": ["inst-%d" % n for n in range(MAX_PLATFORM_MAP_PAIRS + 1)]}
    with caplog.at_level(logging.ERROR, logger=PUBSUB_LOGGER):
        serviced.update(wide)
    assert len([r for r in caplog.records if r.name == PUBSUB_LOGGER]) == 1


def test_a_full_map_stores_every_mapped_platforms_own_list(serviced, caplog):
    full = pairs(MAX_PLATFORM_MAP_PAIRS)
    with caplog.at_level(logging.ERROR, logger=PUBSUB_LOGGER):
        serviced.update(full)
    assert [r for r in caplog.records if r.name == PUBSUB_LOGGER] == []
    for user, (name,) in full.items():
        serviced.lists(user, {name: ["devices/"]})
    assert serviced.stored() == {
        name: ["devices/"] for (name,) in full.values()}
