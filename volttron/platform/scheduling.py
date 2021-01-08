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

"""Schedule generators."""


from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta
from heapq import merge
from itertools import chain, count, cycle
import re


__all__ = ['cron', 'periodic']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'Apache 2.0'


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
        return list(range(first, last + 1))
    return list(range(first, last + 1, skip))


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


def _start_stop(start, stop):
    # Default start date/time to current time
    if start is None:
        start = datetime.now()
    elif isinstance(start, (int, float)):
        start = datetime.fromtimestamp(start)
    elif isinstance(start, timedelta):
        start = datetime.now() + start
    if isinstance(stop, (int, float)):
        stop = datetime.fromtimestamp(stop)
    elif isinstance(stop, timedelta):
        stop = start + stop
    return start, stop


def cron(cron_string, start=None, stop=None, second=0):
    '''Return a schedule generator from a cron-style string.

    cron_string is a cron-style time expression consisting of five
    whitespace-separated fields explained in further detail below.
    start and stop are used to bound the schedule and can be None,
    datetime.datetime or datetime.timedelta objects or numeric values,
    such as is returned by time.time(). If start is None, the current
    time is used. If it is a timedelta, it will be added to the current
    time. If stop is None, cron will generate values infinitely. If it
    is a timedelta, the end time is the start time plus stop. Each
    iteration yields a datetime.datetime object. Since the smallest cron
    unit is a minute, second may be passed in to offset the time within
    the minute.

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

    if not 0 <= second < 60:
        raise ValueError('second is out of the range [0, 59]')
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

    start, stop = _start_stop(start, stop)

    # Default fields to full range of values
    months = months or list(range(1, 13))
    hours = hours or list(range(0, 24))
    minutes = minutes or list(range(0, 60))

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
                    yield datetime(start.year, start.month, start.day, start.hour, minute, second)
            for hour in hours[bisect_right(hours, start.hour):]:
                for minute in minutes:
                    yield datetime(start.year, start.month, start.day, hour, minute, second)
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
                _days = _weekdays(year, month, first_day)
            else:
                _days = list(range(first_day, 32))
            for day in _days:
                for hour in hours:
                    for minute in minutes:
                        dt = datetime(year, month, day, hour, minute, second)
                        if stop and dt > stop:
                            return
                        yield dt
        except ValueError:
            pass


def periodic(period, start=None, stop=None):
    """Generate periodic datetime objects.

    Yields datetime objects increasing by the given period, which
    can be of type int, long, float, or datetime.timedelta.
    start and stop are used to bound the schedule and can be None,
    datetime.datetime or datetime.timedelta objects or numeric values,
    such as is returned by time.time(). If start is None, the current
    time is used. If it is a timedelta, it will be added to the current
    time. If stop is None, cron will generate values infinitely. If it
    is a timedelta, the end time is the start time plus stop. Each
    iteration yields a datetime.datetime object.
    """
    if not isinstance(period, timedelta):
        period = timedelta(seconds=period)
    dt, stop = _start_stop(start, stop)
    while stop is None or dt < stop:
        yield dt
        dt += period
