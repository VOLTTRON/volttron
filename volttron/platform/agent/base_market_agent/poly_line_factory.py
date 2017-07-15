# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import numpy as np
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.poly_line import PolyLine

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
        # print ys
        # print minY, maxY

        # now find the cumulative x associated with each y in the array
        # starting with the highest y
        for y in ys:
            xt = None
            for line in lines:
                x = line.x(y, left=np.nan)
                # print x, y
                if x is not None:
                    xt = x if xt is None else xt + x
            composite.add(Point(xt, y))

        return composite

    @staticmethod
    def fromTupples(points):
        polyLine = PolyLine()
        for p in points:
            if p is not None and len(p) == 2:
                polyLine.add(Point(p[0], p[1]))
        return polyLine

