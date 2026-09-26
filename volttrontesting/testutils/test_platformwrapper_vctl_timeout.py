"""Issue #3330: vctl's own --timeout defaults to 60s and wraps the whole
remote call, including the platform's stop of the agent process (up to
120s worst case in aip.py's ExecutionEnvironment.stop). remove_agent and
stop_agent must pass an explicit --timeout above that budget so a slow
but successful removal on a loaded runner does not report a false
failure. No running platform is needed: execute_command is patched so
the vctl command line is inspected directly.
"""
import os
import shutil

from mock import MagicMock, patch

from volttrontesting.utils.platformwrapper import (PlatformWrapper,
                                                    VCTL_STOP_BUDGET_TIMEOUT)


def _stub_platform_wrapper() -> PlatformWrapper:
    """A PlatformWrapper with no running platform: dynamic_agent is a
    MagicMock whose peerlist() reports no control connection, so
    __wait_for_control_connection_to_exit__ returns on its first check."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=False)
    p.dynamic_agent = MagicMock()
    p.dynamic_agent.vip.peerlist.return_value.get.return_value = []
    return p


def _vctl_calls(mock_execute_command, subcommand: str):
    """Every execute_command call whose vctl command line names
    subcommand, e.g. 'remove' or 'stop'."""
    return [args[0] for args, _kwargs in mock_execute_command.call_args_list
           if subcommand in args[0]]


def test_remove_agent_passes_vctl_timeout_above_stop_budget():
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec:
            mock_exec.return_value = ""
            p.remove_agent("some-uuid")

        remove_calls = _vctl_calls(mock_exec, 'remove')
        assert len(remove_calls) == 1, remove_calls
        cmd = remove_calls[0]
        assert '--timeout' in cmd, cmd
        assert cmd[cmd.index('--timeout') + 1] == str(VCTL_STOP_BUDGET_TIMEOUT), cmd
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


def test_stop_agent_passes_vctl_timeout_above_stop_budget():
    p = _stub_platform_wrapper()
    try:
        with patch('volttrontesting.utils.platformwrapper.execute_command') as mock_exec:
            mock_exec.return_value = ""
            p.stop_agent("some-uuid")

        stop_calls = _vctl_calls(mock_exec, 'stop')
        assert len(stop_calls) == 1, stop_calls
        cmd = stop_calls[0]
        assert '--timeout' in cmd, cmd
        assert cmd[cmd.index('--timeout') + 1] == str(VCTL_STOP_BUDGET_TIMEOUT), cmd
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)
