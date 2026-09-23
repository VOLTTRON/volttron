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
import logging
import os
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

# Step 3: load the real rpc.py - this gives us the production RPC class.
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

def _make_rpc_self(
    caller_caps, message_bus: str = "zmq", enable_auth: bool = True
) -> MagicMock:
    """
    Return a MagicMock shaped like the RPC subsystem object that
    _add_auth_check captures via closure.  caller_caps mirrors the dict
    returned by get_capabilities(user) in the live platform.

    enable_auth defaults to True (auth enabled) so every existing caller
    of this helper keeps enforcing, matching the value a MagicMock's
    auto-created attribute would give before #3237 added the flag.
    """
    mock_self = MagicMock()
    mock_self._message_bus = message_bus
    mock_self._enable_auth = enable_auth
    mock_self.context.vip_message.user = "test_caller"
    mock_self._owner.vip.auth.get_capabilities.return_value = caller_caps
    return mock_self


def _make_auth_checked(
    method, required_caps, caller_caps, message_bus: str = "zmq", enable_auth: bool = True
):
    """
    Call the REAL RPC._add_auth_check with a mock self and return the
    wrapped method.  This is the production function from rpc.py, not a
    local replica.
    """
    mock_self = _make_rpc_self(caller_caps, message_bus, enable_auth)
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
# Tests: #3237, capability enforcement when authentication is disabled
#
# These build a real (non-MagicMock) owner/core-shaped object so that a
# missing `vip.auth` attribute behaves as it does on the live platform
# (AttributeError on access), rather than MagicMock's auto-vivified
# attribute.
# ---------------------------------------------------------------------------

class _PlainOwnerNoAuth:
    """An owner whose vip has no auth attribute, mirroring an agent built
    with authentication disabled (Agent.Subsystems only creates vip.auth
    when enable_auth is true)."""

    def __init__(self):
        self.vip = types.SimpleNamespace()


class _RpcSelfStub:
    """A minimal, real (non-Mock) RPC-shaped self carrying only the
    attributes checked_method reads, for the construction-time enable_auth
    flag."""

    def __init__(self, owner, enable_auth, message_bus="zmq", user="test_caller"):
        self._owner = owner
        self._message_bus = message_bus
        self._enable_auth = enable_auth
        self.context = types.SimpleNamespace(
            vip_message=types.SimpleNamespace(user=user)
        )


class _FakeSignal:
    """No-op stand-in for a Core event signal (onsetup, onconnected, ...)."""

    def connect(self, *args, **kwargs):
        pass


class _FakeCoreNoAuthFlag:
    """Mimics the subset of Core that RPC.__init__ touches, deliberately
    omitting enable_auth to exercise the fail-closed default (#3237)."""

    messagebus = "zmq"
    onsetup = _FakeSignal()
    ondisconnected = _FakeSignal()
    onconnected = _FakeSignal()

    def register(self, *args, **kwargs):
        pass


class _NoExportsOwner:
    pass


class _IterateExportsStub:
    """Carries only what _iterate_exports and _add_auth_check read, so the
    real production methods can run against a hand-built export table
    without a full RPC() construction."""

    _add_auth_check = _RealRPC._add_auth_check
    _iterate_exports = _RealRPC._iterate_exports
    _warn_unenforced_capabilities = _RealRPC._warn_unenforced_capabilities
    # allow() is a dualmethod descriptor; .finstance is the plain instance
    # function it wraps, the same one a real RPC instance dispatches to.
    allow = _RealRPC.__dict__["allow"].finstance

    def __init__(self, exports, enable_auth):
        self._exports = exports
        self._enable_auth = enable_auth


class TestRpcAuthDisabledCapabilityCheck:
    """
    Tests for the REAL RPC._add_auth_check and RPC._iterate_exports against
    the #3237 constraints: skip enforcement when the serving agent's own
    core says authentication is disabled, fail closed otherwise, and never
    take the decision from the incoming message.
    """

    def test_auth_disabled_runs_body_and_returns_value_with_no_auth_subsystem(self):
        """
        Fails at d68dff037 with AttributeError: checked_method reaches
        self._owner.vip.auth.get_capabilities(user) unconditionally, and
        vip has no auth attribute here.
        """
        owner = _PlainOwnerNoAuth()
        rpc_self = _RpcSelfStub(owner, enable_auth=False)
        called = []

        def install_agent(*args, **kwargs):
            called.append(True)
            return "body_ran"

        checked = _RealRPC._add_auth_check(rpc_self, install_agent, {INSTALL_REMOVE_AGENTS})
        result = checked()

        assert called == [True], "method body must run once when auth is disabled"
        assert result == "body_ran"

    def test_auth_enabled_with_missing_auth_subsystem_raises_unauthorized_not_attributeerror(self):
        """
        Fails at d68dff037 with AttributeError for the same reason as
        above. With auth enabled, a missing auth subsystem must fail
        closed (UNAUTHORIZED), never leak AttributeError past the gate.
        """
        owner = _PlainOwnerNoAuth()
        rpc_self = _RpcSelfStub(owner, enable_auth=True)
        called = []

        def install_agent(*args, **kwargs):
            called.append(True)
            return "body_ran"

        checked = _RealRPC._add_auth_check(rpc_self, install_agent, {INSTALL_REMOVE_AGENTS})

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked()

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "method body must not run when the auth subsystem is missing"

    def test_message_content_cannot_influence_enforcement_decision(self):
        """
        The enforcement decision must come only from self._enable_auth,
        captured at construction, never from the incoming message. Vary
        the message user; the auth-disabled outcome must not change.
        """
        owner = _PlainOwnerNoAuth()

        for crafted_user in ("normal_agent", "enable_auth=False", "platform.auth"):
            called = []

            def install_agent(*args, **kwargs):
                called.append(True)
                return "body_ran"

            rpc_self = _RpcSelfStub(owner, enable_auth=False, user=crafted_user)
            checked = _RealRPC._add_auth_check(rpc_self, install_agent, {INSTALL_REMOVE_AGENTS})

            assert checked() == "body_ran"
            assert called == [True]

    def test_missing_enable_auth_attribute_on_core_fails_closed(self):
        """
        Constructs a REAL RPC object against a core with no enable_auth
        attribute. Fails at d68dff037 with AttributeError: RPC.__init__
        never sets self._enable_auth there.
        """
        core = _FakeCoreNoAuthFlag()
        owner = _NoExportsOwner()

        rpc = _RealRPC(core, owner, MagicMock())

        assert rpc._enable_auth is True, "an unreadable flag must enforce, not bypass"

    @pytest.mark.parametrize(
        "raw_value, expect_enforced",
        [
            (False, False),
            (True, True),
            (None, True),
            (0, True),
            ("", True),
            ("False", True),
            ("false", True),
            (1, True),
        ],
    )
    def test_falsy_and_nonbool_enable_auth_values_through_real_constructor(
        self, raw_value, expect_enforced
    ):
        """
        Fails at 6aebfcb0d for None, 0 and "": a bare getattr capture
        treats any falsy value as disabled, though only a real bool
        False should. Kills a mutant hardcoding the capture to True.
        """
        core = _FakeCoreNoAuthFlag()
        core.enable_auth = raw_value
        owner = _NoExportsOwner()

        rpc = _RealRPC(core, owner, MagicMock())

        assert rpc._enable_auth is expect_enforced

    def test_nonbool_enable_auth_value_is_reported_not_guessed(self, caplog):
        """
        A config value that reaches core.enable_auth without ever being a
        real bool (config values arrive unparsed) is logged, not
        silently guessed at in either direction.
        """
        core = _FakeCoreNoAuthFlag()
        core.enable_auth = "False"
        owner = _NoExportsOwner()

        with caplog.at_level(logging.ERROR, logger=_rpc_mod._log.name):
            rpc = _RealRPC(core, owner, MagicMock())

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert "not a bool" in errors[0].getMessage()
        assert rpc._enable_auth is True

    def test_nonbool_enable_auth_value_is_not_echoed_in_the_log(self, caplog):
        """
        The misconfiguration log names the type, not the raw value: a
        secret mis-keyed into enable-auth must not be echoed to the
        agent log (security re-review finding 10).
        """
        core = _FakeCoreNoAuthFlag()
        core.enable_auth = "hunter2-secret-token"
        owner = _NoExportsOwner()

        with caplog.at_level(logging.ERROR, logger=_rpc_mod._log.name):
            rpc = _RealRPC(core, owner, MagicMock())

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert "hunter2-secret-token" not in errors[0].getMessage()
        assert "not a bool" in errors[0].getMessage()
        assert rpc._enable_auth is True

    def test_environment_and_core_mutation_after_construction_cannot_reopen_a_skip(self):
        """
        Fails against a mutant that re-reads AUTH_ENABLED or the live
        core at call time: the captured skip must survive both being
        changed back to enabled after construction.
        """
        core = _FakeCoreNoAuthFlag()
        core.enable_auth = False
        owner = _PlainOwnerNoAuth()
        rpc = _RealRPC(core, owner, MagicMock())

        def install_agent(*args, **kwargs):
            return "body_ran"

        checked = _RealRPC._add_auth_check(rpc, install_agent, {INSTALL_REMOVE_AGENTS})

        os.environ["AUTH_ENABLED"] = "True"
        core.enable_auth = True
        try:
            assert checked() == "body_ran", (
                "a captured skip must not be reopened by a later "
                "environment or core change"
            )
        finally:
            del os.environ["AUTH_ENABLED"]

    def test_environment_and_core_mutation_after_construction_cannot_open_a_gate(self):
        """
        Fails against a mutant that re-reads AUTH_ENABLED or the live
        core at call time: a captured enforce must survive both being
        changed back to disabled after construction.
        """
        core = _FakeCoreNoAuthFlag()
        core.enable_auth = True
        owner = _PlainOwnerNoAuth()
        rpc = _RealRPC(core, owner, MagicMock())
        # The real setup() callback (which sets this) never fires without
        # a live core signal; supply what checked_method reads directly.
        rpc.context = types.SimpleNamespace(
            vip_message=types.SimpleNamespace(user="test_caller")
        )
        called = []

        def install_agent(*args, **kwargs):
            called.append(True)
            return "body_ran"

        checked = _RealRPC._add_auth_check(rpc, install_agent, {INSTALL_REMOVE_AGENTS})

        os.environ["AUTH_ENABLED"] = "False"
        core.enable_auth = False
        try:
            with pytest.raises(jsonrpc.Error) as exc_info:
                checked()
        finally:
            del os.environ["AUTH_ENABLED"]

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "a captured enforce must not be opened by a later change"

    def test_auth_disabled_agent_with_two_gated_exports_logs_exact_warning(self, caplog):
        """
        Kills a mutant that reports the wrong count, only the first
        method name, or appends a server key and VIP address (security
        constraint 4 forbids identifying detail in this warning).
        """
        def gated_a(self):
            return "ran"

        def gated_b(self):
            return "ran"

        def plain_method(self):
            return "ran"

        annotate(gated_a, set, "rpc.allow_capabilities", INSTALL_REMOVE_AGENTS)
        annotate(gated_b, set, "rpc.allow_capabilities", START_STOP_AGENTS)

        # A third, ungated export is present so a mutant reporting
        # len(self._exports) instead of len(gated_method_names) diverges
        # from the correct count of 2.
        stub = _IterateExportsStub(
            {
                "gated_b": gated_b,
                "gated_a": gated_a,
                "plain_method": plain_method,
            },
            enable_auth=False,
        )

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub._iterate_exports()

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert warnings[0].getMessage() == (
            "authentication is disabled: capability requirements for "
            "2 exported method(s) are not enforced: gated_a, gated_b"
        )

    def test_dynamic_allow_on_auth_disabled_agent_logs_a_warning(self, caplog):
        """
        Fails at 6aebfcb0d: allow() wraps the method directly and never
        re-enters _iterate_exports, so a capability granted this way
        after construction skips enforcement with zero warnings.
        """
        def config_update(self):
            return "ran"

        stub = _IterateExportsStub({"config_update": config_update}, enable_auth=False)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub.allow("config_update", "sync_agent_config")

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert warnings[0].getMessage() == (
            "authentication is disabled: capability requirements for "
            "1 exported method(s) are not enforced: config_update"
        )
        # The dynamic path still enforces the skip itself, not only the warning.
        checked = stub._exports["config_update"]
        assert checked(stub) == "ran"

    def test_dynamic_allow_on_auth_enabled_agent_logs_no_warning(self, caplog):
        """Control: the new allow() warning does not fire when auth is enabled."""
        def config_update(self):
            return "ran"

        stub = _IterateExportsStub({"config_update": config_update}, enable_auth=True)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub.allow("config_update", "sync_agent_config")

        assert not [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_auth_disabled_agent_with_gated_export_logs_one_warning(self, caplog):
        """
        Fails at d68dff037: _iterate_exports never inspects enable_auth
        and never logs, so 0 warnings are recorded, not 1.
        """

        def gated_method(self):
            return "ran"

        annotate(gated_method, set, "rpc.allow_capabilities", INSTALL_REMOVE_AGENTS)

        stub = _IterateExportsStub({"gated_method": gated_method}, enable_auth=False)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub._iterate_exports()

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "exactly one warning, not one per gated method"
        assert "gated_method" in warnings[0].getMessage()

    def test_auth_enabled_agent_with_gated_export_logs_no_warning(self, caplog):
        def gated_method(self):
            return "ran"

        annotate(gated_method, set, "rpc.allow_capabilities", INSTALL_REMOVE_AGENTS)

        stub = _IterateExportsStub({"gated_method": gated_method}, enable_auth=True)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub._iterate_exports()

        assert not [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_auth_disabled_agent_with_no_gated_exports_logs_no_warning(self, caplog):
        def plain_method(self):
            return "ran"

        stub = _IterateExportsStub({"plain_method": plain_method}, enable_auth=False)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub._iterate_exports()

        assert not [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_dynamic_allow_with_method_object_on_auth_disabled_agent_logs_a_warning(self, caplog):
        """
        Fails against a mutant that drops the method-object branch's name
        capture (gated_method_name = None): the warning then disappears
        for every caller granting a capability with a method object
        instead of a string alias, which is the form the in-tree auth
        tests use (coverage re-review finding at rpc.py:738, mutant M6).
        """
        def install_agent(self):
            return "ran"

        stub = _IterateExportsStub({}, enable_auth=False)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub.allow(install_agent, INSTALL_REMOVE_AGENTS)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert warnings[0].getMessage() == (
            "authentication is disabled: capability requirements for "
            "1 exported method(s) are not enforced: install_agent"
        )
        checked = stub._exports["install_agent"]
        assert checked(stub) == "ran"

    def test_dynamic_allow_with_unresolved_alias_on_auth_disabled_agent_logs_no_warning(self, caplog):
        """
        Fails against a mutant that drops the `gated_method_name and`
        guard: a failed alias lookup then still reaches the warning call
        with gated_method_name unset, naming a method that was never
        gated (coverage re-review finding at rpc.py:743, mutant M16).
        """
        stub = _IterateExportsStub({}, enable_auth=False)

        with caplog.at_level(logging.WARNING, logger=_rpc_mod._log.name):
            stub.allow("not_an_export", INSTALL_REMOVE_AGENTS)

        assert not [r for r in caplog.records if r.levelno == logging.WARNING]


# ---------------------------------------------------------------------------
# Tests: #3242, parameter-restriction regex full-string anchoring
# ---------------------------------------------------------------------------

class TestParameterRestrictionRegexAnchoring:
    """
    Tests for the REAL RPC._add_auth_check parameter-restriction regex
    against CWE-625: a top-level `|` alternation must not degrade to a
    prefix match on any alternative.
    """

    def test_alternation_restriction_rejects_value_outside_allowed_set(self):
        """
        Fails at d68dff037: re.compile("^" + value + "$") loses full-string
        anchoring on the left alternative, so a value that merely starts
        with an allowed alternative is wrongly accepted.
        """
        caps = {"edit_config_store": {"identity": "/platform.driver|platform.actuator/"}}
        called = []

        def manage_store(identity):
            called.append(True)
            return "wrote"

        checked = _make_auth_checked(manage_store, {"edit_config_store"}, caps)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked(identity="platform.driverEVIL_OTHER_AGENT")

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "method body must not run for an out-of-scope identity"

    def test_single_value_regex_restriction_unchanged_accepts_match(self):
        """Control: a non-alternation restriction still accepts its value."""
        caps = {"edit_config_store": {"identity": "/platform.driver/"}}
        called = []

        def manage_store(identity):
            called.append(True)
            return "wrote"

        checked = _make_auth_checked(manage_store, {"edit_config_store"}, caps)
        result = checked(identity="platform.driver")

        assert called == [True]
        assert result == "wrote"

    def test_single_value_regex_restriction_unchanged_rejects_prefix_match(self):
        """Control: a non-alternation restriction already rejects a
        suffix-appended value before and after the #3242 fix."""
        caps = {"edit_config_store": {"identity": "/platform.driver/"}}
        called = []

        def manage_store(identity):
            called.append(True)
            return "wrote"

        checked = _make_auth_checked(manage_store, {"edit_config_store"}, caps)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked(identity="platform.driverEVIL")

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == []

    def test_alternation_restriction_rejects_trailing_newline_residue(self):
        """
        Fails at 6aebfcb0d: re.match's "$" matches before a final
        newline, so an identity with a newline appended still passes.
        """
        caps = {"edit_config_store": {"identity": "/platform.driver|platform.actuator/"}}
        called = []

        def manage_store(identity):
            called.append(True)
            return "wrote"

        checked = _make_auth_checked(manage_store, {"edit_config_store"}, caps)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked(identity="platform.driver\n")

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == [], "a trailing newline must not slip past full-string anchoring"

    def test_alternation_restriction_accepts_middle_and_last_alternatives(self):
        """
        Fails against a mutant that keeps only the first "|" alternative
        (value[1:-1].split("|")[0]): the middle and last alternatives
        would then be wrongly refused.
        """
        caps = {"edit_config_store": {"identity": "/aaa|bbb|ccc/"}}

        for identity in ("bbb", "ccc"):
            called = []

            def manage_store(identity):
                called.append(True)
                return "wrote"

            checked = _make_auth_checked(manage_store, {"edit_config_store"}, caps)
            result = checked(identity=identity)

            assert called == [True], f"{identity!r} is a legitimate alternative"
            assert result == "wrote"

    def test_alternation_restriction_rejects_value_extending_a_middle_alternative(self):
        """Control for the mutant above: an out-of-scope value built from
        the middle alternative is still refused."""
        caps = {"edit_config_store": {"identity": "/aaa|bbb|ccc/"}}
        called = []

        def manage_store(identity):
            called.append(True)
            return "wrote"

        checked = _make_auth_checked(manage_store, {"edit_config_store"}, caps)

        with pytest.raises(jsonrpc.Error) as exc_info:
            checked(identity="bbbXXX")

        assert exc_info.value.code == jsonrpc.UNAUTHORIZED
        assert called == []


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

    @pytest.mark.parametrize("method_names, capability", [
        (STATUS_METHODS, CLEAR_AGENT_STATUS),
        (START_STOP_METHODS, START_STOP_AGENTS),
        (STOP_PLATFORM_METHODS, STOP_PLATFORM),
        (TAG_AGENT_METHODS, TAG_AGENTS),
        (INSTALL_REMOVE_METHODS, INSTALL_REMOVE_AGENTS)
    ])
    def test_privileged_method_has_correct_annotation(
        self, method_names, capability, control_mod
    ):
        for method_name in method_names:
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
