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
"""The router takes a message's user from the socket it arrived on: the
in-process socket gives the sender, the network socket gives the ZAP user.
Fake sockets record which socket sent each message."""

import ast
import importlib.util
import logging
import os
import re
import subprocess

import pytest
import zmq

from volttron.platform import main as platform_main
from volttron.platform.agent import known_identities
from volttron.platform.vip import router as router_module
from volttron.platform.vip.router import (ORIGIN_INPROC, ORIGIN_NETWORK,
                                          RouterSender)

PROTO = "VIP1"


class FakeFrame:
    """A received frame whose connection properties are given, or raise
    EINVAL as libzmq does for a peer that has none."""

    def __init__(self, data, props=None):
        self.bytes = data if isinstance(data, bytes) else data.encode()
        self._props = props

    def get(self, name):
        if self._props is None or name not in self._props:
            raise zmq.ZMQError(zmq.EINVAL)
        return self._props[name]


class FakeSocket:
    def __init__(self, name, log=None):
        self.name = name
        self.identity = b""
        self.sent = []
        self.events = []
        self.unreachable = set()
        self.router_mandatory = None
        self.sndtimeo = 0
        self.hwm = None
        self._log = log if log is not None else self.events

    def bind(self, address):
        self._log.append((self.name, "bind", address))
        self.last_endpoint = address.encode()

    def set_hwm(self, value):
        self.hwm = value

    def get_monitor_socket(self):
        return None

    @property
    def zap_domain(self):
        raise AssertionError("zap_domain is write-only in this fake")

    @zap_domain.setter
    def zap_domain(self, value):
        self._log.append((self.name, "zap_domain", value))

    def send_multipart(self, frames, flags=0, copy=True):
        first = bytes(frames[0]).decode("iso-8859-1")
        if first in self.unreachable:
            raise zmq.ZMQError(zmq.EHOSTUNREACH)
        self.sent.append([bytes(f).decode("iso-8859-1") for f in frames])


class _TestRouter(platform_main.Router):
    """The real router with its two sockets replaced by fakes."""

    def _add_pubsub_peers(self, peer):
        pass

    def _drop_pubsub_peers(self, peer):
        pass

    def handle_subsystem(self, frames, user_id):
        return None


@pytest.fixture
def context():
    ctx = zmq.Context()
    yield ctx
    ctx.term()


def make_router(context, enable_auth=True, default_user_id=None):
    router = _TestRouter("ipc://@router-origin-test", context=context,
                         enable_auth=enable_auth,
                         default_user_id=default_user_id,
                         service_notifier=None)
    router.socket = FakeSocket("network")
    router.inproc_socket = FakeSocket("inproc")
    router.socket.identity = b"net-id"
    router.inproc_socket.identity = b"inproc-id"
    return router


def message(sender, recipient="peer.b", subsystem="rpc", msg_id="m1"):
    return [sender, recipient, PROTO, "", msg_id, subsystem, "body"]


def network_frames(sender, user_id="u1", recipient="peer.b"):
    """The raw frames of a network message whose first frame carries the
    given ZAP user, or none when user_id is None."""
    props = None if user_id is None else {"User-Id": user_id}
    return [FakeFrame(sender, props), FakeFrame(recipient, props)]


def rpc_recipients(socket):
    """Recipients of the routed messages, leaving out the peerlist notices
    sent when a peer first appears."""
    return [m[0] for m in socket.sent if m[5] == "rpc"]


def forwarded_user(socket):
    assert len(socket.sent) == 1, socket.sent
    return socket.sent[0][3]


def test_route_without_origin_raises_type_error(context):
    router = make_router(context)
    with pytest.raises(TypeError, match="origin"):
        router.route(message("alice"))
    assert router.socket.sent == [] and router.inproc_socket.sent == []


def test_route_with_an_unknown_origin_raises_and_sends_nothing(context):
    router = make_router(context)
    with pytest.raises(ValueError):
        router.route(message("alice"), "elsewhere")
    assert router.socket.sent == [] and router.inproc_socket.sent == []


def test_inproc_origin_gives_the_sender(context):
    router = make_router(context)
    router.route(message("platform.auth"), ORIGIN_INPROC)
    assert forwarded_user(router.socket) == "platform.auth"


def test_network_origin_gives_the_zap_user_not_the_sender(context):
    router = make_router(context)
    router.route(message("s2"), ORIGIN_NETWORK, network_frames("s2", "u1"))
    assert forwarded_user(router.socket) == "u1"


def test_network_frame_without_user_id_gives_empty_and_one_warning(
        context, caplog):
    router = make_router(context, default_user_id="vip.service")
    with caplog.at_level(logging.WARNING, logger=router_module.__name__):
        for msg_id in ("m1", "m2"):
            router.route(message("s3", msg_id=msg_id), ORIGIN_NETWORK,
                         network_frames("s3", None))
    assert [m[3] for m in router.socket.sent] == ["", ""]
    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING and "s3" in r.getMessage()]
    assert len(warnings) == 1


def test_a_second_sender_without_user_id_gets_its_own_warning(
        context, caplog):
    router = make_router(context)
    with caplog.at_level(logging.WARNING, logger=router_module.__name__):
        router.route(message("s3"), ORIGIN_NETWORK, network_frames("s3", None))
        router.route(message("s4"), ORIGIN_NETWORK, network_frames("s4", None))
    names = [r.getMessage() for r in caplog.records
             if r.levelno == logging.WARNING]
    assert len(names) == 2 and "s3" in names[0] and "s4" in names[1]


def test_senders_already_warned_about_are_remembered_only_up_to_a_limit(
        context, monkeypatch):
    monkeypatch.setattr(router_module, "_LOGGED_SENDERS_LIMIT", 5)
    router = make_router(context)
    for number in range(8):
        sender = "s{}x".format(number)
        router.route(message(sender), ORIGIN_NETWORK,
                     network_frames(sender, None))
    assert len(router._logged_senders["no-user"]) == 5


def test_network_frame_with_no_frame_objects_gives_empty(context):
    router = make_router(context)
    router.route(message("s5"), ORIGIN_NETWORK)
    assert forwarded_user(router.socket) == ""


def test_setup_mode_empty_zap_user_is_not_the_sender(context, caplog):
    router = make_router(context)
    with caplog.at_level(logging.WARNING, logger=router_module.__name__):
        router.route(message("control.connection"), ORIGIN_NETWORK,
                     network_frames("control.connection", ""))
    assert forwarded_user(router.socket) == ""
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


@pytest.mark.parametrize("origin,frames", [
    (ORIGIN_INPROC, None),
    (ORIGIN_NETWORK, network_frames("s6", "u1")),
    (ORIGIN_NETWORK, network_frames("s6", None)),
])
def test_with_auth_off_the_user_is_the_sender(context, origin, frames):
    router = make_router(context, enable_auth=False)
    router.route(message("s6"), origin, frames)
    assert forwarded_user(router.socket) == "s6"


def test_replies_go_on_the_socket_each_peer_arrived_on(context):
    router = make_router(context)
    router.route(message("agent.a", "platform.auth"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    router.route(message("platform.auth", "agent.a"), ORIGIN_INPROC)
    # the first message found its recipient on the inproc socket's side
    assert rpc_recipients(router.inproc_socket) == ["platform.auth"]
    assert rpc_recipients(router.socket) == ["agent.a"]
    assert router._identity_sockets["agent.a"] is router.socket
    assert router._identity_sockets["platform.auth"] is router.inproc_socket


@pytest.mark.parametrize("identity", sorted(known_identities.IN_PROCESS_IDENTITIES))
def test_network_message_from_an_in_process_identity_is_dropped_once(
        context, caplog, identity):
    router = make_router(context)
    with caplog.at_level(logging.WARNING, logger=router_module.__name__):
        for msg_id in ("m1", "m2"):
            router.route(message(identity, msg_id=msg_id), ORIGIN_NETWORK,
                         network_frames(identity, "u1"))
    assert router.socket.sent == [] and router.inproc_socket.sent == []
    assert identity not in router._peers
    assert identity not in router._identity_sockets
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING
                and identity in r.getMessage()]
    assert len(warnings) == 1


def test_network_router_probe_from_an_in_process_identity_is_dropped(context):
    router = make_router(context)
    router.route(["platform.auth", ""], ORIGIN_NETWORK,
                 network_frames("platform.auth", "u1"))
    assert "platform.auth" not in router._peers


def test_network_message_under_a_service_identity_leaves_the_service_mapped(context):
    router = make_router(context)
    router.route(message("platform.auth", "agent.a"), ORIGIN_INPROC)
    router.route(message("platform.auth", "agent.a"), ORIGIN_NETWORK,
                 network_frames("platform.auth", "u1"))
    router.socket.sent.clear()
    router.inproc_socket.sent.clear()
    router.route(message("agent.a", "platform.auth"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    assert rpc_recipients(router.inproc_socket) == ["platform.auth"]
    assert rpc_recipients(router.socket) == []


def test_network_peer_cannot_take_an_identity_mapped_to_inproc(context):
    router = make_router(context)
    router.route(message("custom.svc", "agent.a"), ORIGIN_INPROC)
    router.route(message("custom.svc", "agent.a"), ORIGIN_NETWORK,
                 network_frames("custom.svc", "u1"))
    assert router._identity_sockets["custom.svc"] is router.inproc_socket
    assert len(router.socket.sent) == 1   # only the first, inproc, message


def test_identity_that_appears_on_both_sockets_is_dropped_from_network(
        context):
    router = make_router(context)
    router.route(message("custom.svc", "agent.a"), ORIGIN_NETWORK,
                 network_frames("custom.svc", "u1"))
    router.route(message("custom.svc", "agent.a"), ORIGIN_INPROC)
    assert router._identity_sockets["custom.svc"] is router.inproc_socket
    router.socket.sent.clear()
    router.route(message("agent.a", "custom.svc"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    assert [m[0] for m in router.inproc_socket.sent[-1:]] == ["custom.svc"]
    assert router.socket.sent == []


def test_dropping_a_peer_forgets_its_socket(context):
    router = make_router(context)
    router.route(message("agent.a"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    router._drop_peer("agent.a")
    assert "agent.a" not in router._identity_sockets


def test_unreachable_in_process_recipient_is_not_tried_on_the_network_socket(
        context):
    router = make_router(context)
    router.inproc_socket.unreachable.add("platform.auth")
    router.route(message("agent.a", "platform.auth"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    # the error reply to agent.a is the only thing sent, and only on network
    assert [m[0] for m in router.socket.sent] == ["agent.a"]
    assert router.socket.sent[0][5] == "error"
    assert router.inproc_socket.sent == []


def test_error_reply_goes_on_the_senders_socket(context):
    router = make_router(context)
    router.socket.unreachable.add("ghost")
    router.route(message("platform.auth", "ghost"), ORIGIN_INPROC)
    replies = [m for m in router.inproc_socket.sent if m[5] == "error"]
    assert [m[0] for m in replies] == ["platform.auth"]
    assert [m for m in router.socket.sent if m[5] == "error"] == []


def test_distribute_uses_each_peers_socket(context):
    router = make_router(context)
    router.route(message("agent.a"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    router.route(message("platform.health"), ORIGIN_INPROC)
    router.socket.sent.clear()
    router.inproc_socket.sent.clear()
    router._distribute("peerlist", "add", "x")
    assert [m[0] for m in router.socket.sent] == ["agent.a"]
    assert [m[0] for m in router.inproc_socket.sent] == ["platform.health"]


def test_service_sender_picks_the_socket_by_recipient(context):
    router = make_router(context)
    router.route(message("agent.a"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1"))
    router.route(message("platform.health"), ORIGIN_INPROC)
    router.socket.sent.clear()
    router.inproc_socket.sent.clear()
    sender = RouterSender(router)
    sender.send_multipart([zmq.Frame(b"agent.a"), zmq.Frame(b"x")],
                          flags=zmq.NOBLOCK, copy=False)
    sender.send_multipart([zmq.Frame(b"platform.health"), zmq.Frame(b"y")],
                          flags=zmq.NOBLOCK, copy=False)
    assert router.socket.sent == [["agent.a", "x"]]
    assert router.inproc_socket.sent == [["platform.health", "y"]]


def test_hello_reply_carries_the_identity_of_the_arriving_socket(context):
    router = make_router(context)
    router.route(message("agent.a", "", "hello"), ORIGIN_NETWORK,
                 network_frames("agent.a", "u1", ""))
    router.route(message("platform.health", "", "hello"), ORIGIN_INPROC)
    assert router.socket.sent[0][5:9] == ["hello", "welcome", "1.0", "net-id"]
    assert router.inproc_socket.sent[0][5:9] == [
        "hello", "welcome", "1.0", "inproc-id"]


class _SpyRouter(_TestRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.routed = []

    def route(self, frames, origin, raw_frames=None):
        self.routed.append((origin, frames, raw_frames))


class FakePoller:
    def __init__(self, ready):
        self.ready = ready

    def poll(self):
        return self.ready


class ReceivingSocket(FakeSocket):
    def __init__(self, name, frames):
        super().__init__(name)
        self._frames = frames

    def recv_multipart(self, copy=True):
        assert copy is False, "copy=True frames carry no connection metadata"
        return self._frames


def spy_router(context, network_in=None, inproc_in=None):
    router = _SpyRouter("ipc://@router-origin-test", context=context,
                        enable_auth=True)
    raw = [FakeFrame("a", {"User-Id": "u1"}), FakeFrame("b"), FakeFrame("c")]
    router.socket = ReceivingSocket("network", raw)
    router.inproc_socket = ReceivingSocket("inproc", [FakeFrame("p")])
    router._ext_routing = type("R", (), {"_vip_sockets": set(),
                                         "_monitor_sockets": set()})()
    ready = {}
    if network_in:
        ready[router.socket] = zmq.POLLIN
    if inproc_in:
        ready[router.inproc_socket] = zmq.POLLIN
    router._poller = FakePoller(ready)
    return router, raw


def test_poll_passes_the_network_origin_and_the_received_frames(context):
    router, raw = spy_router(context, network_in=True)
    router.poll_sockets()
    (origin, frames, raw_frames), = router.routed
    assert origin == ORIGIN_NETWORK
    assert frames == ["a", "b", "c"]
    assert raw_frames is raw


def test_poll_passes_the_inproc_origin_for_the_inproc_socket(context):
    router, _ = spy_router(context, inproc_in=True)
    router.poll_sockets()
    (origin, frames, _), = router.routed
    assert origin == ORIGIN_INPROC and frames == ["p"]


def test_ext_route_routes_as_network(context):
    router, raw = spy_router(context)
    ext = ReceivingSocket("ext", raw[:3])
    router.ext_route(ext)
    (origin, frames, raw_frames), = router.routed
    assert origin == ORIGIN_NETWORK
    assert raw_frames is None


def test_relayed_frame_carrying_a_user_id_gets_the_empty_user(context):
    router = make_router(context)
    relayed = [FakeFrame("s7", {"User-Id": "control.connection"}),
               FakeFrame("peer.b", {"User-Id": "control.connection"}),
               FakeFrame("VIP1"), FakeFrame(""), FakeFrame("m1"),
               FakeFrame("rpc"), FakeFrame("body")]
    router.ext_route(ReceivingSocket("ext", relayed))
    assert forwarded_user(router.socket) == ""


def configured_router(context):
    """A real Router whose socket factory hands out fakes sharing one log."""
    log = []
    router = _TestRouter("ipc://@router-origin-test", context=context,
                         enable_auth=True,
                         addresses=["tcp://127.0.0.1:22916"])
    sockets = {}

    def factory(ctx, kind):
        name = "network" if "network" not in sockets else "inproc"
        sockets[name] = FakeSocket(name, log)
        return sockets[name]

    router._socket_class = factory
    router.socket = factory(context, zmq.ROUTER)
    router.setup()
    return router, sockets, log


@pytest.mark.parametrize("service", [
    "RoutingService", "PubSubService", "ExternalRPCService"])
def test_each_service_is_given_the_routers_sender_not_a_socket(
        context, monkeypatch, service):
    given = []

    class Spy:
        def __init__(self, sender, *args, **kwargs):
            given.append(sender)

    monkeypatch.setattr(platform_main, service, Spy)
    for other in ("RoutingService", "PubSubService", "ExternalRPCService"):
        if other != service:
            monkeypatch.setattr(platform_main, other,
                                lambda *args, **kwargs: None)
    router, sockets, _ = configured_router(context)
    assert len(given) == 1
    assert isinstance(given[0], RouterSender)
    assert given[0]._router is router
    assert given[0] is router._sender
    assert given[0] is not router.socket
    assert given[0] is not router.inproc_socket


def test_inproc_socket_binds_only_inproc_vip_and_has_no_zap_domain(context):
    router, sockets, log = configured_router(context)
    assert router.inproc_socket is sockets["inproc"]
    assert [e for e in log if e[0] == "inproc"] == [
        ("inproc", "bind", "inproc://vip")]


def test_network_socket_takes_zap_domain_before_its_first_bind(context):
    router, sockets, log = configured_router(context)
    network = [e for e in log if e[0] == "network"]
    assert network[0] == ("network", "zap_domain", b"vip")
    binds = [e[2] for e in network if e[1] == "bind"]
    assert len(binds) == 2 and "inproc://vip" not in binds
    assert any(b.startswith("tcp://") for b in binds)


def test_both_sockets_are_polled(context):
    router, sockets, log = configured_router(context)
    registered = {}
    router._poller = type("P", (), {
        "register": lambda self, s, f: registered.__setitem__(s, f)})()
    router.setup()
    assert set(registered) >= {router.socket, router.inproc_socket}


@pytest.mark.parametrize("router_class", ["Router", "GreenRouter"])
def test_both_router_classes_still_construct(router_class, context):
    router = getattr(platform_main, router_class)(
        "ipc://@router-origin-test", context=context, enable_auth=True)
    assert router.inproc_socket is None


def inproc_vip_lines():
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    out = subprocess.run(
        ["git", "-C", root, "grep", "-n", "-E",
         r"['\"]inproc://vip['\"]", "--", "volttron", "volttrontesting",
         "services", "scripts", "examples", "integrations"],
        capture_output=True, text=True, check=False)
    assert out.returncode in (0, 1), out.stderr
    lines = []
    for line in out.stdout.splitlines():
        path, _, text = line.split(":", 2)
        lines.append((path, text.strip()))
    return lines


# The one place that binds the endpoint and the places that connect to it.
# A new connect site fails the test until it is added here, with its identity
# checked below.
KNOWN_INPROC_VIP_SITES = {
    ("volttron/platform/main.py", "inproc.bind('inproc://vip')"),
    ("volttron/platform/main.py", "address = 'inproc://vip'"),
    ("volttron/platform/aip.py", "agent = Agent(identity='aip', address='inproc://vip',"),
}


def test_every_inproc_vip_connect_in_the_tree_is_listed():
    found = inproc_vip_lines()
    # Denominator: the test files themselves are among the searched paths.
    this_file = "volttrontesting/platform/auth_tests/test_router_origin.py"
    found = {item for item in found if item[0] != this_file}
    assert found == KNOWN_INPROC_VIP_SITES


def _main_tree():
    path = importlib.util.find_spec("volttron.platform.main").origin
    with open(path) as source:
        return ast.parse(source.read())


def _resolve(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return getattr(known_identities, node.id, None)
    return None


def test_every_service_main_starts_on_inproc_has_an_in_process_identity():
    found = []
    for node in ast.walk(_main_tree()):
        if not isinstance(node, ast.Call):
            continue
        keywords = {k.arg: k.value for k in node.keywords}
        address = keywords.get("address")
        if isinstance(address, ast.Name) and address.id == "address" \
                and "identity" in keywords:
            found.append(_resolve(keywords["identity"]))
    assert len(found) >= 5, found
    assert None not in found
    assert set(found) <= known_identities.IN_PROCESS_IDENTITIES
    assert known_identities.AIP in known_identities.IN_PROCESS_IDENTITIES


def test_auth_service_and_aip_identities_are_in_process():
    assert known_identities.AUTH in known_identities.IN_PROCESS_IDENTITIES
    assert known_identities.PROXY_ROUTER \
        in known_identities.IN_PROCESS_IDENTITIES
    assert re.search(r"identity='aip'", open(importlib.util.find_spec(
        "volttron.platform.aip").origin).read())
