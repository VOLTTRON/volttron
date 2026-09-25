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

# _match_shell_var backs _iter_shell_vars, which lsb_release() uses to parse
# /etc/lsb-release-style KEY=VALUE lines. These fix the exact set of lines
# that matching must keep accepting and rejecting unchanged.

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
def test_match_shell_var_valid_input_unchanged(line, expected):
    assert resmon._match_shell_var(line) == expected


# A trailing, unescaped-by-parity backslash right before the closing quote,
# with no quote later in the line: the historical pattern still closed the
# value there instead of leaving it unterminated. These pin that so a
# performance fix cannot silently change what a value like this means.
ESCAPED_FINAL_DELIMITER_CASES = [
    ('FOO="a#\\"', ('FOO', '"a#\\"')),
    ('FOO="\\"', ('FOO', '"\\"')),
    ('FOO="ab\\\\"', ('FOO', '"ab\\\\"')),
]


@pytest.mark.parametrize('line, expected', ESCAPED_FINAL_DELIMITER_CASES)
def test_match_shell_var_escaped_final_delimiter_keeps_old_meaning(line, expected):
    assert resmon._match_shell_var(line) == expected


def test_iter_shell_vars_strips_quotes():
    lines = ['DISTRIB_ID=Ubuntu\n', 'DISTRIB_DESCRIPTION="Ubuntu 22.04.3 LTS"\n']
    result = dict(resmon._iter_shell_vars(lines))
    assert result == {
        'DISTRIB_ID': 'Ubuntu',
        'DISTRIB_DESCRIPTION': 'Ubuntu 22.04.3 LTS',
    }


def test_match_shell_var_pathological_input_stays_bounded():
    # A payload only a linear scan finishes quickly: a long backslash run
    # with no closing quote at all, so a backtracking scan would have to
    # explore every way to split the ambiguous escape before giving up.
    payload = 'KEY="' + '\\' * 100000
    start = time.monotonic()
    resmon._match_shell_var(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
