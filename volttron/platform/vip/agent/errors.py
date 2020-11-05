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
