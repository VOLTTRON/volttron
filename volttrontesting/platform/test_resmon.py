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

import time

import pytest

from volttron.platform import resmon

# _var_re backs _iter_shell_vars, which lsb_release() uses to parse
# /etc/lsb-release-style KEY=VALUE lines. These fix the exact set of lines
# that pattern must keep accepting and rejecting unchanged.

VALID_CASES = [
    ('DISTRIB_ID=Ubuntu', ('DISTRIB_ID', 'Ubuntu')),
    ('DISTRIB_DESCRIPTION="Ubuntu 22.04.3 LTS"',
     ('DISTRIB_DESCRIPTION', '"Ubuntu 22.04.3 LTS"')),
    ('FOO="a \\"quoted\\" value"', ('FOO', '"a \\"quoted\\" value"')),
    ("FOO='single quoted'", ('FOO', "'single quoted'")),
    ('FOO=bar # trailing comment', ('FOO', 'bar')),
    ('FOO="with space" # comment', ('FOO', '"with space"')),
    ('FOO=', ('FOO', '')),
    ('FOO="path\\\\to\\\\thing"', ('FOO', '"path\\\\to\\\\thing"')),
]


@pytest.mark.parametrize('line, expected', VALID_CASES)
def test_var_re_valid_input_unchanged(line, expected):
    match = resmon._var_re.match(line)
    assert match.groups() == expected


def test_iter_shell_vars_strips_quotes():
    lines = ['DISTRIB_ID=Ubuntu\n', 'DISTRIB_DESCRIPTION="Ubuntu 22.04.3 LTS"\n']
    result = dict(resmon._iter_shell_vars(lines))
    assert result == {
        'DISTRIB_ID': 'Ubuntu',
        'DISTRIB_DESCRIPTION': 'Ubuntu 22.04.3 LTS',
    }


def test_var_re_pathological_input_stays_bounded():
    # [^"] overlapped \\., so a backslash run before an unterminated quote
    # backtracked over every split between the escape and fallback branches.
    payload = 'KEY="' + '\\' * 36
    start = time.time()
    resmon._var_re.match(payload)
    elapsed = time.time() - start
    assert elapsed < 2.0
