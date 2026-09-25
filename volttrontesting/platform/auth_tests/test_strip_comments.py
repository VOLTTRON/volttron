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

from volttron.platform.agent.utils import strip_comments

# strip_comments backs the JSON-with-comments parser volttron config
# loading uses; this pins the comment-stripping regex against
# backtracking and against the exact set of inputs it already handles.

VALID_CASES = [
    ('{"a": "b"}', '{"a": "b"}'),
    ('{"a": "b\\"c"}', '{"a": "b\\"c"}'),
    ("{'a': 'b\\'c'}", "{'a': 'b\\'c'}"),
    ('{"a": "b"} // trailing comment\n{"c": "d"}', '{"a": "b"} \n{"c": "d"}'),
    ('{"a": "b"} # hash comment\n{"c": "d"}', '{"a": "b"} \n{"c": "d"}'),
    ('/* block */ {"a": 1}', ' {"a": 1}'),
    ('{"path": "C:\\\\Users\\\\a"}', '{"path": "C:\\\\Users\\\\a"}'),
]


@pytest.mark.parametrize('source, expected', VALID_CASES)
def test_strip_comments_valid_input_unchanged(source, expected):
    assert strip_comments(source) == expected


# A trailing, unescaped-by-parity backslash right before the closing
# quote, with no quote later in the string: the historical pattern still
# closed the string there instead of leaving it unterminated. Pinned so a
# performance fix cannot silently change what a string like this means.
# Each case leaves a comment marker inside what should still be the
# string; without the recovered close, that marker reads as a real
# comment and gets stripped, so these fail against the un-recovered
# regex even though the string itself never actually terminates cleanly.
ESCAPED_FINAL_DELIMITER_CASES = [
    ('"a // b\\"', '"a // b\\"'),
    ('"a # b\\"', '"a # b\\"'),
    ("'a // b\\'", "'a // b\\'"),
    ('"a /* b */ c\\"', '"a /* b */ c\\"'),
]


@pytest.mark.parametrize('source, expected', ESCAPED_FINAL_DELIMITER_CASES)
def test_strip_comments_escaped_final_delimiter_keeps_old_meaning(source, expected):
    assert strip_comments(source) == expected


def test_strip_comments_pathological_input_stays_bounded():
    # A payload only a linear scan finishes quickly: many escaped-quote
    # pairs with nothing to close the string, at a size a backtracking or
    # quadratic-retry scan could not clear in the bound below.
    payload = '{"a": "' + '\\"' * 50000
    start = time.monotonic()
    strip_comments(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
