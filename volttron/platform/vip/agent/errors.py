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



import errno


__all__ = ['VIPError', 'Unreachable', 'Again', 'UnknownSubsystem']


class VIPError(Exception):
    def __init__(self, errnum, msg, peer, subsystem, *args):
        super(VIPError, self).__init__(errnum, msg, peer, subsystem, *args)
        self.errno = int(errnum)
        self.msg = msg
        self.peer = peer
        self.subsystem = subsystem

    def __str__(self):
        return 'VIP error (%d): %s' % (self.errno, self.msg)

    def __repr__(self):
        return '%s%r' % (type(self).__name__, self.args)

    @classmethod
    def from_errno(cls, errnum, msg, *args):
        errnum = int(errnum)
        return {
            errno.EHOSTUNREACH: Unreachable,
            errno.EAGAIN: Again,
            errno.EPROTONOSUPPORT: UnknownSubsystem,
        }.get(errnum, cls)(errnum, msg, *args)


class Unreachable(VIPError):
    def __str__(self):
        return '%s: %s' % (super(Unreachable, self).__str__(), self.peer)


class Again(VIPError):
    pass


class UnknownSubsystem(VIPError):
    def __str__(self):
        return '%s: %s' % (
            super(UnknownSubsystem, self).__str__(), self.subsystem)
