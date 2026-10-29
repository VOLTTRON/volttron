"""vcfg installs of agents that need more than the vctl --timeout maximum
raise the maximum for that one subprocess only (#3367)."""

import os

import pytest

from volttron.platform import instance_setup

MAX_ENV = "VOLTTRON_VCTL_MAX_TIMEOUT"


@pytest.fixture
def popen_calls(monkeypatch):
    calls = []

    class FakeProcess:
        returncode = 0

        def communicate(self):
            return b"", b""

    def fake_popen(cmdargs, env=None, **kwargs):
        calls.append((list(cmdargs), env))
        return FakeProcess()

    monkeypatch.setattr(instance_setup, "Popen", fake_popen)
    monkeypatch.setattr(instance_setup, "verbose", False, raising=False)
    monkeypatch.delenv(MAX_ENV, raising=False)
    return calls


@pytest.mark.parametrize("tag", ["vc", "platform_driver"])
def test_long_install_runs_with_raised_maximum(popen_calls, tag):
    instance_setup._install_agent("agent_dir", "cfg.json", tag, None)

    cmd, env = popen_calls[0]
    assert cmd[cmd.index("--timeout") + 1] == "360"
    assert env[MAX_ENV] == "360"
    assert MAX_ENV not in os.environ


def test_other_install_does_not_raise_maximum(popen_calls):
    instance_setup._install_agent("agent_dir", "cfg.json", "listener", None)

    cmd, env = popen_calls[0]
    assert "--timeout" not in cmd
    assert MAX_ENV not in env


def test_other_commands_do_not_raise_maximum(popen_calls):
    instance_setup._cmd(["volttron-ctl", "enable", "--tag", "vc"])

    assert MAX_ENV not in popen_calls[0][1]
