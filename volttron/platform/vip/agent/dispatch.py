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



import weakref


__all__ = ['Signal']


class Signal:
    def __init__(self):
        self._receivers = weakref.WeakValueDictionary()

    def connect(self, receiver, owner=None):
        self._receivers[receiver] = receiver if owner is None else owner

    def disconnect(self, receiver):
        try:
            self._receivers.pop(receiver)
            return True
        except KeyError:
            return False

    def send(self, sender, **kwargs):
        return [receiver(sender, **kwargs)
                for receiver in self._receivers]

    def sendby(self, executor, sender, **kwargs):
        return [executor(receiver, sender, **kwargs)
                for receiver in self._receivers]

    def receiver(self, func):
        self.connect(func)
        return func

    def __bool__(self):
        return bool(self._receivers)
