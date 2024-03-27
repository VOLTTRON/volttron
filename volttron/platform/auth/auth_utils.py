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

import re

_dump_re = re.compile(r"([,\\])")
_load_re = re.compile(r"\\(.)|,")

def isregex(obj):
    return len(obj) > 1 and obj[0] == obj[-1] == "/"

def dump_user(*args):
    return ",".join([_dump_re.sub(r"\\\1", arg) for arg in args])


def load_user(string):
    def sub(match):
        return match.group(1) or "\x00"

    return _load_re.sub(sub, string).split("\x00")
