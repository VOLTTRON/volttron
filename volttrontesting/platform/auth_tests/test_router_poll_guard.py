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

import logging

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
from volttron.platform.vip import routingservice as routingservice_module
from volttron.platform.vip.tracking import Tracker

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

# Each message makes route() raise when nothing guards the call.
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
    "pubsub with an unknown operation": [
        "agent.x", "", "VIP1", "", "m1", "pubsub", "bogus"],
    "recipient that is a list": [
        "agent.x", '["r"]', "VIP1", "", "m1", "rpc", "body"],
    "recipient that is a dict": [
        "agent.x", '{"r": 1}', "VIP1", "", "m1", "rpc", "body"],
    "sender that is a list": [
        '["a"]', "", "VIP1", "", "m1", "ping"],
    "sender that is a dict": [
        '{"a": 1}', "", "VIP1", "", "m1", "ping"],
    "probe whose sender is a list": ['["a"]', ""],
}
GOOD = ["agent.good", "", "VIP1", "", "m2", "ping"]


def good_replied(router):
    return [m for m in router.socket.sent if m[0] == "agent.good"]


@pytest.mark.parametrize("shape", sorted(CRASH_SHAPES))
def test_a_message_that_makes_route_raise_does_not_stop_the_poll(
        router, shape):
    poll(router, arrive(router, message(*CRASH_SHAPES[shape])))


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
    assert BODY_MARKER not in record.getMessage()


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


def test_logging_frames_that_are_text_does_not_raise():
    shown = str(platform_main.FramesFormatter(
        ["agent.x", 5, zmq.Frame(b"VIP1"), ["a"]]))
    assert "agent.x" in shown and "VIP1" in shown and "5" in shown
