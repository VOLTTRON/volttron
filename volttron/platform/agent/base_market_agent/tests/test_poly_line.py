# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

import pytest
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.poly_line import PolyLine

@pytest.mark.market
def test_poly_line_min():
    min = PolyLine.min(1,2)
    assert min == 1

@pytest.mark.market
def test_poly_line_min_first_none():
    min = PolyLine.min(None,2)
    assert min == 2

@pytest.mark.market
def test_poly_line_min_second_none():
    min = PolyLine.min(1,None)
    assert min == 1

@pytest.mark.market
def test_poly_line_max():
    max = PolyLine.max(1,2)
    assert max == 2

@pytest.mark.market
def test_poly_line_max_first_none():
    max = PolyLine.max(None,2)
    assert max == 2

@pytest.mark.market
def test_poly_line_max_second_none():
    max = PolyLine.max(1,None)
    assert max == 1

@pytest.mark.market
def test_poly_line_sum():
    sum = PolyLine.sum(1,2)
    assert sum == 3

@pytest.mark.market
def test_poly_line_sum_first_none():
    sum = PolyLine.sum(None,2)
    assert sum == 2

@pytest.mark.market
def test_poly_line_sum_second_none():
    sum = PolyLine.sum(1,None)
    assert sum == 1

@pytest.mark.market
def test_poly_line_init_points_none():
    line = PolyLine()
    assert len(line.points) == 0

@pytest.mark.market
def test_poly_line_add_one_point():
    line = PolyLine()
    line.add(Point(4,8))
    assert len(line.points) == 1

@pytest.mark.market
def test_poly_line_add_two_points():
    line = PolyLine()
    line.add(Point(4,8))
    line.add(Point(2,4))
    assert len(line.points) == 2

@pytest.mark.market
def test_poly_line_add_points_is_sorted():
    line = PolyLine()
    line.add(Point(4,8))
    line.add(Point(2,4))
    assert line.points[0].x == 2

@pytest.mark.market
def test_poly_line_intersection_not_none():
    demand = create_demand_curve()
    supply = create_supply_curve()
    intersection = PolyLine.intersection(demand, supply)
    assert intersection is not None

@pytest.mark.market
def test_poly_line_intersection_yeilds_two():
    demand = create_demand_curve()
    supply = create_supply_curve()
    intersection = PolyLine.intersection(demand, supply)
    assert len(intersection) == 2

@pytest.mark.market
def test_poly_line_no_intersection():
    demand1 = create_demand_curve()
    demand2 = create_demand_curve()
    intersection = PolyLine.intersection(demand1, demand2)
    assert len(intersection) == 2

def create_supply_curve():
    supply_curve = PolyLine()
    price = 0
    quantity = 0
    supply_curve.add(Point(price,quantity))
    price = 1000
    quantity = 1000
    supply_curve.add(Point(price,quantity))
    return supply_curve

def create_demand_curve():
    demand_curve = PolyLine()
    price = 0
    quantity = 1000
    demand_curve.add(Point(price,quantity))
    price = 1000
    quantity = 0
    demand_curve.add(Point(price,quantity))
    return demand_curve
