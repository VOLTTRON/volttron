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


def test_itersettings_pathological_input_stays_bounded():
    # [^\]] overlapped \\., so a backslash run before an unterminated
    # section header backtracked over every split between the escape and
    # fallback branches.
    payload = '[' + '\\' * 36
    start = time.time()
    list(_action().itersettings(None, [payload]))
    elapsed = time.time() - start
    assert elapsed < 2.0
