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

from volttron.platform import config

# ConfigFileAction.itersettings backs config.ArgumentParser, which
# control_parser.py builds vctl's option parser from. These fix the exact
# set of "[section]" header lines that pattern must keep accepting and
# rejecting unchanged.


def _action():
    return config.ConfigFileAction(option_strings=['--config'], dest='config')


VALID_CASES = [
    (['[section]\n', 'key = value\n'], 'section'),
    (['[sec\\]tion]\n', 'key = value\n'], 'sec]tion'),
    (['  [ spaced section ]  # trailing comment\n', 'key = value\n'],
     'spaced section'),
    (['[a\\\\b]\n', 'key = value\n'], 'a\\b'),
    (['[]\n', 'key = value\n'], ''),
]


@pytest.mark.parametrize('lines, expected_section', VALID_CASES)
def test_itersettings_valid_section_unchanged(lines, expected_section):
    settings = list(_action().itersettings(None, lines))
    assert settings[0][0] == expected_section


# A trailing, unescaped-by-parity backslash right before the closing
# bracket, with no bracket later in the line: the historical pattern still
# closed the header there instead of leaving it unterminated. These pin
# that so a performance fix cannot silently change what a header like this
# means: a later reader kept filing keys under the wrong section for it.
ESCAPED_FINAL_DELIMITER_CASES = [
    ('[x\\]', ('x\\', '')),
    ('[x\\] rest', ('x\\', ' rest')),
    ('[\\]', ('\\', '')),
]


@pytest.mark.parametrize('line, expected', ESCAPED_FINAL_DELIMITER_CASES)
def test_match_section_header_escaped_final_delimiter_keeps_old_meaning(line, expected):
    assert config.match_section_header(line) == expected


# Embedded-newline boundary cases the historical single-call match still
# had to settle, now pinned as literals.
EMBEDDED_NEWLINE_CASES = [
    ('[\\ ]', ('\\ ', '')),
    ('[a]\nb', None),
    ('[a]b\n', ('a', 'b')),
    # a true wall (no preceding backslash) must stop the scan outright,
    # not keep looking past it for a later bracket.
    ('[]\n]', None),
]


@pytest.mark.parametrize('line, expected', EMBEDDED_NEWLINE_CASES)
def test_match_section_header_embedded_newline_boundary(line, expected):
    assert config.match_section_header(line) == expected


@pytest.mark.timeout(10)
def test_match_section_header_pathological_backslash_run_stays_bounded():
    # A payload only a linear scan finishes quickly: a long backslash run
    # with no closing bracket at all, so a backtracking scan would have to
    # explore every way to split the ambiguous escape before giving up.
    payload = '[' + '\\' * 100000
    start = time.monotonic()
    config.match_section_header(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0


@pytest.mark.timeout(10)
def test_match_section_header_pathological_whitespace_run_stays_bounded():
    # The leading \s*, the lazy name group, and the trailing \s* all being
    # able to absorb the same run of spaces made an unterminated header
    # cubic in the run's length; a payload only a linear scan finishes
    # quickly proves that overlap is gone.
    payload = '[' + ' ' * 100000 + 'x'
    start = time.monotonic()
    config.match_section_header(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0


@pytest.mark.timeout(10)
def test_match_section_header_reconsider_heavy_stays_bounded():
    # Many escaped brackets, each pushed onto the recovery list, followed
    # by an embedded newline: checking that boundary once per line, not
    # once per popped candidate, is what keeps this linear.
    payload = '[' + '\\]x' * 350000 + '\nx\ny'
    start = time.monotonic()
    config.match_section_header(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
