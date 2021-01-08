# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

'''Interface to Linux inotify system calls.'''



from collections import namedtuple
import ctypes
from ctypes import c_int, c_long, c_uint32, c_char_p
import os
import struct
import sys
from threading import RLock


__all__ = ['inotify']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__version__ = '2.0'


IN_ACCESS = 0x00000001   # File was accessed
IN_MODIFY = 0x00000002   # File was modified
IN_ATTRIB = 0x00000004   # Metadata changed
IN_CLOSE_WRITE = 0x00000008   # Writtable file was closed
IN_CLOSE_NOWRITE = 0x00000010   # Unwrittable file closed
IN_OPEN = 0x00000020   # File was opened
IN_MOVED_FROM = 0x00000040   # File was moved from X
IN_MOVED_TO = 0x00000080   # File was moved to Y
IN_CREATE = 0x00000100   # Subfile was created
IN_DELETE = 0x00000200   # Subfile was deleted
IN_DELETE_SELF = 0x00000400   # Self was deleted
IN_MOVE_SELF = 0x00000800   # Self was moved

# the following are legal events.  they are sent as needed to any watch
IN_UNMOUNT = 0x00002000   # Backing fs was unmounted
IN_Q_OVERFLOW = 0x00004000   # Event queued overflowed
IN_IGNORED = 0x00008000   # File was ignored

# helper events
IN_CLOSE = (IN_CLOSE_WRITE | IN_CLOSE_NOWRITE)   # close
IN_MOVE = (IN_MOVED_FROM | IN_MOVED_TO)   # moves

# special flags
IN_ONLYDIR = 0x01000000   # only watch the path if it is a directory
IN_DONT_FOLLOW = 0x02000000   # don't follow a sym link
IN_EXCL_UNLINK = 0x04000000   # exclude events on unlinked objects
IN_MASK_ADD = 0x20000000   # add to the mask of an already existing watch
IN_ISDIR = 0x40000000   # event occurred against dir
IN_ONESHOT = 0x80000000   # only send event once

# All of the events - we build the list by hand so that we can add flags in
# the future and not break backward compatibility.  Apps will get only the
# events that they originally wanted.  Be sure to add new events here!
IN_ALL_EVENTS = (IN_ACCESS | IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE |
                 IN_CLOSE_NOWRITE | IN_OPEN | IN_MOVED_FROM | IN_MOVED_TO |
                 IN_DELETE | IN_CREATE | IN_DELETE_SELF | IN_MOVE_SELF)

# Flags for sys_inotify_init1.
IN_CLOEXEC = 0o2000000   # O_CLOEXEC
IN_NONBLOCK = os.O_NONBLOCK


__all__.extend(name for name in dir() if name.startswith('IN_'))


_libc = ctypes.CDLL(None)
inotify_init = ctypes.CFUNCTYPE(c_int, c_int, use_errno=True)(
    ('inotify_init1', _libc), ((1, 'flags', 0),))
inotify_add_watch = ctypes.CFUNCTYPE(
    c_int, c_int, c_char_p, c_uint32, use_errno=True)(
        ('inotify_add_watch', _libc),
        ((1, 'fd'), (1, 'pathname'), (1, 'mask', IN_ALL_EVENTS)))
inotify_rm_watch = ctypes.CFUNCTYPE(c_int, c_int, c_int, use_errno=True)(
    ('inotify_rm_watch', _libc), ((1, 'fd'), (1, 'wd')))

def _errcheck(result, func, args):
    if result == -1:
        errnum = ctypes.get_errno()
        raise OSError(errnum, os.strerror(errnum))
    return result or None

inotify_init.errcheck = _errcheck
inotify_add_watch.errcheck = _errcheck
inotify_rm_watch.errcheck = _errcheck


Event = namedtuple('Event', 'pathname mask cookie name')


class _inotify(object):
    def __init__(self, flags=0):
        self._fd = inotify_init(flags)
        self._watch_wds = {}
        self._watch_names = {}
        self._buf = ''
        self._lock = self._lock_class()

    def __del__(self):
        self.close()

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def add_watch(self, pathname, mask=IN_ALL_EVENTS):
        wd = inotify_add_watch(self.fileno(), pathname.encode("utf-8"), mask | IN_IGNORED)
        with self._lock:
            self._watch_names[pathname] = wd
            self._watch_wds[wd] = (pathname, mask)

    def rm_watch(self, pathname):
        with self._lock:
            wd = self._watch_names.pop(pathname)
        inotify_rm_watch(self.fileno(), wd)

    def read(self):
        while True:
            if self._buf:
                data = self._buf
            else:
                data = os.read(self.fileno(), 8192)
                if not data:
                    return
            wd, mask, cookie, length = struct.unpack_from('iIII', data)
            name = data[16:16+length].rstrip(b'\0')
            self._buf = data[16+length:]
            with self._lock:
                try:
                    pathname, masked = self._watch_wds[wd]
                except KeyError:
                    inotify_rm_watch(self.fileno(), wd)
                    continue
                if mask & IN_IGNORED:
                    self._watch_wds.pop(wd)
                    rmwd = self._watch_names.pop(pathname, None)
                    if wd != rmwd:
                        self._watch_names[pathname] = rmwd
                    if not mask & masked:
                        continue
            break
        return Event(pathname, mask, cookie, name)

    def fileno(self):
        if self._fd is None:
            raise ValueError('I/O operation on closed file')
        return self._fd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __next__(self):
        return self.read()

    def __iter__(self):
        return self


class inotify(_inotify):
    _lock_class = lambda s: RLock()


def _main(argv, inotify_cls):
    masks = sorted((name[3:], value) for name, value in globals().items()
                   if name.startswith('IN_') and
                   name not in ['IN_NONBLOCK', 'IN_CLOEXEC', 'IN_ALL_EVENTS',
                                'IN_CLOSE', 'IN_MOVE'])
    with inotify_cls() as inot:
        for pathname in argv[1:]:
            try:
                inot.add_watch(pathname)
            except OSError as exc:
                print('%s: error: %s: %s' % (
                    os.path.basename(argv[0]), exc, pathname), file=sys.stderr)
                sys.exit(1)
        for event in inot:
            if event.name:
                pathname = os.path.join(event.pathname, event.name)
            else:
                pathname = event.pathname
            events = '|'.join(name for name, value in masks
                              if event.mask & value)
            parts = [pathname, events]
            if event.mask & IN_MOVE:
                parts.append(str(event.cookie))
            print(*parts, sep='  ')


if __name__ == '__main__':
    try:
        _main(sys.argv, inotify)
    except KeyboardInterrupt:
        pass
