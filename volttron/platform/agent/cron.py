# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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

# pylint: disable=W0142,W0403
#}}}

'''cron-like schedule generator.'''


from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta
from heapq import merge
from itertools import chain, count, cycle
import re


__all__ = ['schedule']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


_range_re = re.compile(r'^(.{0}(?=\*)|\w*(?=-)|\w+(?!\*))'
                       r'(?:[*-]?((?<=\*).{0}|(?<=-)\w*|(?=/).{0}))?'
                       r'(?:/(\d+))?$', re.I)


def _split_range(string):
    '''Generator to split cron ranges into (start, end, skip) tuples.

    Takes a string of the folloing forms:

        [start][-[end]][/skip][,...]
        *[/skip]

    where * is equivalent to first-last and yeilds the 3-tuple with each
    iteration.
    '''
    for rng in string.split(','):
        if not rng:
            continue
        match = _range_re.match(rng)
        if match:
            yield match.groups()
        else:
            raise ValueError('bad range expresion: {}'.format(rng))


def _convert_item(item, default, translate=None):
    '''Convert item to an integer.

    Return None if item is None or default if item is the empty string.
    Otherwise, try to convert item using the int() builtin.  If int()
    fails, use the translate function, if given, or re-raise ValueError.
    '''
    if item is None:
        return
    if not item:
        return default
    try:
        return int(item)
    except ValueError:
        if not translate:
            raise
        return translate(item)


def _convert_range(rng, minimum, maximum, translate=None):
    '''Convert range 3-tuples to integer lists.

    If rng evaluates to False, just return int.  Otherwise, convert the
    range values to integers using the minimum as the default for the
    start value, maximum as the default for the end value and translate
    to convert string values.
    '''
    if not rng:
        return rng
    first, last, skip = rng
    first = _convert_item(first, minimum, lambda x: translate(x, 0))
    last = _convert_item(last, maximum, lambda x: translate(x, 1))
    if last is None:
        return [first]
    skip = _convert_item(skip, 1)
    if skip is None:
        return range(first, last + 1)
    return range(first, last + 1, skip)


def _coallesce_ranges(fieldname, ranges, minimum, maximum, translate=None):
    '''Combine multiple ranges into a single sorted list of values.'''
    if not ranges:
        return
    result = set()
    for rng in ranges:
        rng = _convert_range(rng, minimum, maximum, translate)
        if not rng:
            continue
        if rng[0] < minimum:
            raise ValueError(
                    '{} value of {} is below the minimum of {}'.format(
                    fieldname, rng[0], minimum))
        if rng[-1] > maximum:
            raise ValueError(
                    '{} value of {} is above the maximum of {}'.format(
                    fieldname, rng[-1], maximum))
        result |= set(rng)
    return tuple(sorted(result)) or None


def _translate_month(month, pos):
    '''Translate month names to integers.'''
    try:
        return ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug',
                'sep', 'oct', 'nov', 'dec'].index(month[:3].lower()) + 1
    except ValueError:
        raise ValueError('invalid month name: {}'.format(month))


def _translate_weekday(weekday, pos):
    '''Translate weekday names to integers.'''
    try:
        index = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].index(
                 weekday[:3].lower()) + 1
    except ValueError:
        raise ValueError('invalid day name: {}'.format(weekday))
    # If Sunday is is in the start position, return it as 0
    if index == 7 and not pos:
        index = 0
    return index


def parse_cron_string(cron_string):
    fields = cron_string.split()
    if len(fields) > 5:
        raise ValueError('too many fields in cron string')
    elif len(fields) < 5:
        raise ValueError('too few fields in cron string')
    minute, hour, day, month, weekday = [
            None if field == '*' else _split_range(field) for field in fields]
    return (_coallesce_ranges('minute', minute, 0, 59),
            _coallesce_ranges('hour', hour, 0, 23),
            _coallesce_ranges('day', day, 1, 31),
            _coallesce_ranges('month', month, 1, 12, _translate_month),
            _coallesce_ranges('weekday', weekday, 0, 7, _translate_weekday))


def schedule(cron_string, start=None, stop=None):
    '''Return a schedule generator from a cron-style string.

    cron_string is a cron-style time expression consisting of five
    whitespace-separated fields explained in further detail below.
    start and stop are used to bound the schedule and can be None,
    datetime.datetime objects or numeric values, such as is returned by
    time.time().  stop may also be supplied as a datetime.timedelta
    object, in which case the end time is start + stop.  If start is
    None, the current time is used.  If stop is None, schedule will
    generate values infinitely.  Each iteration yields a
    datetime.datetime object.

    The following description of the cron fields is taken from the
    crontab(5) man page (with slight modifications).

    The time and date fields are:

           field          allowed values
           -----          --------------
           minute         0-59
           hour           0-23
           day of month   1-31
           month          1-12 (or names, see below)
           day of week    0-7 (0 or 7 is Sunday, or use names)

    A field may contain an asterisk (*), which always stands for
    "first-last".

    Ranges of numbers are allowed.  Ranges are two numbers separated
    with a hyphen.  The specified range is inclusive.  For example, 8-11
    for an 'hours' entry specifies execution at hours 8, 9, 10, and 11.
    If the range start or end value is left off, the first or last value
    will be used.  For example, -8 for an 'hours' entry is equivalent to
    0-8, 20- for a 'days of month' entry is equivalent to 20-31, and -
    for a 'months' entry is equivalent to 1-12.

    Lists are allowed.  A list is a set of numbers (or ranges) separated
    by commas.  Examples: "1,2,5,9", "0-4,8-12".

    Step values can be used in conjunction with ranges.  Following a
    range with "/<number>" specifies skips of the number's value through
    the range.  For example, "0-23/2" can be used in the 'hours' field
    to specify every other hour.  Step values are also permitted after
    an asterisk, "*/2" in the 'hours' field is equivalent to "0-23/2".

    Names can also be used for the 'month' and 'day of week' fields.
    Use at least the first three letters of the particular day or month
    (case does not matter).

    Note: The day can be specified in the following two fields: 'day of
    month', and 'day of week'.  If both fields are restricted (i.e., do
    not contain the "*" character), then both are used to compute
    date/time values.  For example, "30 4 1,15 * 5" is interpreted as
    "4:30 am on the 1st and 15th of each month, plus every Friday."
    '''

    minutes, hours, days, months, weekdays = parse_cron_string(cron_string)
    # Convert 0-Sunday to 7-Sunday to match datetime.isoweekday()
    if weekdays and weekdays[0] == 0:
        weekdays = weekdays[1:] + (() if weekdays[-1] == 7 else (7,))
    # Check that there are some valid month/day combinations.
    if months and days and not weekdays:
        unsafe = set([(2, 30), (2, 31), (4, 31), (6, 31), (9, 31), (11, 31)])
        combos = set([(m, d) for m in months for d in days])
        if not combos - unsafe:
            raise ValueError('given months and days produce only '
                             'impossible combinations')

    # Default start date/time to current time
    if start is None:
        start = datetime.now()
    elif isinstance(start, (int, long, float)):
        start = datetime.fromtimestamp(start)
    if isinstance(stop, (int, long, float)):
        stop = datetime.fromtimestamp(stop)
    elif isinstance(stop, timedelta):
        stop = start + stop

    # Default fields to full range of values
    months = months or range(1, 13)
    hours = hours or range(0, 24)
    minutes = minutes or range(0, 60)

    def _weekdays(year, month, day=1):
        '''Iterate over all the days in weekdays for the given year and
        month starting with day.
        '''
        dt = date(year, month, day)
        weekday = dt.isoweekday()
        i = bisect_left(weekdays, weekday)
        dt += timedelta(weekdays[i] - weekday if i < len(weekdays)
                        else weekdays[0] + 7 - weekday)
        day, weekday = dt.day, dt.isoweekday()
        for next in chain(weekdays[i + 1:], cycle(weekdays)):
            if day > 31:
                break
            yield day
            day, weekday = day + (next - weekday if next > weekday
                                  else next + 7 - weekday), next

    # Handle special case when the start month and day are in the set
    if start.month in months:
        if (not (days or weekdays) or days and start.day in days or
                weekdays and start.isoweekday() in weekdays):
            if start.hour in hours:
                for minute in minutes[bisect_right(minutes, start.minute):]:
                    yield datetime(start.year, start.month, start.day, start.hour, minute)
            for hour in hours[bisect_right(hours, start.hour):]:
                for minute in minutes:
                    yield datetime(start.year, start.month, start.day, hour, minute)
        first_month = [(start.year, start.month, start.day + 1)]
    else:
        first_month = []

    # Iterate over all values until stop is hit
    for year, month, first_day in chain(first_month,
            ((start.year, m, 1) for m in months[bisect_right(months, start.month):]),
            ((y, m, 1) for y in count(start.year + 1) for m in months)):
        try:
            if days:
                _days = days[bisect_left(days, first_day):]
                if weekdays:
                    _days = merge(_days, _weekdays(year, month, first_day))
            elif weekdays:
                _days = _weekdays(year, month)
            else:
                _days = range(1, 32)
            for day in _days:
                for hour in hours:
                    for minute in minutes:
                        dt = datetime(year, month, day, hour, minute)
                        if stop and dt > stop:
                            return
                        yield dt
        except ValueError:
            pass

