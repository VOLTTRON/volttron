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

# Pins strip_comments output on inputs it already handled, and bounds its
# running time on inputs that made the earlier pattern backtrack.

VALID_CASES = [
    ('{"a": "b"}', '{"a": "b"}'),
    ('{"a": "b\\"c"}', '{"a": "b\\"c"}'),
    ("{'a': 'b\\'c'}", "{'a': 'b\\'c'}"),
    ('{"a": "b"} // trailing comment\n{"c": "d"}', '{"a": "b"} \n{"c": "d"}'),
    ('{"a": "b"} # hash comment\n{"c": "d"}', '{"a": "b"} \n{"c": "d"}'),
    ('/* block */ {"a": 1}', ' {"a": 1}'),
    ('{"path": "C:\\\\Users\\\\a"}', '{"path": "C:\\\\Users\\\\a"}'),
    # a hash inside a real string is not a comment start
    ('"#"', '"#"'),
    # an unclosed block comment is left as literal text, not stripped
    ('/*', '/*'),
    ('a/* b', 'a/* b'),
    # a closed block comment must not poison a later, separate one: only
    # a real search miss may be remembered, not every comment attempt
    ('/* ok */ /* another */end', ' end'),
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


@pytest.mark.timeout(10)
def test_strip_comments_pathological_input_stays_bounded():
    # A payload only a linear scan finishes quickly: many escaped-quote
    # pairs with nothing to close the string, at a size a backtracking or
    # quadratic-retry scan could not clear in the bound below.
    payload = '{"a": "' + '\\"' * 50000
    start = time.monotonic()
    strip_comments(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0


@pytest.mark.timeout(10)
def test_strip_comments_unterminated_string_stays_bounded():
    # A long run of backslashes with no closing quote at all: the
    # historical pattern backtracked over every way to split the
    # ambiguous escape before giving up.
    payload = '"' + '\\' * 100000 + 'x'
    start = time.monotonic()
    strip_comments(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0


@pytest.mark.timeout(10)
def test_strip_comments_repeated_unclosed_block_comment_stays_bounded():
    # Many unclosed block-comment starts in a row: searching for a
    # closing */ from each one in turn, instead of once, cost quadratic
    # time in the number of starts.
    payload = 'a/*' * 70000
    start = time.monotonic()
    strip_comments(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
