# -*- coding: utf-8 -*-
"""
Unit tests for VO-006 RC-A fix: privileged control-plane RPC methods must
require the correct capabilities to run gated control commands.

These tests exercise:

  1. The REAL RPC._add_auth_check gate from
     volttron/platform/vip/agent/subsystems/rpc.py, loaded via
     importlib.util.spec_from_file_location (no live platform, no gevent
     greenlet scheduler).  Each test constructs a minimal mock ``self``
     supplying the three attributes the closure reads (context.vip_message.user,
     _message_bus, _owner.vip.auth.get_capabilities) and asserts both the
     authorization DECISION (UNAUTHORIZED raised / not raised) AND the SIDE
     EFFECT (method body called / not called), per [[data-invariants]] Rule 1.

  2. That the @RPC.allow annotations are present on the expected
     ControlService methods (static decorator check, no platform startup).

Import strategy: rpc.py, decorators.py, and control.py all pull in heavy
transitive deps through the volttron.platform.vip.agent package __init__.
We load each via importlib.util.spec_from_file_location to skip the package
__init__ chain and only pull in what the module itself needs.  Stubs are
injected into sys.modules before spec.loader.exec_module() for the four
relative imports that rpc.py needs (.base, ..results, ..decorators, zmq).
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: locate the monolith root and inject it into sys.path so that
# volttron.platform.jsonrpc (which only needs stdlib + jsonapi) is importable.
# ---------------------------------------------------------------------------
MONOLITH_ROOT = Path(__file__).resolve().parents[2]  # tests/unit/../../
if str(MONOLITH_ROOT) not in sys.path:
    sys.path.insert(0, str(MONOLITH_ROOT))

# jsonrpc is importable with just stdlib + jsonapi (no gevent required)
from volttron.platform import jsonrpc  # noqa: E402
from volttron.platform.agent.known_identities import (CLEAR_AGENT_STATUS, INSTALL_REMOVE_AGENTS ,
                                                      START_STOP_AGENTS, STOP_PLATFORM, TAG_AGENTS)  # noqa: E402


def _load_module_directly(rel_path: str, module_name: str):
    """Load a .py file as a module without triggering its package __init__."""
    full_path = MONOLITH_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_if_missing(mod_name, attrs):
    if mod_name not in sys.modules:
        stub = types.ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(stub, k, v)
        sys.modules[mod_name] = stub


# ---------------------------------------------------------------------------
# Load decorators.py and rpc.py using the direct-file strategy.
#
# rpc.py's relative imports are resolved by injecting stubs into sys.modules
# for the four names it needs:
#   .base             -> SubsystemBase (empty base class)
#   ..results         -> counter, ResultsDictionary (unused in _add_auth_check)
#   ..decorators      -> the REAL decorators.py (needed for annotate/annotations)
#   zmq / zmq.green   -> stub (ZMQError, ENOTSOCK; never reached in unit tests)
# ---------------------------------------------------------------------------

# Step 1: load the real decorators.py so annotate/annotations are genuine.
_decorators_mod = _load_module_directly(
    "volttron/platform/vip/agent/decorators.py",
    "volttron.platform.vip.agent.decorators",
)
annotate = _decorators_mod.annotate
annotations = _decorators_mod.annotations

# Step 2: stubs for rpc.py's remaining relative imports.
_base_stub = types.ModuleType("volttron.platform.vip.agent.subsystems.base")


class _SubsystemBase:
    pass


_base_stub.SubsystemBase = _SubsystemBase
sys.modules["volttron.platform.vip.agent.subsystems.base"] = _base_stub

_results_stub = types.ModuleType("volttron.platform.vip.agent.results")
_results_stub.counter = lambda: iter(range(10_000))


class _ResultsDictionary(dict):
    pass


_results_stub.ResultsDictionary = _ResultsDictionary
sys.modules["volttron.platform.vip.agent.results"] = _results_stub

# zmq stubs: ZMQError and ENOTSOCK are referenced at module import time.
_stub_if_missing("zmq", {"ZMQError": Exception})
_stub_if_missing("zmq.green", {"ENOTSOCK": -1})

# Step 3: load the real rpc.py — this gives us the production RPC class.
_rpc_mod = _load_module_directly(
    "volttron/platform/vip/agent/subsystems/rpc.py",
    "volttron.platform.vip.agent.subsystems.rpc",
)
_RealRPC = _rpc_mod.RPC


# ---------------------------------------------------------------------------
# Helper: build the minimal mock ``self`` that RPC._add_auth_check needs.
#
# The closure only reads three things from self:
#   self.context.vip_message.user          -> the calling identity
#   self._message_bus                      -> "zmq" | "rmq"
#   self._owner.vip.auth.get_capabilities  -> callable returning cap dict
# ---------------------------------------------------------------------------

def _make_rpc_self(caller_caps, message_bus: str = "zmq") -> MagicMock:
    """
    Return a MagicMock shaped like the RPC subsystem object that
    _add_auth_check captures via closure.  caller_caps mirrors the dict
    returned by get_capabilities(user) in the live platform.
    """
    mock_self = MagicMock()
    mock_self._message_bus = message_bus
    mock_self.context.vip_message.user = "test_caller"
    mock_self._owner.vip.auth.get_capabilities.return_value = caller_caps
    return mock_self


def _make_auth_checked(method, required_caps, caller_caps, message_bus: str = "zmq"):
    """
    Call the REAL RPC._add_auth_check with a mock self and return the
    wrapped method.  This is the production function from rpc.py, not a
    local replica.
    """
    mock_self = _make_rpc_self(caller_caps, message_bus)
    return _RealRPC._add_auth_check(mock_self, method, required_caps)


# ---------------------------------------------------------------------------
# Tests: authorization gate decisions and side effects
# ---------------------------------------------------------------------------

class TestRpcAllowGate:
    """
    Tests for the REAL RPC._add_auth_check authorization gate.

    Each test calls the production function from
    volttron/platform/vip/agent/subsystems/rpc.py via _make_auth_checked and
    asserts both the DECISION (UNAUTHORIZED / allowed) and the SIDE EFFECT
    (body did not / did execute), satisfying [[data-invariants]] Rule 1.
    """

    def test_zero_capability_peer_rejected_and_no_side_effect(self):
        """
        A peer with no capabilities must receive UNAUTHORIZED, and the
        underlying method body must NOT execute.
        """
        called = []

        def install_agent(*args, **kwargs):
            called.append(True)
            return "body_ran"

        checked = _make_auth_checked(install_agent, {INSTALL_REMOVE_AGENTS}, {})

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked()

        # Decision: UNAUTHORIZED returned
        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        # Side-effect: body must NOT have run
        assert called == [], "method body must not execute when caller lacks capability"

    def test_none_capabilities_peer_rejected_and_no_side_effect(self):
        """
        get_capabilities returning None (identity not in auth file) must also
        be rejected and must not reach the method body.
        """
        called = []

        def stop_agent(uuid):
            called.append(True)

        checked = _make_auth_checked(stop_agent, {START_STOP_AGENTS}, None)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked("some-uuid")

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "method body must not execute when caller has no capabilities"

    def test_platform_web_capabilities_rejected_and_no_side_effect(self):
        """
        PLATFORM_WEB only holds allow_auth_modifications.  Calling a gated
        control method must be rejected (RC-C confused-deputy closure invariant:
        the platform_web service must NOT be able to reach control RPCs).
        """
        platform_web_caps = {"allow_auth_modifications": None}
        called = []

        def shutdown(*args, **kwargs):
            called.append(True)

        checked = _make_auth_checked(shutdown, {START_STOP_AGENTS}, platform_web_caps)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked()

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "platform_web must not reach privileged control methods"

    def test_peer_with_install_remove_agents_allowed_and_body_runs(self):
        """
        A peer whose capability set includes INSTALL_REMOVE_AGENTS must pass
        the gate and the method body must execute.
        """
        caps = {INSTALL_REMOVE_AGENTS: None}
        called = []

        def install_agent(*args, **kwargs):
            called.append(True)
            return "body_ran"

        checked = _make_auth_checked(install_agent, {INSTALL_REMOVE_AGENTS}, caps)
        result = checked()

        # Decision: no exception raised
        # Side-effect: body ran
        assert called == [True], "method body must execute when caller has capability"
        assert result == "body_ran"

    def test_control_connection_full_caps_allowed_and_body_runs(self):
        """
        Regression: CONTROL_CONNECTION (vctl) with all its production
        capabilities including START_STOP_AGNENTS must pass.
        """
        control_conn_caps = {
            "edit_config_store": None,
            "modify_rpc_method_allowance": None,
            "allow_auth_modifications": None,
            START_STOP_AGENTS: None,
        }
        called = []

        def start_agent(uuid):
            called.append(True)
            return "started"

        checked = _make_auth_checked(start_agent, {START_STOP_AGENTS}, control_conn_caps)
        result = checked("agent-uuid")

        assert called == [True]
        assert result == "started"

    def test_control_full_caps_allowed_and_body_runs(self):
        """
        Regression: CONTROL identity (the ControlService itself calling internal
        methods) with all production capabilities including INSTALL_REMOVE_AGENTS
        must pass.
        """
        control_caps = {
            "edit_config_store": None,
            "modify_rpc_method_allowance": None,
            "allow_auth_modifications": None,
            INSTALL_REMOVE_AGENTS: None,
        }
        called = []

        def remove_agent(uuid, remove_auth=True):
            called.append(True)
            return "removed"

        checked = _make_auth_checked(remove_agent, {INSTALL_REMOVE_AGENTS}, control_caps)
        result = checked("agent-uuid")

        assert called == [True]
        assert result == "removed"

    def test_clear_status_zero_caps_rejected_and_no_side_effect(self):
        """
        Two-sided behavioral test for clear_status (B4 addition):
        zero-capability caller receives UNAUTHORIZED and _aip.clear_status
        is NOT called.
        """
        aip_mock = MagicMock()
        called = []

        def clear_status(clear_all=False):
            # mirrors ControlService.clear_status body
            called.append(True)
            aip_mock.clear_status(clear_all)

        checked = _make_auth_checked(clear_status, {CLEAR_AGENT_STATUS}, {})

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked()

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "clear_status body must not run for zero-cap caller"
        aip_mock.clear_status.assert_not_called()

    def test_clear_status_allowed_and_aip_called(self):
        """
        Two-sided behavioral test for clear_status (B4 addition):
        caller with CLEAR_AGENT_STATUS passes the gate and _aip.clear_status
        IS called.
        """
        aip_mock = MagicMock()
        called = []

        def clear_status(clear_all=False):
            called.append(True)
            aip_mock.clear_status(clear_all)

        caps = {CLEAR_AGENT_STATUS: None}
        checked = _make_auth_checked(clear_status, {CLEAR_AGENT_STATUS}, caps)
        checked(clear_all=True)

        assert called == [True], "clear_status body must run for capable caller"
        aip_mock.clear_status.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# Tests: @RPC.allow annotations on ControlService methods
# ---------------------------------------------------------------------------

def _load_control_module():
    """
    Load control.py without triggering the full Agent import chain.
    Stubs out the heavy imports that control.py needs at module level.
    """
    # Stub heavy dependencies that control.py imports at module scope
    for mod_name in [
        "volttron.platform.vip.agent",
        "volttron.platform.vip.agent.subsystems.query",
    ]:
        if mod_name not in sys.modules:
            stub = types.ModuleType(mod_name)
            sys.modules[mod_name] = stub

    # Agent base and decorators stubs for ControlService.__bases__
    agent_stub = sys.modules["volttron.platform.vip.agent"]

    class FakeAgent:
        pass

    class FakeCore:
        @staticmethod
        def receiver(event):
            def deco(fn):
                return fn
            return deco

    class FakeRPC:
        @staticmethod
        def export(fn):
            # Apply the rpc.exports annotation the real RPC.export does
            annotate(fn, set, "rpc.exports", fn.__name__)
            return fn

        @staticmethod
        def allow(capabilities):
            # Apply the rpc.allow_capabilities annotation the real RPC.allow does
            def decorate(method):
                if isinstance(capabilities, str):
                    annotate(method, set, "rpc.allow_capabilities", capabilities)
                else:
                    for cap in capabilities:
                        annotate(method, set, "rpc.allow_capabilities", cap)
                return method
            return decorate

    agent_stub.Agent = FakeAgent
    agent_stub.Core = FakeCore
    agent_stub.RPC = FakeRPC

    query_stub = sys.modules["volttron.platform.vip.agent.subsystems.query"]
    query_stub.Query = object

    # Now load control.py directly
    control_path = MONOLITH_ROOT / "volttron/platform/control/control.py"
    spec = importlib.util.spec_from_file_location(
        "_test_control_module", control_path
    )
    mod = importlib.util.module_from_spec(spec)

    # Stub remaining dependencies that control.py imports
    _stub_if_missing("volttron.platform.aip", {"AIPplatform": object})
    _stub_if_missing("volttron.platform.jsonapi", {"dumps": lambda x: x, "dumpb": lambda x: x})
    _stub_if_missing("volttron.platform.agent.utils", {"get_messagebus": lambda: "zmq",
                                                        "get_aware_utc_now": lambda: None})
    _stub_if_missing("volttron.platform.messaging.health", {
        "Status": MagicMock(), "STATUS_BAD": "BAD"
    })
    _stub_if_missing("volttron.platform.scheduling", {"periodic": lambda x: x})

    sys.modules["_test_control_module"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def control_mod():
    return _load_control_module()


STATUS_METHODS = [
    "clear_status"
    ]
START_STOP_METHODS = [
    "start_agent",
    "stop_agent",
    "restart_agent",
    "shutdown",
    "prioritize_agent"
    ]
STOP_PLATFORM_METHODS = [
    "stop_platform"
    ]
TAG_AGENT_METHODS = [
    "tag_agent"
    ]
INSTALL_REMOVE_METHODS = [
    "remove_agent",
    "install_agent_rmq",
    "install_agent"
    ]

READ_ONLY_METHODS = [
    "peerlist",
    "serverkey",
    "agent_status",
    "agent_name",
    "agent_version",
    "agent_versions",
    "status_agents",
    "list_agents",
    "agent_vip_identity",
    "identity_exists",
    "get_all_agent_publickeys"
]


class TestControlServiceAnnotations:
    """
    Static checks that @RPC.allow(<capability>) was applied to every
    privileged method and NOT applied to read-only methods.
    """

    @pytest.mark.parametrize("method_name", "capability", [
        (STATUS_METHODS, CLEAR_AGENT_STATUS),
        (START_STOP_METHODS, START_STOP_AGENTS),
        (STOP_PLATFORM_METHODS, STOP_PLATFORM),
        (TAG_AGENT_METHODS, TAG_AGENTS),
        (INSTALL_REMOVE_METHODS, INSTALL_REMOVE_AGENTS)
    ])
    def test_privileged_method_has_correct_annotation(
        self, method_name, control_mod
    ):
        """
        Each privileged method must carry correct capabilities in its
        rpc.allow_capabilities annotation set; if the decorator is missing
        the gate never wires up and the method is reachable by any peer.
        """
        ControlService = control_mod.ControlService
        method = getattr(ControlService, method_name)
        caps = annotations(method, set, "rpc.allow_capabilities")
        assert caps, (
            f"ControlService.{method_name} has no rpc.allow_capabilities "
            f"annotation; @RPC.allow({capability!r}) is missing"
        )
        assert capability in caps, (
            f"ControlService.{method_name} annotations {caps!r} "
            f"do not include {capablity!r}"
        )

    @pytest.mark.parametrize("method_name", READ_ONLY_METHODS)
    def test_read_only_method_does_not_require_capability(
        self, method_name, control_mod
    ):
        """
        Read-only methods must NOT carry capabilities; they remain
        accessible to monitoring agents and the vctl status queries.
        """
        ControlService = control_mod.ControlService
        method = getattr(ControlService, method_name)
        caps = annotations(method, set, "rpc.allow_capabilities")
        capabilities = [CLEAR_AGENT_STATUS, START_STOP_AGENTS, STOP_PLATFORM, TAG_AGENTS, INSTALL_REMOVE_AGENTS]
        for capability in capabilities:
            assert capability not in caps, (
                f"ControlService.{method_name} should NOT require "
                f"{capability!r} but {caps!r} was found"
            )
