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
"""vctl rejects a --timeout that is not a finite number greater than 0, from
the command line and from the config file (#3367)."""

import io
import sys
from types import SimpleNamespace

import pytest

from volttron.platform.control import control_parser

REJECTED = ["inf", "-inf", "nan", "0", "-1", "abc", ""]


@pytest.fixture
def run_vctl(monkeypatch, tmp_path):
    """Runs main() with the parser unstubbed; the connection, platform setup
    and logging are stubbed, and each connection made is recorded."""
    stderr = io.StringIO()
    seen = {}
    connections = []

    def run(argv, config_text=None):
        if config_text is not None:
            (tmp_path / "config").write_text(config_text)
            monkeypatch.delenv("SKIP_VOLTTRON_CONFIG", raising=False)
        else:
            monkeypatch.setenv("SKIP_VOLTTRON_CONFIG", "1")
        monkeypatch.setattr(sys, "argv", ["vctl"] + argv)
        return control_parser.main()

    monkeypatch.setattr(control_parser, "get_home", lambda: str(tmp_path))
    monkeypatch.setattr(control_parser, "_stderr", stderr)
    monkeypatch.setattr(control_parser, "log_to_file", lambda *a, **k: None)
    monkeypatch.setattr(control_parser.utils, "is_volttron_running",
                        lambda home: True)

    def connect(address):
        connections.append(address)
        return SimpleNamespace(kill=lambda: None)

    monkeypatch.setattr(control_parser, "ControlConnection", connect)
    monkeypatch.setattr(control_parser, "list_peers", lambda opts: 0)

    def setup_platform(opts):
        seen["timeout"] = opts.timeout
        return SimpleNamespace(setup=lambda: None)

    monkeypatch.setattr(control_parser.aipmod, "AIPplatform", setup_platform)
    run.stderr = stderr
    run.seen = seen
    run.connections = connections
    return run


@pytest.mark.parametrize("value", REJECTED)
def test_command_line_rejects_invalid_timeout(run_vctl, capsys, value):
    with pytest.raises(SystemExit) as exc:
        run_vctl(["--timeout=" + value, "peerlist"])

    assert exc.value.code == 2
    assert "--timeout" in capsys.readouterr().err
    assert "timeout" not in run_vctl.seen
    assert run_vctl.connections == []


@pytest.mark.parametrize("value", ["inf", "nan", "0", "-1"])
def test_config_file_rejects_invalid_timeout(run_vctl, capsys, value):
    with pytest.raises(SystemExit) as exc:
        run_vctl(["peerlist"], config_text="timeout = {}\n".format(value))

    assert exc.value.code == 2
    assert "--timeout" in capsys.readouterr().err
    assert "timeout" not in run_vctl.seen
    assert run_vctl.connections == []


@pytest.mark.parametrize("value,expected", [("0.5", 0.5), ("60", 60.0)])
def test_valid_timeout_is_kept(run_vctl, value, expected):
    run_vctl(["--timeout", value, "peerlist"])

    assert run_vctl.seen["timeout"] == expected
    assert len(run_vctl.connections) == 1


def test_default_timeout_is_60(run_vctl):
    run_vctl(["peerlist"])

    assert run_vctl.seen["timeout"] == 60


MAX_ENV = "VOLTTRON_VCTL_MAX_TIMEOUT"


def test_maximum_timeout_is_300_seconds():
    assert control_parser.MAX_TIMEOUT_SECONDS == 300


def test_timeout_at_the_maximum_is_kept(run_vctl, monkeypatch):
    monkeypatch.delenv(MAX_ENV, raising=False)

    run_vctl(["--timeout", "300", "peerlist"])

    assert run_vctl.seen["timeout"] == 300.0
    assert len(run_vctl.connections) == 1


def test_timeout_above_the_maximum_is_rejected(run_vctl, monkeypatch, capsys):
    monkeypatch.delenv(MAX_ENV, raising=False)

    with pytest.raises(SystemExit) as exc:
        run_vctl(["--timeout", "300.5", "peerlist"])

    err = capsys.readouterr().err
    assert exc.value.code == 2
    assert "300" in err
    assert MAX_ENV in err
    assert "timeout" not in run_vctl.seen
    assert run_vctl.connections == []


def test_config_file_timeout_above_the_maximum_is_rejected(
        run_vctl, monkeypatch, capsys):
    monkeypatch.delenv(MAX_ENV, raising=False)

    with pytest.raises(SystemExit) as exc:
        run_vctl(["peerlist"], config_text="timeout = 301\n")

    assert exc.value.code == 2
    assert MAX_ENV in capsys.readouterr().err
    assert run_vctl.connections == []


def test_environment_raises_the_maximum(run_vctl, monkeypatch, capsys):
    monkeypatch.setenv(MAX_ENV, "600")

    run_vctl(["--timeout", "600", "peerlist"])
    assert run_vctl.seen["timeout"] == 600.0

    with pytest.raises(SystemExit) as exc:
        run_vctl(["--timeout", "601", "peerlist"])
    assert exc.value.code == 2
    assert "600" in capsys.readouterr().err


def test_environment_lowers_the_maximum(run_vctl, monkeypatch):
    monkeypatch.setenv(MAX_ENV, "10")

    with pytest.raises(SystemExit) as exc:
        run_vctl(["--timeout", "11", "peerlist"])

    assert exc.value.code == 2


@pytest.mark.parametrize("value", ["nan", "inf", "0", "-1", "abc", ""])
def test_invalid_environment_maximum_is_a_usage_error(
        run_vctl, monkeypatch, capsys, value):
    monkeypatch.setenv(MAX_ENV, value)

    with pytest.raises(SystemExit) as exc:
        run_vctl(["--timeout", "5", "peerlist"])

    assert exc.value.code == 2
    assert MAX_ENV in capsys.readouterr().err
    assert run_vctl.connections == []
