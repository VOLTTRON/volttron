"""Unit tests for the key-variable check at the top of utils.vip_main (#3344).

Run outside the platform with no keys, vip_main raises a ValueError naming
the environment variables to set. Those names must be the ones the code reads.
"""
import re

import pytest

from volttron.platform.agent import utils

PUBLIC_VAR = "AGENT_PUBLICKEY"
SECRET_VAR = "AGENT_SECRETKEY"
DUMMY_PUBLIC = "dummy-public-key"
DUMMY_SECRET = "dummy-secret-key"


class ReachedAgentClass(Exception):
    """Raised by the stand-in agent class to stop vip_main after the check."""


class RecordingAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        raise ReachedAgentClass(self)


@pytest.fixture(autouse=True)
def standalone_env(monkeypatch):
    for name in (PUBLIC_VAR, SECRET_VAR, "AGENT_PUBLIC", "AGENT_SECRET",
                 "VOLTTRON_SERVERKEY", "_LAUNCHED_BY_PLATFORM"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(utils, "isapipe", lambda fd: False)
    monkeypatch.setattr(utils, "get_address", lambda: "ipc://@dummy")
    monkeypatch.setattr(utils, "get_home", lambda: "/dummy-home")
    monkeypatch.setattr("volttron.platform.auth.certs.Certs", lambda: object())


def missing_keys_message():
    with pytest.raises(ValueError) as excinfo:
        utils.vip_main(RecordingAgent)
    return str(excinfo.value)


def test_missing_keys_message_names_the_variables_the_code_reads():
    message = missing_keys_message()

    assert PUBLIC_VAR in message
    assert SECRET_VAR in message
    assert "run without the platform" in message


def test_setting_the_variables_the_message_names_gets_past_the_check(monkeypatch):
    named = re.findall(r"AGENT_[A-Z]+", missing_keys_message())
    assert len(named) == 2

    for name in named:
        monkeypatch.setenv(name, "dummy-value")

    with pytest.raises(ReachedAgentClass):
        utils.vip_main(RecordingAgent)


def test_keys_from_environment_reach_the_agent_class(monkeypatch):
    monkeypatch.setenv(PUBLIC_VAR, DUMMY_PUBLIC)
    monkeypatch.setenv(SECRET_VAR, DUMMY_SECRET)

    with pytest.raises(ReachedAgentClass) as excinfo:
        utils.vip_main(RecordingAgent)

    agent = excinfo.value.args[0]
    assert agent.kwargs["publickey"] == DUMMY_PUBLIC
    assert agent.kwargs["secretkey"] == DUMMY_SECRET


def test_only_one_key_variable_is_still_refused(monkeypatch):
    monkeypatch.setenv(PUBLIC_VAR, DUMMY_PUBLIC)

    with pytest.raises(ValueError, match=SECRET_VAR):
        utils.vip_main(RecordingAgent)


def test_launched_by_platform_skips_the_check(monkeypatch):
    monkeypatch.setenv("_LAUNCHED_BY_PLATFORM", "1")

    with pytest.raises(ReachedAgentClass):
        utils.vip_main(RecordingAgent)
