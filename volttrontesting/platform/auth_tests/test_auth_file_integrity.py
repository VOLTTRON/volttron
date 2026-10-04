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
# }}}
"""A reload, a failed write or a busy lock must never leave auth.json, or
what a later change is built from, older or emptier than the file was
(#3320)."""

import errno
import os

import gevent
import gevent.event
import pytest

from volttron.platform.auth import AuthFile
from volttron.platform.auth import auth_file as auth_file_module
from volttron.platform.auth.auth_file import AuthFileReadError
from volttrontesting.platform.auth_tests.test_auth_file_lock import (
    _bytes, _entry, _seed, _users)


@pytest.fixture
def auth_path(tmp_path):
    return str(tmp_path / "auth.json")


class _PausedReload(AuthFile):
    """Stops a reload greenlet just before it replaces auth_data, standing
    in for the watcher thread being preempted there."""

    reloader = None

    def __init__(self, *args, **kwargs):
        self.reached = gevent.event.Event()
        self.resume = gevent.event.Event()
        super().__init__(*args, **kwargs)

    @property
    def auth_data(self):
        return self.__dict__["auth_data"]

    @auth_data.setter
    def auth_data(self, value):
        if gevent.getcurrent() is self.reloader:
            self.reached.set()
            self.resume.wait(timeout=5)
        self.__dict__["auth_data"] = value


@pytest.mark.auth
@pytest.mark.parametrize("reload", ["load", "load_allow_snapshot"])
def test_reload_cannot_replace_the_data_a_change_is_built_from(auth_path,
                                                               monkeypatch,
                                                               reload):
    _seed(auth_path)
    auth_file = _PausedReload(auth_path)
    other_file = AuthFile(auth_path)
    test_greenlet = gevent.getcurrent()
    read = auth_file.read

    def yield_then_read():
        if gevent.getcurrent() is test_greenlet:
            # The watcher runs on its own thread, so it can run here, after
            # the change has loaded the file and before it uses auth_data.
            auth_file.resume.set()
            gevent.sleep(0)
        return read()

    monkeypatch.setattr(auth_file, "read", yield_then_read)

    auth_file.reloader = gevent.spawn(getattr(auth_file, reload))
    assert auth_file.reached.wait(timeout=5)
    other = gevent.spawn(other_file.add, _entry("x", "X"))
    other.join(timeout=0.5)
    if "x" not in _users(auth_path):
        # The reload still holds the lock, so release it on a timer rather
        # than from inside the change below.
        gevent.spawn_later(0.3, auth_file.resume.set)

    auth_file.add(_entry("y", "Y"))
    other.join(timeout=5)
    auth_file.reloader.join(timeout=5)

    assert other.successful()
    assert set(_users(auth_path)) == {"x", "y"}


class _FailingWrite:
    """A file whose write puts the first `written` bytes on disk and then
    fails, as a full disk does."""

    def __init__(self, fil, written):
        self.fil = fil
        self.written = written

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.fil.close()

    def write(self, text):
        self.fil.write(text[:self.written])
        self.fil.flush()
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))


@pytest.mark.auth
@pytest.mark.parametrize("written", [0, 10])
def test_failed_write_leaves_a_file_the_next_change_refuses(auth_path,
                                                             monkeypatch,
                                                             written):
    _seed(auth_path, [_entry("x", "X")])
    writer = AuthFile(auth_path)

    def failing_open(path, mode="r", *args, **kwargs):
        fil = open(path, mode, *args, **kwargs)
        return _FailingWrite(fil, written) if "w" in mode else fil

    monkeypatch.setattr(auth_file_module, "open", failing_open,
                        raising=False)
    with pytest.raises(OSError):
        writer.add(_entry("y", "Y"))
    monkeypatch.delattr(auth_file_module, "open")
    torn = _bytes(auth_path)

    with pytest.raises(AuthFileReadError):
        AuthFile(auth_path).add(_entry("z", "Z"))

    assert len(torn) == written
    assert _bytes(auth_path) == torn


@pytest.mark.auth
def test_missing_file_is_created_and_takes_a_change(auth_path):
    AuthFile(auth_path).add(_entry("x", "X"))

    assert _users(auth_path) == ["x"]
