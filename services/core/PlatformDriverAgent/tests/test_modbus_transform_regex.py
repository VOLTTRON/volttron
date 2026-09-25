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

import pytest

from platform_driver.interfaces.modbus_tk.maps import CSVRegister, MapException

# CSVRegister._transform parses the "transform" column of a register map
# CSV (see maps/scale_reg_map.csv, which uses scale_reg(I_AC_CurrentSF)),
# so the character class must keep accepting real register-name arguments.

# Each case asserts on the parsed function and its full argument, by a
# behaviour that only the correct, untruncated argument produces: a mutant
# that captured a single character of the argument still returns a
# non-None transform for every one of these, so "is not None" alone would
# have missed it.
VALID_CASES = [
    # scale(0.5): multiplier truncated to "0" would make func(2) == 0.
    ('scale(0.5)', lambda transform: transform(2) == 1.0),
    # scale_int(2.5): multiplier truncated to "2" would make func(2) == 4.
    ('scale_int(2.5)', lambda transform: transform(2) == 5),
    # mod10k(True): reverse=True swaps high/low; a wrong argument gives
    # the un-reversed result (20003) instead.
    ('mod10k(True)', lambda transform: transform(131075) == 30002),
    # scale_reg keeps the full register name for the caller to resolve
    # later; a truncated argument would leave only its first character.
    ('scale_reg(I_AC_CurrentSF)',
     lambda transform: transform.register_args == ['I_AC_CurrentSF']),
    ('scale_reg_pow_10(I_AC_CurrentSF)',
     lambda transform: transform.register_args == ['I_AC_CurrentSF']),
]


@pytest.mark.parametrize('transform_str, check', VALID_CASES)
def test_transform_regex_valid_input_unchanged(transform_str, check):
    reg = CSVRegister(None, {'transform': transform_str})
    assert check(reg._transform)


# a-zA-z (a typo for a-zA-Z) also matched the ASCII range between 'Z' and
# 'a': [ \ ] ^ ` in addition to the underscore real register names use.
STRAY_CHARS = ['[', '\\', ']', '^', '`']


@pytest.mark.parametrize('stray', STRAY_CHARS)
def test_transform_regex_rejects_stray_range_characters(stray):
    reg = CSVRegister(None, {'transform': 'scale(1{}2)'.format(stray)})
    with pytest.raises(MapException):
        reg._transform


def test_transform_regex_rejects_bracket_in_register_name():
    # Before the range fix, a-zA-z also accepted '[', so scale_reg(a[b)
    # silently kept "a[b" as the register name instead of failing here.
    reg = CSVRegister(None, {'transform': 'scale_reg(a[b)'})
    with pytest.raises(MapException):
        reg._transform
