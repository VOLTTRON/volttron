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

import numpy as np
import logging
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent import utils

_log = logging.getLogger(__name__)
utils.setup_logging()


def remove(duplicate):
    final_list = []
    for num in duplicate:
        if num not in final_list:
            final_list.append(num)
    return final_list


class PolyLineFactory:
    @staticmethod
    def combine(lines, increment):

        # we return a new PolyLine which is a composite (summed horizontally) of inputs
        composite = PolyLine()

        # find the range defined by the curves
        minY = None
        maxY = None
        for l in lines:
            minY = PolyLine.min(minY, l.min_y())
            maxY = PolyLine.max(maxY, l.max_y())

        # special case if the lines are already horizontal or None
        if minY == maxY:
            minSumX = None
            maxSumX = None
            for line in lines:
                minX = None
                maxX = None
                for point in line.points:
                    minX = PolyLine.min(minX, point.x)
                    maxX = PolyLine.max(maxX, point.x)
                minSumX = PolyLine.sum(minSumX, minX)
                maxSumX = PolyLine.sum(maxSumX, maxX)
            composite.add(Point(minSumX, minY))
            if minX != maxX:
                composite.add(Point(maxSumX, maxY))
            return composite

        # create an array of ys in equal increments, with highest first
        # this is assuming that price decreases with increase in demand (buyers!)
        # but seems to work with multiple suppliers?
        ys = sorted(np.linspace(minY, maxY, num=increment), reverse=True)

        # now find the cumulative x associated with each y in the array
        # starting with the highest y
        for y in ys:
            xt = None
            for line in lines:
                x = line.x(y)
                # print x, y
                if x is not None:
                    xt = x if xt is None else xt + x
            composite.add(Point(xt, y))

        return composite

    @staticmethod
    def combine_withoutincrement(lines):

        # we return a new PolyLine which is a composite (summed horizontally) of inputs
        composite = PolyLine()
        if len(lines) < 2:
            if isinstance(lines[0], list):
                for point in lines[0]:
                    composite.add(Point(point[0], point[1]))
                return composite
            return lines[0]
        # find the range defined by the curves
        ys=[]
        for l in lines:
            ys=ys+l.vectorize()[1]

        ys = remove(ys)

        ys.sort(reverse=True)
        for y in ys:
            xt = None
            for line in lines:
                x = line.x(y)
                if x is not None:
                    xt = x if xt is None else xt + x
            composite.add(Point(xt, y))
        return composite

    @staticmethod
    def fromTupples(points):
        poly_line = PolyLine()
        for p in points:
            if p is not None and len(p) == 2:
                poly_line.add(Point(p[0], p[1]))
        return poly_line
