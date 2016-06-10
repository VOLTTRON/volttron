# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those
# of the authors and should not be interpreted as representing official
# policies,
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

# }}}
"""
Utility methods for different aggregate historians
"""
from datetime import datetime, timedelta


def format_aggregation_time_period(time_period):
    period = int(time_period[:-1])
    unit = time_period[-1:]
    if unit == 'm':
        if period >= 60 and period % 60 == 0:
            period /= 60
            unit = 'h'
    if unit == 'h':
        if period >= 24 and period % 24 == 0:
            period /= 24
            unit = 'd'
    if unit == 'd':
        if period >= 7 and period % 7 == 0:
            period /= 7
            unit = 'w'
    # elif unit == 'w':
    #     start_time = end_time - timedelta(weeks=period_int)
    # elif unit == 'M':
    #     start_time = end_time - timedelta(days=30)
    return time_period


def compute_aggregation_frequency_seconds(period, use_calendar_periods):
    """
    Return aggregate collection frequency in seconds. This can be used
    to call the aggregate collection method periodically using
    self.core.periodic()
    @param period: period string from AggregateHistorian config
    @param calendar_periods: boolean to say if aggregate period should be
    based on calendar periods. For example: Week = Sunday to Saturday,
    Hourly average would be 1AM= 2AM, 2AM-3AM etc
    @return: collection frequency in seconds
    """
    period_int = int(period[:-1])
    unit = period[-1:]
    if unit == 'm':
        return period_int * 60
    elif unit == 'h':
        return period_int * 60 * 60
    elif unit == 'd':
        return period_int * 24 * 60 * 60
    elif unit == 'w':
        return period_int * 7 * 24 * 60 * 60
    elif unit == 'M':
        if use_calendar_periods:
            # collect more frequently than needed so that
            # we don't miss collecting February in case we
            # start collecting on say Jan 31
            return period_int * 15 * 24 * 60 * 60
        else:
            return period_int * 30 * 24 * 60 * 60


def compute_aggregation_timeslice(period, use_calender_time_periods):
    current = datetime.utcnow()
    period_int = int(period[:-1])
    unit = period[-1:]
    end_time = current
    if unit == 'm':
        start_time = end_time - timedelta(minutes=period_int)
    elif unit == 'h':
        start_time = end_time - timedelta(hours=period_int)
    elif unit == 'd':
        start_time = end_time - timedelta(days=period_int)
    elif unit == 'w':
        start_time = end_time - timedelta(weeks=period_int)
    elif unit == 'M':
        start_time = end_time - timedelta(days=30)
    else:
        raise ValueError("Invalid unit {} provided for aggregation_period. "
                         "Unit should be m/h/d/w/M".format(unit))

    if use_calender_time_periods:
        if unit == 'h':
            start_time = start_time.replace(minute=0,
                                            second=0,
                                            microsecond=0)
            end_time = end_time.replace(minute=0,
                                        second=0,
                                        microsecond=0)
        elif unit == 'd' or unit == 'w':
            start_time = start_time.replace(hour=0,
                                            minute=0,
                                            second=0,
                                            microsecond=0)
            end_time = end_time.replace(hour=0,
                                        minute=0,
                                        second=0,
                                        microsecond=0)
        elif unit == 'M':
            end_time = current.replace(day=1,
                                       hour=0,
                                       minute=0,
                                       second=0,
                                       microsecond=0)
            # get last day of previous month
            start_time = end_time - timedelta(days=1)
            # move to first day of previous month
            start_time = start_time.replace(day=1,
                                            hour=0,
                                            minute=0,
                                            second=0,
                                            microsecond=0)

    return end_time, start_time
