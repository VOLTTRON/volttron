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

'''gevent-safe interface to Linux inotify system calls.'''

import errno as errno
import sys

import gevent
from gevent.select import select

from . import IN_NONBLOCK, _inotify, _main
import logging

_log = logging.getLogger(__name__)


class inotify(_inotify):
    class _lock_class:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            pass

    def __init__(self, flags=0):
        try:
            super(inotify, self).__init__(flags | IN_NONBLOCK)
        except Exception as e:
            # Could happen due to I/O errors. Example - too many open files
            _log.error("Error instantiating inotify. "
                      "Auth files will not be monitored for updates. Exception: {}".format(e))
            raise e

    def read(self):
        while True:
            try:
                return super(inotify, self).read()
            except OSError as exc:
                if exc.errno != errno.EAGAIN:
                    raise
            select([self], [], [])


if __name__ == '__main__':
    try:
        gevent.spawn(_main, sys.argv, inotify).join()
    except KeyboardInterrupt:
        pass
