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

try:
    from volttron.platform.agent.base_market_agent.point import Point
except ImportError:
    pytest.skip("Market service requirements not installed.", allow_module_level=True)

@pytest.mark.market
def test_point_init():
    p = Point(4,8)
    assert p.x == 4.0
    assert p.y == 8.0

@pytest.mark.market
def test_point_x_none():
    with pytest.raises(ValueError):
        p = Point(None,8)

@pytest.mark.market
def test_point_x_negative():
    with pytest.raises(ValueError):
        p = Point(-8,8)

@pytest.mark.market
def test_point_y_none():
    with pytest.raises(ValueError):
        p = Point(4,None)

def test_point_y_negative():
    with pytest.raises(ValueError):
        p = Point(4,-4)

@pytest.mark.market
def test_point_tuppleize():
    p = Point(4,8)
    assert p == (4.0,8.0)
