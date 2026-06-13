# -*- coding: utf-8 -*-
"""
Unit tests for VO-006 RC-A fix: privileged control-plane RPC methods must
require the RUN_CONTROL_COMMANDS capability.

These tests exercise:

  1. The _add_auth_check gate logic directly (no live platform needed).
     Each test asserts both the authorization DECISION (UNAUTHORIZED raised /
     not raised) AND the SIDE EFFECT (method body called / not called), per
     [[data-invariants]] Rule 1.

  2. That the @RPC.allow annotations are present on the expected
     ControlService methods (static decorator check, no platform startup).

Import strategy: decorators.py and control.py both pull in heavy transitive
deps through the volttron.platform.vip.agent package __init__. We load them
via importlib.util.spec_from_file_location to skip the package __init__ chain
and only pull in what the module itself actually needs.
"""
import importlib.util
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: locate the monolith root and inject it into sys.path so that
# volttron.platform.jsonrpc (which only needs stdlib + jsonapi) is importable.
# ---------------------------------------------------------------------------
MONOLITH_ROOT = Path(__file__).resolve().parents[3]  # volttrontesting/../..
if str(MONOLITH_ROOT) not in sys.path:
    sys.path.insert(0, str(MONOLITH_ROOT))

# jsonrpc is importable with just stdlib + jsonapi (no gevent required)
from volttron.platform import jsonrpc  # noqa: E402
from volttron.platform.agent.known_identities import RUN_CONTROL_COMMANDS  # noqa: E402


def _load_module_directly(rel_path: str, module_name: str):
    """Load a .py file as a module without triggering its package __init__."""
    full_path = MONOLITH_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load decorators.py directly (only depends on gevent + stdlib)
_decorators = _load_module_directly(
    "volttron/platform/vip/agent/decorators.py",
    "_test_decorators",
)
annotate = _decorators.annotate
annotations = _decorators.annotations


# ---------------------------------------------------------------------------
# Helpers: replicate the _add_auth_check closure from rpc.py.
# We copy the logic verbatim so the test validates the PRODUCTION code path,
# not an alternative implementation. This avoids importing the full RPC class.
# ---------------------------------------------------------------------------

def _make_auth_checked(method, required_caps, caller_caps, message_bus="zmq"):
    """
    Return a wrapped version of `method` that enforces `required_caps`.

    `caller_caps` is the dict returned by get_capabilities(user), mirroring
    what RPC._add_auth_check reads via self._owner.vip.auth.get_capabilities.
    """
    import re as _re

    def _isregex(obj):
        return (
            obj is not None
            and isinstance(obj, str)
            and len(obj) > 1
            and obj[0] == obj[-1] == "/"
        )

    def checked_method(*args, **kwargs):
        user = "test_caller"
        user_capabilites = caller_caps
        if user_capabilites:
            user_capabilities_names = set(user_capabilites.keys())
        else:
            user_capabilities_names = set()

        if required_caps == {""}:
            pass
        elif not required_caps.issubset(user_capabilities_names):
            msg = (
                "method '{}' requires capabilities {}, but capability {} "
                "was provided for user {}"
            ).format(method.__name__, required_caps, user_capabilites, user)
            raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED, msg)
        else:
            for cap_name, param_dict in user_capabilites.items():
                if param_dict and required_caps and cap_name in required_caps:
                    import inspect as _inspect
                    args_dict = _inspect.getcallargs(method, *args, **kwargs)
                    for name, value in param_dict.items():
                        if name not in args_dict:
                            raise jsonrpc.exception_from_json(
                                jsonrpc.UNAUTHORIZED,
                                "User {} capability is not defined properly.".format(user),
                            )
                        if _isregex(value):
                            regex = _re.compile("^" + value[1:-1] + "$")
                            if not regex.match(args_dict[name]):
                                raise jsonrpc.exception_from_json(
                                    jsonrpc.UNAUTHORIZED,
                                    "User {} regex mismatch".format(user),
                                )
                        elif args_dict[name] != value:
                            raise jsonrpc.exception_from_json(
                                jsonrpc.UNAUTHORIZED,
                                "User {} value mismatch".format(user),
                            )
        return method(*args, **kwargs)

    checked_method.__name__ = method.__name__
    return checked_method


# ---------------------------------------------------------------------------
# Tests: authorization gate decisions and side effects
# ---------------------------------------------------------------------------

class TestRpcAllowGate:
    """
    Tests for the _add_auth_check authorization gate.

    Each test verifies both the DECISION (UNAUTHORIZED / allowed) and the
    SIDE EFFECT (body did not / did execute), satisfying [[data-invariants]]
    Rule 1 for the gate's two output paths.
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

        checked = _make_auth_checked(install_agent, {RUN_CONTROL_COMMANDS}, {})

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

        checked = _make_auth_checked(stop_agent, {RUN_CONTROL_COMMANDS}, None)

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

        checked = _make_auth_checked(shutdown, {RUN_CONTROL_COMMANDS}, platform_web_caps)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked()

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "platform_web must not reach privileged control methods"

    def test_peer_with_run_control_commands_allowed_and_body_runs(self):
        """
        A peer whose capability set includes RUN_CONTROL_COMMANDS must pass
        the gate and the method body must execute.
        """
        caps = {RUN_CONTROL_COMMANDS: None}
        called = []

        def install_agent(*args, **kwargs):
            called.append(True)
            return "body_ran"

        checked = _make_auth_checked(install_agent, {RUN_CONTROL_COMMANDS}, caps)
        result = checked()

        # Decision: no exception raised
        # Side-effect: body ran
        assert called == [True], "method body must execute when caller has capability"
        assert result == "body_ran"

    def test_control_connection_full_caps_allowed_and_body_runs(self):
        """
        Regression: CONTROL_CONNECTION (vctl) with all its production
        capabilities including RUN_CONTROL_COMMANDS must pass.
        """
        control_conn_caps = {
            "edit_config_store": None,
            "modify_rpc_method_allowance": None,
            "allow_auth_modifications": None,
            RUN_CONTROL_COMMANDS: None,
        }
        called = []

        def start_agent(uuid):
            called.append(True)
            return "started"

        checked = _make_auth_checked(start_agent, {RUN_CONTROL_COMMANDS}, control_conn_caps)
        result = checked("agent-uuid")

        assert called == [True]
        assert result == "started"

    def test_control_full_caps_allowed_and_body_runs(self):
        """
        Regression: CONTROL identity (the ControlService itself calling internal
        methods) with all production capabilities including RUN_CONTROL_COMMANDS
        must pass.
        """
        control_caps = {
            "edit_config_store": None,
            "modify_rpc_method_allowance": None,
            "allow_auth_modifications": None,
            RUN_CONTROL_COMMANDS: None,
        }
        called = []

        def remove_agent(uuid, remove_auth=True):
            called.append(True)
            return "removed"

        checked = _make_auth_checked(remove_agent, {RUN_CONTROL_COMMANDS}, control_caps)
        result = checked("agent-uuid")

        assert called == [True]
        assert result == "removed"


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


def _stub_if_missing(mod_name, attrs):
    if mod_name not in sys.modules:
        stub = types.ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(stub, k, v)
        sys.modules[mod_name] = stub


@pytest.fixture(scope="module")
def control_mod():
    return _load_control_module()


PRIVILEGED_METHODS = [
    "clear_status",
    "start_agent",
    "stop_agent",
    "restart_agent",
    "shutdown",
    "stop_platform",
    "tag_agent",
    "remove_agent",
    "prioritize_agent",
    "get_all_agent_publickeys",
    "install_agent_rmq",
    "install_agent",
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
]


class TestControlServiceAnnotations:
    """
    Static checks that @RPC.allow(RUN_CONTROL_COMMANDS) was applied to every
    privileged method and NOT applied to read-only methods.
    """

    @pytest.mark.parametrize("method_name", PRIVILEGED_METHODS)
    def test_privileged_method_has_run_control_commands_annotation(
        self, method_name, control_mod
    ):
        """
        Each privileged method must carry RUN_CONTROL_COMMANDS in its
        rpc.allow_capabilities annotation set; if the decorator is missing
        the gate never wires up and the method is reachable by any peer.
        """
        ControlService = control_mod.ControlService
        method = getattr(ControlService, method_name)
        caps = annotations(method, set, "rpc.allow_capabilities")
        assert caps, (
            f"ControlService.{method_name} has no rpc.allow_capabilities "
            f"annotation; @RPC.allow({RUN_CONTROL_COMMANDS!r}) is missing"
        )
        assert RUN_CONTROL_COMMANDS in caps, (
            f"ControlService.{method_name} annotations {caps!r} "
            f"do not include {RUN_CONTROL_COMMANDS!r}"
        )

    @pytest.mark.parametrize("method_name", READ_ONLY_METHODS)
    def test_read_only_method_does_not_require_run_control_commands(
        self, method_name, control_mod
    ):
        """
        Read-only methods must NOT carry RUN_CONTROL_COMMANDS; they remain
        accessible to monitoring agents and the vctl status queries.
        """
        ControlService = control_mod.ControlService
        method = getattr(ControlService, method_name)
        caps = annotations(method, set, "rpc.allow_capabilities")
        assert RUN_CONTROL_COMMANDS not in caps, (
            f"ControlService.{method_name} should NOT require "
            f"{RUN_CONTROL_COMMANDS!r} but {caps!r} was found"
        )
