# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
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


class PolyLineFactory(object):
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

