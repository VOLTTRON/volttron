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


class FrozenDict(dict):
    """
    A wrapper around a dictionary that allows us to "freeze" a dictionary so that
    we can no longer set values on the object itself.  This does that we can't
    change the value instance object if its mutable.
    """
    def __init__(self, *args, **kwargs):
        self._frozen = False
        dict.__init__(self, *args, **kwargs)

    def freeze(self):
        self._frozen = True

    def __setitem__(self, key, value):
        if (self._frozen):
            raise TypeError("Attempted assignment to a frozen dict")
        else:
            return dict.__setitem__(self, key, value)
