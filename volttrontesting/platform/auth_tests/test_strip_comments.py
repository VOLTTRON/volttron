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


def test_strip_comments_pathological_input_stays_bounded():
    # The old (?:\\?.)*? let a lone backslash match via the optional escape
    # or via the bare "." alternative, so an unterminated quoted string with
    # many backslashes backtracked over every split of that ambiguity.
    payload = '"' + '\\' * 36 + 'x'
    start = time.time()
    strip_comments(payload)
    elapsed = time.time() - start
    assert elapsed < 2.0
