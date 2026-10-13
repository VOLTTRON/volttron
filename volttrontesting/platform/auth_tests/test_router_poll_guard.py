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
"""A message that makes the router raise is dropped and logged, and the router
keeps polling. A quit still stops it. Fake sockets stand in for zmq, and the
real routing, pub/sub and external RPC services handle the messages."""

import json
import logging
from collections import defaultdict

import pytest
import zmq

from volttron.platform import main as platform_main
from volttron.platform.vip import router as router_module
from volttron.platform.vip.externalrpcservice import ExternalRPCService
from volttron.platform.vip.pubsubservice import PubSubService
from volttron.platform.vip.router import (ORIGIN_INPROC, ORIGIN_NETWORK,
                                          RouterSender, UNROUTABLE, ERROR,
                                          INCOMING, OUTGOING)
from volttron.platform.vip.routingservice import (
    RoutingService, STATUS_CONNECTED, STATUS_CONNECTING, STATUS_DISCONNECTED)
from volttron.platform.vip import pubsubservice as pubsubservice_module
from volttron.platform.vip import routingservice as routingservice_module
from volttron.platform.vip.tracking import Tracker
from volttron.utils.frame_serialization import (deserialize_frames,
                                                serialize_frames)

ROUTER_LOGGER = router_module.__name__
BODY_MARKER = "BODYMARKER-5678"


class Raw:
    """A received frame: its bytes, and the User-Id of its connection."""

    def __init__(self, data, user=None):
        self.bytes = data if isinstance(data, bytes) else data.encode()
        self._user = user

    def get(self, name):
        if self._user is None:
            raise zmq.ZMQError(zmq.EINVAL)
        return {"User-Id": self._user}[name]


def message(*parts, user="u1"):
    return [Raw(p, user if i == 0 else None) for i, p in enumerate(parts)]


class FakeSocket:
    def __init__(self, name, inbox=()):
        self.name = name
        self.identity = b""
        self.sent = []
        self.inbox = list(inbox)
        self.closed = False

    def recv_multipart(self, copy=True):
        return self.inbox.pop(0)

    def send_multipart(self, frames, flags=0, copy=True):
        self.sent.append([bytes(getattr(f, "bytes", f)).decode("latin-1")
                          for f in frames])

    def close(self, linger=None):
        self.closed = True


class FakePoller:
    """Hands out one scripted poll result per call."""

    def __init__(self, results):
        self.results = list(results)

    def poll(self):
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _Router(platform_main.Router):
    def _add_pubsub_peers(self, peer):
        pass

    def _drop_pubsub_peers(self, peer):
        pass


@pytest.fixture
def context():
    ctx = zmq.Context()
    yield ctx
    ctx.term()


@pytest.fixture
def router(context):
    router = _Router("ipc://@router-poll-guard-test", context=context,
                     enable_auth=True, service_notifier=None)
    router.socket = FakeSocket("network")
    router.inproc_socket = FakeSocket("in-process")
    sender = RouterSender(router)
    router._sender = sender
    routing = RoutingService(sender, context, zmq.Socket, None, [], "inst-a")
    router._ext_routing = routing
    router.pubsub = PubSubService(sender, {}, routing)
    router.ext_rpc = ExternalRPCService(sender, routing)
    return router


def poll(router, *scripted):
    router._poller = FakePoller(scripted)
    for _ in scripted:
        router.poll_sockets()


def arrive(router, *messages, on="socket"):
    sock = getattr(router, on)
    sock.inbox.extend(messages)
    return {sock: zmq.POLLIN}


VIP = ["VIP1", "", "m1"]

# Each message makes an unguarded route() raise, which
# test_these_shapes_make_an_unguarded_route_raise checks.
CRASH_SHAPES = {
    "external_rpc with too few frames": ["agent.x", "", "VIP1", "", "m1",
                                         "external_rpc", "send_peer"],
    "external_rpc send_peer with a text body": [
        "agent.x", "", "VIP1", "", "m1", "external_rpc", "send_peer", "text"],
    "external_rpc send_platform with a text body": [
        "agent.x", "", "VIP1", "", "m1", "external_rpc", "send_platform",
        "text"],
    "pubsub publish with a text body": [
        "agent.x", "", "VIP1", "", "m1", "pubsub", "publish", "t", "text"],
    "recipient that is a list": [
        "agent.x", '["r"]', "VIP1", "", "m1", "rpc", "body"],
    "recipient that is a dict": [
        "agent.x", '{"r": 1}', "VIP1", "", "m1", "rpc", "body"],
}

# These once crashed the router. route() now drops them without raising, so
# the guard is not what protects against them.
QUIET_SHAPES = {
    "pubsub with an unknown operation": [
        "agent.x", "", "VIP1", "", "m1", "pubsub", "bogus"],
    "sender that is a list": ['["a"]', "", "VIP1", "", "m1", "ping"],
    "sender that is a dict": ['{"a": 1}', "", "VIP1", "", "m1", "ping"],
    "probe whose sender is a list": ['["a"]', ""],
}
GOOD = ["agent.good", "", "VIP1", "", "m2", "ping"]


def good_replied(router):
    return [m for m in router.socket.sent if m[0] == "agent.good"]


@pytest.mark.parametrize("shape", sorted(CRASH_SHAPES))
def test_these_shapes_make_an_unguarded_route_raise(router, shape):
    with pytest.raises(Exception):
        router.route(deserialize_frames(message(*CRASH_SHAPES[shape])),
                     ORIGIN_NETWORK)


@pytest.mark.parametrize("shape", sorted(QUIET_SHAPES))
def test_these_shapes_are_dropped_by_route_without_raising(router, shape):
    router.route(deserialize_frames(message(*QUIET_SHAPES[shape])),
                 ORIGIN_NETWORK)
    assert router.socket.sent == [] and router.inproc_socket.sent == []


@pytest.mark.parametrize("shape", sorted(CRASH_SHAPES))
def test_a_message_that_makes_route_raise_does_not_stop_the_poll(
        router, shape):
    poll(router, arrive(router, message(*CRASH_SHAPES[shape])))
    assert sum(router._drop_counts.values()) == 1


@pytest.mark.parametrize("shape", sorted(CRASH_SHAPES))
def test_the_next_message_is_still_routed(router, shape):
    poll(router,
         arrive(router, message(*CRASH_SHAPES[shape])),
         arrive(router, message(*GOOD, user="u2")))
    (reply,) = good_replied(router)
    assert reply[5:7] == ["ping", "pong"]


def test_a_bad_message_does_not_stop_the_rest_of_the_same_poll(router):
    ready = arrive(router, message(*CRASH_SHAPES["recipient that is a list"]))
    ready.update(arrive(router, message(*GOOD), on="inproc_socket"))
    poll(router, ready)
    (reply,) = [m for m in router.inproc_socket.sent if m[0] == "agent.good"]
    assert reply[5:7] == ["ping", "pong"]


@pytest.mark.parametrize("shape", [
    "recipient that is a list", "external_rpc send_peer with a text body",
    "pubsub publish with a text body"])
def test_a_bad_in_process_message_does_not_stop_the_poll(router, shape):
    poll(router,
         arrive(router, message(*CRASH_SHAPES[shape]), on="inproc_socket"),
         arrive(router, message(*GOOD), on="inproc_socket"))
    (reply,) = [m for m in router.inproc_socket.sent if m[0] == "agent.good"]
    assert reply[5:7] == ["ping", "pong"]


def test_a_failure_is_logged_once_per_sender_and_type_without_the_body(
        router, caplog):
    def bad(sender, body=BODY_MARKER):
        return message(sender, "", "VIP1", "", "m1", "external_rpc",
                       "send_peer", body)

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        for _ in range(3):
            poll(router, arrive(router, bad("agent.x")))
        poll(router, arrive(router, bad("agent.y")))
        poll(router, arrive(router, message(
            "agent.x", "", "VIP1", "", "m1", "external_rpc", "send_peer")))
    records = [r for r in caplog.records if r.name == ROUTER_LOGGER]
    messages = [r.getMessage() for r in records]
    assert len(messages) == 3, messages
    assert "agent.x" in messages[0] and "TypeError" in messages[0]
    assert "agent.y" in messages[1] and "TypeError" in messages[1]
    assert "agent.x" in messages[2] and "ValueError" in messages[2]
    assert all(BODY_MARKER not in m for m in messages)
    assert all(r.exc_info is None for r in records)


def test_a_sender_that_cannot_be_a_set_key_is_logged_without_raising(
        router, caplog):
    def fail(*args, **kwargs):
        raise ValueError(BODY_MARKER)

    router.route = fail
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        poll(router, arrive(router, message('["a"]', "", "VIP1", "", "m1",
                                            "rpc")))
    (record,) = [r for r in caplog.records if r.name == ROUTER_LOGGER]
    assert "ValueError" in record.getMessage()
    assert BODY_MARKER not in record.getMessage()


def test_an_unreadable_message_is_dropped_and_logged(
        router, caplog, monkeypatch):
    def fail(frames):
        raise ValueError(BODY_MARKER)

    monkeypatch.setattr(platform_main, "deserialize_frames", fail)
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        poll(router, arrive(router, message("agent.x")))
    (record,) = [r for r in caplog.records if r.name == ROUTER_LOGGER]
    assert "ValueError" in record.getMessage()
    assert "'<unreadable>'" in record.getMessage()
    assert BODY_MARKER not in record.getMessage()
    assert router._logged_senders == {"route failed ValueError":
                                      {"<unreadable>"}}


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_an_exception_that_is_not_an_error_still_leaves_the_loop(router, exc):
    def stop(*args, **kwargs):
        raise exc()

    router.route = stop
    with pytest.raises(exc):
        poll(router, arrive(router, message(*GOOD)))


def test_quit_from_control_still_stops_the_platform(router):
    router._ext_routing.close_external_connections = lambda: None
    quit_message = message("control", "", "VIP1", "", "m1", "quit")
    with pytest.raises(KeyboardInterrupt):
        poll(router, arrive(router, quit_message, on="inproc_socket"))
    assert router.socket.closed and router.inproc_socket.closed


def test_a_zmq_error_in_the_poll_is_logged_and_the_loop_goes_on(
        router, caplog):
    with caplog.at_level(logging.ERROR, logger=platform_main.__name__):
        poll(router,
             zmq.ZMQError(zmq.EAGAIN),
             arrive(router, message(*GOOD, user="u2")))
    assert any("polling" in r.getMessage() for r in caplog.records
               if r.name == platform_main.__name__)
    assert len(good_replied(router)) == 1


@pytest.mark.parametrize("errno", [zmq.ETERM, zmq.ENOTSOCK])
def test_a_poll_error_that_cannot_recover_is_raised(router, errno):
    with pytest.raises(zmq.ZMQError):
        poll(router, zmq.ZMQError(errno))


# A sender that is not text is dropped before the router records anything.

NOT_TEXT = [5, 1.5, None, ["a"], {"a": 1}, [["a"]]]


@pytest.mark.parametrize("origin", [ORIGIN_NETWORK, ORIGIN_INPROC])
@pytest.mark.parametrize("frames_after_sender", [
    ["", "VIP1", "", "m1", "ping"],
    [""],
], ids=["full message", "router probe"])
@pytest.mark.parametrize("sender", NOT_TEXT, ids=repr)
def test_a_sender_that_is_not_text_is_dropped_and_recorded_nowhere(
        router, caplog, sender, frames_after_sender, origin):
    issued = []
    router.issue = lambda topic, frames, extra=None: issued.append(
        (topic, extra))
    with caplog.at_level(logging.DEBUG, logger=ROUTER_LOGGER):
        router.route([sender] + frames_after_sender, origin)
    assert router._peers == set()
    assert router._identity_sockets == {}
    assert router._logged_senders == {}
    assert router.socket.sent == [] and router.inproc_socket.sent == []
    assert issued[-1] == (UNROUTABLE, "sender is not text")
    assert [r for r in caplog.records if r.name == ROUTER_LOGGER] == []


@pytest.mark.parametrize("frames_after_sender", [
    ["", "VIP1", "", "m1", "ping"], [""]], ids=["full message", "router probe"])
def test_a_text_sender_is_still_recorded(router, frames_after_sender):
    router.route(["agent.x"] + frames_after_sender, ORIGIN_NETWORK)
    assert router._peers == {"agent.x"}
    assert "agent.x" in router._identity_sockets


# Message statistics read the frames the router carries, which are decoded
# text on the way in and zmq frames on the way out.


@pytest.fixture
def tracked(router):
    router._tracker = Tracker()
    router._tracker.enable()
    return router


def test_a_ping_is_still_answered_and_counted_while_tracking(tracked):
    poll(tracked, arrive(tracked, message(*GOOD, user="u2")))
    (reply,) = good_replied(tracked)
    assert reply[5:7] == ["ping", "pong"]
    stats = tracked._tracker.stats
    assert stats["incoming"]["peer"] == {"agent.good": 1}
    assert stats["incoming"]["subsystem"] == {"ping": 1}
    assert stats["outgoing"]["peer"] == {"agent.good": 1}
    assert stats["outgoing"]["subsystem"] == {"ping": 1}


def test_a_call_to_control_is_delivered_while_tracking(tracked):
    # stats.disable travels as an ordinary call to the control agent.
    call = message("agent.x", "control", "VIP1", "", "m1", "RPC", "{}")
    poll(tracked, arrive(tracked, call))
    (delivered,) = [m for m in tracked.inproc_socket.sent if m[0] == "control"]
    assert delivered[1] == "agent.x"
    tracked._tracker.disable()
    assert tracked._tracker.enabled is False


def test_statistics_are_keyed_by_text_when_a_frame_is_not_text(tracked):
    tracked._tracker.hit(INCOMING, ["a", "", "VIP1", ["x"], "m", 5], None)
    tracked._tracker.hit(UNROUTABLE, [["a"], ""], "sender is not text")
    stats = tracked._tracker.stats
    assert stats["incoming"]["user"] == {"<not text>": 1}
    assert stats["incoming"]["subsystem"] == {"<not text>": 1}
    assert stats["unroutable"]["peer"] == {"<not text>": 1}


def test_an_error_is_counted_by_its_text_number(tracked):
    error = (zmq.Frame(b"113"), zmq.Frame(b"No route to host"))
    tracked._tracker.hit(ERROR, ["a", "b", "VIP1", "u", "m", "RPC"], error)
    assert tracked._tracker.stats["error"]["error"] == {"113": 1}
    assert tracked._tracker.stats["error"]["peer"] == {"a": 1}


def test_outgoing_zmq_frames_are_counted_by_their_text(tracked):
    frames = [zmq.Frame(p) for p in (b"agent.x", b"", b"VIP1", b"usr", b"m",
                                     b"RPC")]
    tracked._tracker.hit(OUTGOING, frames, None)
    stats = tracked._tracker.stats["outgoing"]
    assert stats["peer"] == {"agent.x": 1}
    assert stats["user"] == {"usr": 1}
    assert stats["subsystem"] == {"RPC": 1}


def test_outgoing_frames_are_decoded_in_the_wire_encoding(tracked):
    # serialize_frames writes text as ISO-8859-1, so the outgoing key must
    # match the key the same text gets on the way in.
    frames = serialize_frames(
        ["agent.\xff", "", "VIP1", "usr\xe9", "m", "sub\xfc"])
    tracked._tracker.hit(OUTGOING, frames, None)
    stats = tracked._tracker.stats["outgoing"]
    assert stats["peer"] == {"agent.\xff": 1}
    assert stats["user"] == {"usr\xe9": 1}
    assert stats["subsystem"] == {"sub\xfc": 1}


def test_a_zmq_frame_is_shown_as_its_bytes():
    shown = str(platform_main.FramesFormatter([zmq.Frame(b"VIP1"), "x"]))
    assert shown == "[b'VIP1', 'x']"


def test_logging_frames_that_are_text_does_not_raise():
    shown = str(platform_main.FramesFormatter(
        ["agent.x", 5, zmq.Frame(b"VIP1"), ["a"]]))
    assert "agent.x" in shown and "VIP1" in shown and "5" in shown


# A dropped message is visible: the subsystem is named, the traceback is kept
# at DEBUG, and every drop is counted even when its warning is suppressed.


def bad_send_peer(sender, subsystem="external_rpc"):
    return message(sender, "", "VIP1", "", "m1", subsystem, "send_peer",
                   BODY_MARKER)


def test_the_warning_names_the_subsystem_cut_to_100_characters(
        router, caplog):
    long_name = "S" * 300
    router.route = lambda *args, **kwargs: 1 / 0
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        poll(router, arrive(router, message(
            "agent.x", "", "VIP1", "", "m1", long_name, "op")))
        poll(router, arrive(router, bad_send_peer("agent.y")))
    first, second = [r.getMessage() for r in caplog.records
                     if r.name == ROUTER_LOGGER]
    assert "'" + "S" * 99 in first and "S" * 100 not in first
    assert "in subsystem 'external_rpc'" in second
    assert "ZeroDivisionError" in first


def test_the_traceback_is_kept_at_debug_and_not_in_the_warning(
        router, caplog):
    with caplog.at_level(logging.DEBUG, logger=platform_main.__name__):
        poll(router, arrive(router, bad_send_peer("agent.x")))
    (record,) = [r for r in caplog.records
                 if r.name == platform_main.__name__ and r.exc_info]
    assert record.levelno == logging.DEBUG
    assert record.exc_info[0] is TypeError
    assert "agent.x" in record.getMessage()


@pytest.mark.parametrize("frames, subsystem", [
    (["agent.x", "", "VIP1", "", "m1"], "<unknown>"),
    (["agent.x", "", "VIP1", "", "m1", "sub6"], "'sub6'"),
])
def test_the_subsystem_is_named_once_the_frame_exists(
        router, caplog, frames, subsystem):
    router.route = lambda *args, **kwargs: 1 / 0
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        poll(router, arrive(router, message(*frames)))
    (warning,) = [r.getMessage() for r in caplog.records
                  if r.name == ROUTER_LOGGER]
    assert "in subsystem %s: routing raised ZeroDivisionError" % subsystem \
        in warning


@pytest.mark.parametrize("count, expected", [
    (1, False), (9, False), (10, True), (11, False), (20, False),
    (100, True), (101, False), (110, False), (1000, True), (1010, False),
    (10000, True), (100000, True), (200000, False)])
def test_summaries_are_logged_only_at_powers_of_ten(count, expected):
    assert router_module.is_power_of_ten(count) is expected


def test_the_sender_is_the_first_argument_of_a_once_only_warning(
        router, caplog):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        router._log_once("kind", "agent.x", "Saw %r with %s", "extra")
        router._log_once("kind", "agent.x", "Saw %r with %s", "extra")
    (warning,) = [r.getMessage() for r in caplog.records]
    assert warning == "Saw 'agent.x' with extra"


def test_every_drop_is_counted_but_one_sender_is_warned_once(router, caplog):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        for _ in range(3):
            poll(router, arrive(router, bad_send_peer("agent.x")))
    assert router._drop_counts == {"route failed TypeError": 3}
    (warning,) = [r.getMessage() for r in caplog.records
                  if r.name == ROUTER_LOGGER]
    assert "(1 dropped so far)" in warning


def test_a_count_summary_is_logged_at_each_power_of_ten(router, caplog):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        for _ in range(100):
            poll(router, arrive(router, bad_send_peer("agent.x")))
    summaries = [r.getMessage() for r in caplog.records
                 if r.name == ROUTER_LOGGER and "dropped so far:" in
                 r.getMessage()]
    assert summaries == [
        "10 messages dropped so far: route failed TypeError",
        "100 messages dropped so far: route failed TypeError"]
    assert router._drop_counts["route failed TypeError"] == 100


def test_senders_past_the_warning_limit_are_still_counted(
        router, caplog, monkeypatch):
    monkeypatch.setattr(router_module, "_LOGGED_SENDERS_LIMIT", 2)
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        for n in range(5):
            poll(router, arrive(router, bad_send_peer("agent.%d" % n)))
    warned = [r.getMessage() for r in caplog.records
              if r.name == ROUTER_LOGGER and "routing raised" in
              r.getMessage()]
    assert len(warned) == 2
    assert router._drop_counts == {"route failed TypeError": 5}


def test_drops_of_different_types_are_counted_apart(router):
    poll(router, arrive(router, bad_send_peer("agent.x")))
    poll(router, arrive(router, message(
        "agent.x", "", "VIP1", "", "m1", "external_rpc", "send_peer")))
    assert router._drop_counts == {"route failed TypeError": 1,
                                   "route failed ValueError": 1}


# An external subscription list from a peer is stored only when it is a dict
# of text keys to lists of text; a bad one must not break later publishes.


def external_list(sender, payload):
    return message(sender, "", "VIP1", "", "m1", "pubsub", "external_list",
                   payload)


PUBLISH_BODY = '{"headers": {"h": 1}, "message": "payload", "bus": ""}'


def publish(router, sender="agent.p", topic="devices/a"):
    before = len(router.socket.sent)
    poll(router, arrive(router, message(
        sender, "", "VIP1", "", "m9", "pubsub", "publish", topic,
        PUBLISH_BODY, user="u9")))
    return [m for m in router.socket.sent[before:] if m[0] == sender]


def connect_platform(router, name):
    """Register a connected remote platform; return its fake socket."""
    sock = FakeSocket(name)
    router._ext_routing._instances[name] = {
        "socket": sock, "status": STATUS_CONNECTED}
    return sock


MALFORMED_LISTS = {
    "key list of numbers": '{"ghost": [1]}',
    "value a string": '{"ghost": "devices/"}',
    "value null": '{"ghost": null}',
    "value a dict": '{"ghost": {"devices/": 1}}',
    "nested list": '{"ghost": [["devices/"]]}',
    "one good one bad": '{"good": ["devices/"], "ghost": [1]}',
    "a list": '["ghost"]',
    "a number": "5",
}


def test_a_publish_is_answered_without_any_external_list(router):
    (reply,) = publish(router)
    assert reply[5:7] == ["pubsub", "request_response"]


@pytest.mark.parametrize("shape", sorted(MALFORMED_LISTS))
def test_a_malformed_external_list_is_refused_and_publishes_still_reply(
        router, caplog, shape):
    router.pubsub._ext_subscriptions["kept"] = {"kept/"}
    with caplog.at_level(logging.WARNING):
        poll(router, arrive(router, external_list(
            "agent.x", MALFORMED_LISTS[shape])))
    assert dict(router.pubsub._ext_subscriptions) == {"kept": {"kept/"}}
    (reply,) = publish(router)
    assert reply[5:7] == ["pubsub", "request_response"]
    refusals = [r for r in caplog.records if "external subscription"
                in r.getMessage()]
    assert len(refusals) == 1
    assert "ghost" not in refusals[0].getMessage()


def test_a_malformed_external_list_is_logged_once(router, caplog):
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            poll(router, arrive(router, external_list(
                "agent.x", MALFORMED_LISTS["key list of numbers"])))
    assert len([r for r in caplog.records if "external subscription"
                in r.getMessage()]) == 1
    assert router.pubsub._bad_external_lists == 3


def test_a_valid_external_list_is_stored(router, monkeypatch):
    monkeypatch.setattr(pubsubservice_module, "get_platform_instance_name",
                        lambda: "inst-a")
    poll(router, arrive(router, external_list(
        "agent.x", '{"inst-b": ["devices/", "alerts/"], "inst-c": []}')))
    assert dict(router.pubsub._ext_subscriptions) == {
        "inst-b": ["devices/", "alerts/"], "inst-c": []}


@pytest.fixture
def local_name(monkeypatch):
    monkeypatch.setattr(pubsubservice_module, "get_platform_instance_name",
                        lambda: "inst-a")


def test_a_publish_reaches_a_platform_that_listed_a_matching_prefix(
        router, local_name):
    remote = connect_platform(router, "inst-b")
    poll(router, arrive(router, external_list(
        "agent.x", '{"inst-b": ["devices/"]}')))
    (reply,) = publish(router)
    assert reply[5:7] == ["pubsub", "request_response"]
    (forwarded,) = remote.sent
    assert forwarded[4:7] == ["pubsub", "external_publish", "devices/a"]


def test_a_publish_is_not_sent_to_a_platform_with_another_prefix(
        router, local_name):
    remote = connect_platform(router, "inst-b")
    poll(router, arrive(router, external_list(
        "agent.x", '{"inst-b": ["alerts/"]}')))
    publish(router)
    assert remote.sent == []


class CountingDict(defaultdict):
    """Counts how often the stored dict is turned into text."""

    formatted = 0

    def __repr__(self):
        type(self).formatted += 1
        return super().__repr__()


def many(count, prefixes=0):
    """A JSON list: `count` platforms with `prefixes` prefixes each."""
    return json.dumps({"p%d" % n: ["x/%d" % m for m in range(prefixes)]
                       for n in range(count)})


def test_storing_a_list_does_not_format_the_stored_dict_below_debug(
        router, local_name, caplog):
    CountingDict.formatted = 0
    router.pubsub._ext_subscriptions = CountingDict(set)
    with caplog.at_level(logging.INFO, logger=pubsubservice_module.__name__):
        poll(router, arrive(router, external_list("agent.x", many(20))))
    assert len(router.pubsub._ext_subscriptions) == 20
    assert CountingDict.formatted == 0


def test_the_incoming_frames_are_not_formatted_below_debug(router, local_name,
                                                          caplog):
    CountingDict.formatted = 0
    frames = ["agent.x", "", "VIP1", "", "m1", "pubsub", "external_list",
              CountingDict(set, {"inst-b": ["devices/"]})]
    with caplog.at_level(logging.INFO, logger=pubsubservice_module.__name__):
        assert router.pubsub._update_external_subscriptions(frames) is True
    assert CountingDict.formatted == 0


def test_the_stored_list_is_logged_as_a_count_at_debug(router, local_name,
                                                      caplog):
    with caplog.at_level(logging.DEBUG, logger=pubsubservice_module.__name__):
        poll(router, arrive(router, external_list(
            "agent.x", '{"inst-b": ["devices/", "alerts/"], "inst-c": []}')))
    texts = [r.getMessage() for r in caplog.records
             if "New external list" in r.getMessage()]
    assert texts == [
        "PUBSUBSERVICE New external list for inst-b: 2 prefixes "
        "(1 platforms stored)",
        "PUBSUBSERVICE New external list for inst-c: 0 prefixes "
        "(2 platforms stored)"]


def test_a_list_of_64_platforms_is_stored(router, local_name):
    poll(router, arrive(router, external_list("agent.x", many(64))))
    assert len(router.pubsub._ext_subscriptions) == 64


def test_a_list_of_65_platforms_is_refused(router, local_name):
    router.pubsub._ext_subscriptions["kept"] = {"kept/"}
    poll(router, arrive(router, external_list("agent.x", many(65))))
    assert dict(router.pubsub._ext_subscriptions) == {"kept": {"kept/"}}
    assert router.pubsub._bad_external_lists == 1


def test_a_platform_with_1024_prefixes_is_stored(router, local_name):
    poll(router, arrive(router, external_list("agent.x", many(1, 1024))))
    assert len(router.pubsub._ext_subscriptions["p0"]) == 1024


def test_a_platform_with_1025_prefixes_is_refused(router, local_name):
    poll(router, arrive(router, external_list("agent.x", many(1, 1025))))
    assert dict(router.pubsub._ext_subscriptions) == {}
    assert router.pubsub._bad_external_lists == 1


def refusal_warnings(caplog):
    return [r.getMessage() for r in caplog.records
            if r.name == pubsubservice_module.__name__
            and r.levelno == logging.WARNING]


def test_the_refusal_warning_names_the_sender(router, caplog):
    with caplog.at_level(logging.WARNING):
        poll(router, arrive(router, external_list(
            "agent.x", MALFORMED_LISTS["a list"])))
        poll(router, arrive(router, external_list(
            "agent.y", MALFORMED_LISTS["a list"])))
        poll(router, arrive(router, external_list(
            "agent.x", MALFORMED_LISTS["a list"])))
    first, second = refusal_warnings(caplog)
    assert "'agent.x'" in first and "'agent.y'" not in first
    assert "'agent.y'" in second


def test_a_refusal_count_is_logged_at_each_power_of_ten(router, caplog):
    with caplog.at_level(logging.WARNING):
        for _ in range(100):
            poll(router, arrive(router, external_list(
                "agent.x", MALFORMED_LISTS["a list"])))
    warnings = refusal_warnings(caplog)
    assert len(warnings) == 3
    assert "10 external subscription lists refused so far" in warnings[1]
    assert "100 external subscription lists refused so far" in warnings[2]
    assert router.pubsub._bad_external_lists == 100


def test_senders_past_the_limit_are_counted_without_a_line_each(
        router, caplog, monkeypatch):
    monkeypatch.setattr(pubsubservice_module, "_LOGGED_SENDERS_LIMIT", 2)
    with caplog.at_level(logging.WARNING):
        for n in range(5):
            poll(router, arrive(router, external_list(
                "agent.%d" % n, MALFORMED_LISTS["a list"])))
    assert len(refusal_warnings(caplog)) == 2
    assert router.pubsub._bad_external_lists == 5


@pytest.mark.parametrize("payload, answer", [
    (MALFORMED_LISTS["a list"], "\x00"),
    ('{"inst-b": ["devices/"]}', "\x01"),
])
def test_the_reply_to_an_external_list_says_whether_it_was_stored(
        router, local_name, payload, answer):
    poll(router, arrive(router, external_list("agent.x", payload)))
    (reply,) = [m for m in router.socket.sent if m[0] == "agent.x"]
    assert reply[5:8] == ["pubsub", "request_response", answer]


# Things the guard and the router rules must still do.


class Odd(Exception):
    pass


def test_any_exception_subclass_from_route_is_dropped_and_polling_goes_on(
        router):
    calls = []

    def raise_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise Odd("unexpected")
        return type(router).route(router, *args, **kwargs)

    router.route = raise_once
    poll(router,
         arrive(router, message(*GOOD)),
         arrive(router, message(*GOOD, user="u2")))
    assert router._drop_counts == {"route failed Odd": 1}
    (reply,) = good_replied(router)
    assert reply[5:7] == ["ping", "pong"]


def test_an_agentstop_with_no_target_is_refused_not_dropped_by_the_guard(
        router, caplog):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        poll(router, arrive(router, message(
            "agent.x", "", "VIP1", "", "m1", "agentstop")))
    assert router._drop_counts == {}
    (warning,) = [r.getMessage() for r in caplog.records
                  if r.name == ROUTER_LOGGER]
    assert 'Refused router operation "agentstop"' in warning


def test_an_agentstop_naming_the_sender_is_allowed(router):
    router._peers.add("agent.x")
    router._peers.add("agent.y")
    poll(router, arrive(router, message(
        "agent.x", "", "VIP1", "", "m1", "agentstop", "agent.x")))
    assert "agent.x" not in router._peers and "agent.y" in router._peers


# The sockets to other platforms: poll_sockets must read what arrives on an
# outbound socket, or the level-triggered poll returns it again forever.


def test_an_outbound_platform_socket_is_read_and_its_message_discarded(
        router):
    ext = FakeSocket("outbound", inbox=[message(
        "agent.x", "", "VIP1", "", "m1", "ping")])
    router._ext_routing._vip_sockets.add(ext)
    routed = []
    router.route = lambda *args, **kwargs: routed.append(args)
    poll(router, {ext: zmq.POLLIN})
    assert ext.inbox == []
    assert routed == []
    assert router.socket.sent == [] and router.inproc_socket.sent == []
    assert router._peers == set()


# The monitor event is the only thing that marks a platform connected.


class MonitorHarness:
    def __init__(self, routing, monkeypatch):
        self.routing = routing
        self.monitor = object()
        self.connected = []
        routing._instances["inst-b"] = {
            "monitor_socket": self.monitor, "status": STATUS_CONNECTING}
        routing.register("on_connect", self.connected.append)
        self.event = None
        monkeypatch.setattr(routingservice_module, "recv_monitor_message",
                            lambda sock: {"event": self.event})

    def fire(self, event):
        self.event = event
        self.routing.handle_monitor_event(self.monitor)

    @property
    def status(self):
        return self.routing._instances["inst-b"]["status"]


@pytest.fixture
def monitored(router, monkeypatch):
    return MonitorHarness(router._ext_routing, monkeypatch)


def test_a_connect_event_marks_the_platform_connected_and_sends_subscriptions(
        monitored):
    monitored.fire(zmq.EVENT_CONNECTED)
    assert monitored.status == STATUS_CONNECTED
    assert monitored.connected == ["inst-b"]


def test_a_disconnect_event_marks_the_platform_disconnected_only(monitored):
    monitored.fire(zmq.EVENT_CONNECTED)
    monitored.fire(zmq.EVENT_DISCONNECTED)
    assert monitored.status == STATUS_DISCONNECTED
    assert monitored.connected == ["inst-b"]


def test_a_delayed_connect_event_changes_the_status_only(monitored):
    monitored.fire(zmq.EVENT_CONNECT_DELAYED)
    assert monitored.status == "CONNECTION_DELAY"
    assert monitored.connected == []


def test_a_key_that_is_not_text_is_refused(router):
    # JSON keys are always text on the wire; this reaches the check directly.
    frames = ["agent.x", "", "VIP1", "", "m1", "pubsub", "external_list",
              {5: ["devices/"]}]
    assert router.pubsub._update_external_subscriptions(frames) is False
    assert dict(router.pubsub._ext_subscriptions) == {}
