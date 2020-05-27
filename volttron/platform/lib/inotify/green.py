# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

'''gevent-safe interface to Linux inotify system calls.'''

import errno as errno
import sys

import gevent
from gevent.select import select

from . import _inotify, __all__, _main
from . import *
import logging

_log = logging.getLogger(__name__)


class inotify(_inotify):
    class _lock_class(object):
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
