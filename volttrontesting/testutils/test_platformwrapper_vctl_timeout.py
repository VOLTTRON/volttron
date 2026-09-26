"""Issue #3330: vctl's own --timeout defaults to 60s and wraps the whole
remote call, including the platform's stop of the agent process (up to
120s worst case in aip.py's ExecutionEnvironment.stop). remove_agent and
stop_agent must pass an explicit --timeout above that budget so a slow
but successful removal on a loaded runner does not report a false
failure, and must warn (not fail) when the platform actually needed to
escalate past SIGINT. No running platform is needed: execute_command and
the wall clock are patched so the vctl command line and the log output
are inspected directly.
"""
import logging
import os
import shutil

from mock import MagicMock, patch

from volttrontesting.utils.platformwrapper import PlatformWrapper

# The platform's worst-case stop budget (aip.py: 60 + 30 + 30 across
# SIGINT/SIGTERM/SIGKILL). The vctl --timeout the harness passes must
# clear it; import-free so a missing flag fails as an assertion, not an
# ImportError.
PLATFORM_WORST_CASE_STOP_SECONDS = 120

# aip.py's SIGINT wait, past which _execute_vctl_stop_or_remove warns.
SIGINT_WAIT_SECONDS = 60


def _stub_platform_wrapper() -> PlatformWrapper:
    """A PlatformWrapper with no running platform: dynamic_agent is a
    MagicMock whose peerlist() reports no control connection, so
    __wait_for_control_connection_to_exit__ returns on its first check."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=False)
    p.dynamic_agent = MagicMock()
    p.dynamic_agent.vip.peerlist.return_value.get.return_value = []
    return p


def _cleanup(p: PlatformWrapper):
    p.skip_cleanup = True
    shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


def _vctl_calls(mock_execute_command, subcommand: str):
    """Every execute_command call whose vctl command line names
    subcommand, e.g. 'remove' or 'stop'."""
    return [args[0] for args, _kwargs in mock_execute_command.call_args_list
           if subcommand in args[0]]


def _assert_timeout_clears_stop_budget(cmd):
    assert '--timeout' in cmd, f"no --timeout flag in {cmd}"
    value = int(cmd[cmd.index('--timeout') + 1])
    assert value > PLATFORM_WORST_CASE_STOP_SECONDS, value


def test_remove_agent_passes_vctl_timeout_above_stop_budget():
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec:
            mock_exec.return_value = ""
            p.remove_agent("some-uuid")

        remove_calls = _vctl_calls(mock_exec, 'remove')
        assert len(remove_calls) == 1, remove_calls
        _assert_timeout_clears_stop_budget(remove_calls[0])
    finally:
        _cleanup(p)


def test_stop_agent_passes_vctl_timeout_above_stop_budget():
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec:
            mock_exec.return_value = ""
            p.stop_agent("some-uuid")

        stop_calls = _vctl_calls(mock_exec, 'stop')
        assert len(stop_calls) == 1, stop_calls
        _assert_timeout_clears_stop_budget(stop_calls[0])
    finally:
        _cleanup(p)


def test_remove_agent_warns_when_stop_needed_escalation(caplog):
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec, \
             patch('volttrontesting.utils.platformwrapper.time.monotonic',
                   side_effect=[0.0, SIGINT_WAIT_SECONDS + 1]):
            mock_exec.return_value = ""
            with caplog.at_level(logging.WARNING, logger="volttrontesting.utils.platformwrapper"):
                p.remove_agent("some-uuid")

        assert any("some-uuid" in r.message and "escalation" in r.message
                  for r in caplog.records), caplog.text
    finally:
        _cleanup(p)


def test_remove_agent_does_not_warn_under_sigint_wait(caplog):
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec, \
             patch('volttrontesting.utils.platformwrapper.time.monotonic',
                   side_effect=[0.0, SIGINT_WAIT_SECONDS - 1]):
            mock_exec.return_value = ""
            with caplog.at_level(logging.WARNING, logger="volttrontesting.utils.platformwrapper"):
                p.remove_agent("some-uuid")

        assert not any("escalation" in r.message for r in caplog.records), caplog.text
    finally:
        _cleanup(p)


def test_stop_agent_warns_when_stop_needed_escalation(caplog):
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec, \
             patch('volttrontesting.utils.platformwrapper.time.monotonic',
                   side_effect=[0.0, SIGINT_WAIT_SECONDS + 1]):
            mock_exec.return_value = ""
            with caplog.at_level(logging.WARNING, logger="volttrontesting.utils.platformwrapper"):
                p.stop_agent("some-uuid")

        assert any("some-uuid" in r.message and "escalation" in r.message
                  for r in caplog.records), caplog.text
    finally:
        _cleanup(p)
