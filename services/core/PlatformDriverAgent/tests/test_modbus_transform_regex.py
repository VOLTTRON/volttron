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

VALID_CASES = [
    ('scale(0.001)', 'scale', '0.001'),
    ('scale_int(1.0)', 'scale_int', '1.0'),
    ('mod10k(True)', 'mod10k', 'True'),
    ('scale_reg(I_AC_CurrentSF)', 'scale_reg', 'I_AC_CurrentSF'),
    ('scale_reg_pow_10(I_AC_CurrentSF)', 'scale_reg_pow_10', 'I_AC_CurrentSF'),
]


@pytest.mark.parametrize('transform, func_name, expected_arg', VALID_CASES)
def test_transform_regex_valid_input_unchanged(transform, func_name, expected_arg):
    reg = CSVRegister(None, {'transform': transform})
    assert reg._transform is not None


# a-zA-z (a typo for a-zA-Z) also matched the ASCII range between 'Z' and
# 'a': [ \ ] ^ ` in addition to the underscore real register names use.
STRAY_CHARS = ['[', '\\', ']', '^', '`']


@pytest.mark.parametrize('stray', STRAY_CHARS)
def test_transform_regex_rejects_stray_range_characters(stray):
    reg = CSVRegister(None, {'transform': 'scale(1{}2)'.format(stray)})
    with pytest.raises(MapException):
        reg._transform


def test_transform_regex_still_accepts_underscore_register_names():
    # Underscore is a real, shipped character (scale_reg_map.csv), not part
    # of the range typo being fixed; the fix must not reject it.
    reg = CSVRegister(None, {'transform': 'scale_reg(I_AC_CurrentSF)'})
    assert reg._transform is not None
