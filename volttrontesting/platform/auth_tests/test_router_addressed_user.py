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
"""Messages addressed to the router are handled with the user the router
assigned, a call relayed from another platform reaches the local agent with no
user, and each router operation that changes platform state is refused for
senders that may not perform it. Fake sockets record what is sent."""

import ast
import logging
import os

import pytest
import zmq

from volttron.platform import main as platform_main
from volttron.platform.vip import router as router_module
from volttron.platform.vip.externalrpcservice import ExternalRPCService
from volttron.platform.vip.pubsubservice import PubSubService
from volttron.platform.vip.router import (ORIGIN_INPROC, ORIGIN_NETWORK,
                                          RouterSender)
from volttron.platform.vip.routingservice import RoutingService

PROTO = "VIP1"
ROUTER_LOGGER = router_module.__name__


def text(frame):
    if isinstance(frame, bytes):
        return frame.decode("iso-8859-1")
    if hasattr(frame, "bytes"):
        return frame.bytes.decode("iso-8859-1")
    return str(frame)


class FakeFrame:
    """A received frame with the given connection properties."""

    def __init__(self, data, props=None):
        self.bytes = data if isinstance(data, bytes) else data.encode()
        self._props = props

    def get(self, name):
        if self._props is None or name not in self._props:
            raise zmq.ZMQError(zmq.EINVAL)
        return self._props[name]


class WireFrame(bytes):
    """A received frame that also compares equal to its text, as a frame
    would if the old protocol comparison were repaired."""

    def __eq__(self, other):
        if isinstance(other, str):
            return self.decode() == other
        return bytes.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = bytes.__hash__


class RecordingSocket:
    def __init__(self, name):
        self.name = name
        self.identity = b""
        self.sent = []
        self.closed = False

    def send_multipart(self, frames, flags=0, copy=True):
        self.sent.append([text(f) for f in frames])

    def close(self, linger=None):
        self.closed = True


class _GatedRouter(platform_main.Router):
    """The real router with fake sockets and the real handle_subsystem."""

    def _add_pubsub_peers(self, peer):
        pass

    def _drop_pubsub_peers(self, peer):
        pass


class _RecordingRouter(_GatedRouter):
    """Records the frames each router-addressed message reaches
    handle_subsystem with."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handled = []

    def handle_subsystem(self, frames, user_id):
        self.handled.append((list(frames), user_id))
        return False


@pytest.fixture
def context():
    ctx = zmq.Context()
    yield ctx
    ctx.term()


def build_router(context, router_class=_GatedRouter, enable_auth=True):
    router = router_class("ipc://@router-addressed-test", context=context,
                          enable_auth=enable_auth, service_notifier=None)
    router.socket = RecordingSocket("network")
    router.inproc_socket = RecordingSocket("inproc")
    router.socket.identity = b"net-id"
    router.inproc_socket.identity = b"inproc-id"
    return router


class Harness:
    """A router with the real routing, pub/sub and external RPC services, and
    its platform connection steps replaced by recorders."""

    def __init__(self, context):
        self.router = build_router(context)
        sender = RouterSender(self.router)
        self.router._sender = sender
        self.routing = RoutingService(sender, context, zmq.Socket, None, [],
                                      "inst-a")
        self.router._ext_routing = self.routing
        self.router.pubsub = PubSubService(sender, {}, self.routing)
        self.router.ext_rpc = ExternalRPCService(sender, self.routing)
        self.calls = []
        self.routing._setup_authorization = (
            lambda info: self.calls.append(("setup", info)))
        self.routing._build_connection = (
            lambda info: self.calls.append(("connect", info)))
        self.routing._update_entry = (
            lambda frames: self.calls.append(("update",)))
        self.routing._instances["b"] = {"status": "CONNECTING"}
        self.routing._onconnect_pubsub_handler = (
            lambda name: self.calls.append(("onconnect", name)))
        self.router._peers.update({"victim", "bystander"})

    def send(self, subsystem, op, sender, user, *payload):
        frames = [sender, "", PROTO, user, "m1", subsystem, op, *payload]
        return self.router.handle_subsystem(frames, user)


@pytest.fixture
def harness(context):
    return Harness(context)


# Each row: what the operation is, its payload, the senders (routing
# identity, user) that may perform it, the ones that may not, and a snapshot
# of the platform state the operation changes.
KEY_DISCOVERY_ONLY = dict(
    allowed=[("keydiscovery", "keydiscovery")],
    denied=[("agent.x", "agent.x"), ("control", "control"),
            ("keydiscovery", "u1")])
AUTH_SERVICE_ONLY = dict(
    allowed=[("platform.auth", "platform.auth")],
    denied=[("agent.x", "agent.x"), ("keydiscovery", "keydiscovery"),
            ("platform.auth", "u1")])
PLATFORM_PEER_ONLY = dict(
    allowed=[("instance.b.0.5", "u2")],
    denied=[("agent.x", "agent.x"), ("instance", "u2"),
            ("control", "control")])

OPERATIONS = {
    "setupmode_platform_connection": dict(
        subsystem="routing_table", payload=({"instance-name": "b"},),
        snapshot=lambda h: list(h.calls), **KEY_DISCOVERY_ONLY),
    "normalmode_platform_connection": dict(
        subsystem="routing_table", payload=({"instance-name": "b"},),
        snapshot=lambda h: list(h.calls), **KEY_DISCOVERY_ONLY),
    "web-addresses": dict(
        subsystem="routing_table", payload=(["http://other"],),
        snapshot=lambda h: list(h.routing._web_addresses),
        **KEY_DISCOVERY_ONLY),
    "update": dict(
        subsystem="routing_table", payload=({"vip": ["x"]},),
        snapshot=lambda h: list(h.calls),
        allowed=[],
        denied=[("agent.x", "agent.x"), ("control", "control"),
                ("keydiscovery", "keydiscovery")]),
    "hello": dict(
        subsystem="routing_table", payload=("welcome", "b"),
        snapshot=lambda h: (h.routing._instances["b"]["status"],
                            list(h.calls)),
        **PLATFORM_PEER_ONLY),
    "auth_update": dict(
        subsystem="pubsub", payload=({"capabilities": {"u": ["c"]}},),
        snapshot=lambda h: dict(h.router.pubsub._user_capabilities),
        **AUTH_SERVICE_ONLY),
    "protected_update": dict(
        subsystem="pubsub",
        payload=({"write-protect": [{"topic": "t", "capabilities": ["c"]}]},),
        snapshot=lambda h: h.router.pubsub._protected_topics.get_topic_caps(),
        **AUTH_SERVICE_ONLY),
    "send_peer": dict(
        subsystem="external_rpc", payload=({"to_peer": "agent.z"},),
        snapshot=lambda h: list(h.router.socket.sent),
        **PLATFORM_PEER_ONLY),
    "agentstop": dict(
        subsystem="agentstop", payload=("victim",),
        snapshot=lambda h: sorted(h.router._peers),
        allowed=[("victim", "victim"), ("victim", "u9"),
                 ("control", "control")],
        denied=[("bystander", "bystander"), ("agent.x", "agent.x"),
                ("control", "u1")]),
}


def refusals(caplog):
    return [r for r in caplog.records
            if r.name == ROUTER_LOGGER and r.getMessage().startswith("Refused")]


def run(harness, name, sender, user):
    spec = OPERATIONS[name]
    if name == "agentstop":
        return harness.router.handle_subsystem(
            [sender, "", PROTO, user, "m1", "agentstop", "victim"], user)
    return harness.send(spec["subsystem"], name, sender, user,
                        *spec["payload"])


def cases(key):
    return [pytest.param(name, pair, id="{}-{}-{}".format(name, *pair))
            for name, spec in OPERATIONS.items() for pair in spec[key]]


@pytest.mark.parametrize("name,pair", cases("denied"))
def test_a_disallowed_sender_changes_nothing(harness, caplog, name, pair):
    before = OPERATIONS[name]["snapshot"](harness)
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        result = run(harness, name, *pair)
    assert OPERATIONS[name]["snapshot"](harness) == before
    assert not result
    assert len(refusals(caplog)) == 1


@pytest.mark.parametrize("name,pair", cases("allowed"))
def test_an_allowed_sender_still_changes_the_state(harness, caplog, name,
                                                   pair):
    before = OPERATIONS[name]["snapshot"](harness)
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        run(harness, name, *pair)
    assert OPERATIONS[name]["snapshot"](harness) != before
    assert refusals(caplog) == []


def test_agentstop_by_an_allowed_sender_drops_only_the_named_peer(harness):
    run(harness, "agentstop", "control", "control")
    assert harness.router._peers == {"bystander"}


def test_welcome_from_a_platform_peer_marks_the_named_platform_connected(
        harness):
    run(harness, "hello", "instance.b.0.5", "u2")
    assert harness.routing._instances["b"]["status"] == "CONNECTED"
    assert harness.calls == [("onconnect", "b")]


def test_a_relayed_call_from_a_platform_peer_is_delivered_with_no_user(
        harness):
    run(harness, "send_peer", "instance.b.0.5", "u2")
    (sent,) = harness.router.socket.sent
    assert sent[0] == "agent.z"
    assert sent[3] == ""


def test_a_refusal_is_logged_once_per_sender_and_never_logs_the_body(
        harness, caplog):
    marker = "BODYMARKER-1234"
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        for _ in range(3):
            harness.send("pubsub", "auth_update", "agent.x", "agent.x",
                         {"capabilities": {marker: ["c"]}})
        harness.send("pubsub", "auth_update", "agent.y", "agent.y",
                     {"capabilities": {marker: ["c"]}})
    messages = [r.getMessage() for r in refusals(caplog)]
    assert len(messages) == 2
    assert "agent.x" in messages[0] and "agent.y" in messages[1]
    assert all(marker not in m for m in messages)
    assert all("auth_update" in m for m in messages)


def test_the_same_sender_is_logged_again_for_a_different_operation(
        harness, caplog):
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        harness.send("pubsub", "auth_update", "agent.x", "agent.x",
                     {"capabilities": {}})
        harness.send("pubsub", "protected_update", "agent.x", "agent.x",
                     {"write-protect": []})
    assert len(refusals(caplog)) == 2


def test_quit_from_control_stops_the_router(harness):
    closed = []
    harness.routing.close_external_connections = lambda: closed.append(True)
    with pytest.raises(KeyboardInterrupt):
        harness.router.handle_subsystem(
            ["control", "", PROTO, "control", "m1", "quit"], "control")
    assert closed == [True]
    assert harness.router.socket.closed
    assert harness.router.inproc_socket.closed


def test_quit_from_any_other_user_does_nothing(harness, caplog):
    # The routing identity says control but the user does not.
    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        try:
            result = harness.router.handle_subsystem(
                ["control", "", PROTO, "u1", "m1", "quit"], "u1")
        except KeyboardInterrupt:
            pytest.fail("quit from a user other than control stopped the router")
    assert not result
    assert len(refusals(caplog)) == 1


@pytest.mark.parametrize("sender", [5, None])
def test_a_sender_that_is_not_text_is_refused_without_raising(harness, sender):
    before = list(harness.router.socket.sent)
    result = harness.send("external_rpc", "send_peer", sender, "u2",
                          {"to_peer": "agent.z"})
    assert not result
    assert harness.router.socket.sent == before


@pytest.mark.parametrize("op", [{"a": 1}, ["x"], 7, None])
def test_an_operation_that_is_not_text_does_not_raise_in_the_check(
        harness, op):
    frames = ["agent.x", "", PROTO, "u1", "m1", "routing_table", op]
    harness.router.handle_subsystem(frames, "u1")
    assert harness.calls == []


@pytest.mark.parametrize("subsystem", [{"a": 1}, ["x"], 7])
def test_a_subsystem_that_is_not_text_is_left_to_the_dispatch(
        harness, subsystem):
    frames = ["agent.x", "", PROTO, "u1", "m1", subsystem, "op"]
    assert harness.router.handle_subsystem(frames, "u1") is None
    assert harness.calls == []


# C1: the user of a message addressed to the router.

def route_query(router, frame_user, origin, raw_frames=None, sender="alice"):
    frames = [sender, "", PROTO, frame_user, "m1", "query", "serverkey"]
    router.route(frames, origin, raw_frames)


def test_a_network_message_to_the_router_is_handled_with_the_zap_user(context):
    router = build_router(context, _RecordingRouter)
    raw = [FakeFrame("alice", {"User-Id": "u1"})]
    route_query(router, "control.connection", ORIGIN_NETWORK, raw)
    ((frames, user_id),) = router.handled
    assert user_id == "u1"
    assert frames[3] == "u1"


def test_a_network_peer_with_no_user_is_handled_with_the_empty_user(context):
    router = build_router(context, _RecordingRouter)
    route_query(router, "control.connection", ORIGIN_NETWORK, [FakeFrame("a")])
    ((frames, user_id),) = router.handled
    assert (user_id, frames[3]) == ("", "")


def test_an_in_process_message_to_the_router_carries_the_sender(context):
    router = build_router(context, _RecordingRouter)
    route_query(router, "control", ORIGIN_INPROC, sender="aip")
    ((frames, user_id),) = router.handled
    assert (user_id, frames[3]) == ("aip", "aip")


def test_with_auth_off_the_message_carries_the_sender(context):
    router = build_router(context, _RecordingRouter, enable_auth=False)
    route_query(router, "control", ORIGIN_NETWORK, [FakeFrame("a")])
    ((frames, user_id),) = router.handled
    assert (user_id, frames[3]) == ("alice", "alice")


def test_a_message_to_a_peer_still_carries_the_senders_user(context):
    router = build_router(context, _RecordingRouter)
    frames = ["alice", "peer.b", PROTO, "forged", "m1", "rpc", "body"]
    router.route(frames, ORIGIN_NETWORK, [FakeFrame("alice", {"User-Id": "u1"})])
    (sent,) = [m for m in router.socket.sent if m[5] == "rpc"]
    assert sent[3] == "u1"


def test_an_external_rpc_forged_user_reaches_the_agent_as_no_user(context):
    router = build_router(context)
    sender = RouterSender(router)
    routing = RoutingService(sender, context, zmq.Socket, None, [], "inst-a")
    router._ext_routing = routing
    router.ext_rpc = ExternalRPCService(sender, routing)
    frames = ["instance.b.0.5", "", PROTO, "control.connection", "m1",
              "external_rpc", "send_peer", {"to_peer": "agent.z"}]
    router.route(frames, ORIGIN_NETWORK, [FakeFrame("x", {"User-Id": "u2"})])
    (sent,) = [m for m in router.socket.sent if m[5] == "external_rpc"]
    assert sent[0] == "agent.z"
    assert sent[3] == ""


# C2

def test_a_relayed_call_carries_no_user_whatever_the_frame_held():
    out = RecordingSocket("network")
    service = ExternalRPCService(out, None)
    frames = ["instance.b.0.5", "", PROTO, "control.connection", "m1",
              "external_rpc", "send_peer", {"to_peer": "agent.z"}]
    service.handle_subsystem(frames)
    (sent,) = out.sent
    assert sent[0] == "agent.z"
    assert sent[3] == ""


# C3

def ext_frames(subsystem, body):
    return [WireFrame(x.encode()) for x in
            ("s7", PROTO, "control.connection", "m1", subsystem, body)]


class _ExtSocket(RecordingSocket):
    def __init__(self, frames):
        super().__init__("ext")
        self._frames = frames

    def recv_multipart(self, copy=True):
        return self._frames


@pytest.mark.parametrize("subsystem,body", [
    ("external_rpc", '{"to_peer": "agent.z"}'),
    ("pubsub", '{"to_peer": "agent.z"}'),
    ("routing_table", '{"to_peer": "agent.z"}'),
])
def test_ext_route_forwards_nothing_for_a_relayed_frame_shape(
        harness, subsystem, body):
    spied = []
    harness.router.pubsub.handle_subsystem = (
        lambda frames, user_id="": spied.append(("pubsub", frames)))
    harness.routing.handle_subsystem = (
        lambda frames: spied.append(("routing_table", frames)))
    harness.router.ext_route(_ExtSocket(ext_frames(subsystem, body)))
    assert harness.router.socket.sent == []
    assert harness.router.inproc_socket.sent == []
    assert spied == []


def test_ext_route_has_no_branch_past_the_route_call():
    path = platform_main.__file__
    with open(path) as fil:
        tree = ast.parse(fil.read())
    (func,) = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "ext_route"]
    statements = [s for s in func.body
                  if not (isinstance(s, ast.Expr)
                          and isinstance(s.value, ast.Constant))]
    assert [type(s).__name__ for s in statements] == ["Assign", "Expr"]


# C4: every operation the dispatch tables accept is either in OPERATIONS
# above or listed here with the reason it needs no sender check.

UNGATED = {
    # Subsystem names; the checked operations sit under them.
    "quit": "checked: only the control user",
    "query": "read-only answers",
    "pubsub": "subsystem name",
    "routing_table": "subsystem name",
    "external_rpc": "subsystem name",
    # query values are read-only.
    "addresses": "query value", "local_address": "query value",
    "serverkey": "query value", "volttron-central-address": "query value",
    "volttron-central-serverkey": "query value",
    "instance-name": "query value", "bind-web-address": "query value",
    "platform-version": "query value", "message-bus": "query value",
    "agent-monitor-frequency": "query value",
    # pubsub operations that act on the caller's own state or a response.
    "subscribe": "the caller's own subscriptions",
    "unsubscribe": "the caller's own subscriptions",
    "synchronize": "the caller's own subscriptions",
    "publish": "checked per topic against the sender's user",
    "list": "read-only",
    "error": "response handling",
    "request_response": "response handling",
    # Not part of this change; the pub/sub round covers them.
    "external_list": "left to the pub/sub change",
    "external_publish": "left to the pub/sub change",
    # Any local agent may ask the platform to relay a call.
    "send_platform": "relaying an agent's own call to a connected platform",
}

DISPATCH_TABLES = [
    ("main.py", "Router"),
    ("vip/routingservice.py", "RoutingService"),
    ("vip/pubsubservice.py", "PubSubService"),
    ("vip/externalrpcservice.py", "ExternalRPCService"),
]


def dispatched_names(path, class_name):
    root = os.path.dirname(platform_main.__file__)
    with open(os.path.join(root, path)) as fil:
        tree = ast.parse(fil.read())
    (cls,) = [n for n in ast.walk(tree)
              if isinstance(n, ast.ClassDef) and n.name == class_name]
    (func,) = [n for n in cls.body
               if isinstance(n, ast.FunctionDef)
               and n.name == "handle_subsystem"]
    names = set()
    for node in ast.walk(func):
        if (isinstance(node, ast.Compare) and len(node.ops) == 1
                and isinstance(node.ops[0], ast.Eq)
                and isinstance(node.left, ast.Name)
                and node.left.id in ("op", "subsystem", "name")
                and isinstance(node.comparators[0], ast.Constant)
                and isinstance(node.comparators[0].value, str)):
            names.add(node.comparators[0].value)
    return names


def test_the_enumeration_finds_a_known_operation_in_each_table():
    found = {path: dispatched_names(path, cls)
             for path, cls in DISPATCH_TABLES}
    assert "agentstop" in found["main.py"]
    assert "web-addresses" in found["vip/routingservice.py"]
    assert "auth_update" in found["vip/pubsubservice.py"]
    assert "send_peer" in found["vip/externalrpcservice.py"]


@pytest.mark.parametrize("path,class_name", DISPATCH_TABLES)
def test_every_dispatched_operation_is_checked_or_listed_as_needing_no_check(
        path, class_name):
    unknown = (dispatched_names(path, class_name) - set(OPERATIONS)
               - set(UNGATED))
    assert unknown == set(), (
        "new router operation without a sender rule: {}".format(sorted(unknown)))


def test_every_listed_operation_is_still_dispatched():
    dispatched = set()
    for path, cls in DISPATCH_TABLES:
        dispatched |= dispatched_names(path, cls)
    assert set(OPERATIONS) - dispatched == set()
