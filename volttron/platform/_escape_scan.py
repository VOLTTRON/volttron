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

"""Escape-aware delimiter scanning shared by config.py and resmon.py.

Both files scan forward for a closing delimiter, escaping backslash pairs
as they go; when that walk lands on a delimiter the caller cannot use, it
un-escapes the nearest earlier delimiter that still has an unused
backslash of its own, the same recovery a backtracking engine reaches by
trying every split of the ambiguous escape once a later position fails,
without repeating the walk itself.
"""


def backslash_run_before(text, pos):
    """Count the consecutive backslashes immediately before pos."""
    count = 0
    i = pos - 1
    while i >= 0 and text[i] == '\\':
        count += 1
        i -= 1
    return count


def find_close(line, start, delim, tail_ok):
    """Return the index of the delim character that closes a value
    starting at start, or None if no closing position works. tail_ok(line,
    pos) says whether closing at pos (just past the candidate delimiter)
    leaves a usable rest of line.
    """
    i = start
    found = None
    reconsider = []
    while True:
        q = line.find(delim, i)
        if q == -1:
            break
        backslashes = backslash_run_before(line, q)
        if backslashes % 2 == 0 and tail_ok(line, q + 1):
            found = q
            break
        if backslashes == 0:
            while reconsider:
                candidate = reconsider.pop()
                if tail_ok(line, candidate + 1):
                    found = candidate
                    break
            break
        reconsider.append(q)
        i = q + 1
    if found is None:
        while reconsider:
            candidate = reconsider.pop()
            if tail_ok(line, candidate + 1):
                found = candidate
                break
    return found
