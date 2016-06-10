'''
Copyright (c) 2016, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.


This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or
service by trade name, trademark, manufacturer, or otherwise does
not necessarily constitute or imply its endorsement, recommendation,
r favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''
import datetime
from datetime import timedelta as td

"""Common functions used across multiple algorithms."""


def check_date(current_time, timestamp_array):
    """Check current timestamp with previous timestamp

    to verify that there are no large missing data gaps.
    """
    if not timestamp_array:
        return False
    if current_time.date() != timestamp_array[-1].date():
        if (timestamp_array[-1].date() + td(days=1) != current_time.date() or
                (timestamp_array[-1].hour != 23 and current_time.hour == 0)):
            return True
        return False


def validation_builder(validate, dx_name, data_tag):
    data = {}
    for key, value in validate.items():
        tag = dx_name + data_tag + key
        data.update({tag: value})
    return data


def check_run_status(timestamp_array, current_time, no_required_data, minimum_diagnostic_time=None):
    """The diagnostics run at a regular interval (some minimum elapsed amount of time) and have a
       minimum data count requirement (each time series of data must contain some minimum number
       of points).
       ARGS:
            timestamp_array(list(datetime)): ordered array of timestamps associated with building
                data.
            no_required_data(integer):  The minimum number of measurements for each time series used
                in the analysis.
    """
    def minimum_data():
        if len(timestamp_array) < no_required_data:
            return None
        return True
    if minimum_diagnostic_time is not None:
        sampling_interval = (timestamp_array[-1] - timestamp_array[0])/len(timestamp_array)
        required_time = (timestamp_array[-1] - timestamp_array[0]) + sampling_interval
        if required_time >= minimum_diagnostic_time:
             return minimum_data()
        return False
    if timestamp_array and timestamp_array[-1].hour != current_time.hour:
        return minimum_data()
    return False


def setpoint_control_check(setpoint_array, point_array, allowable_deviation,
                           dx_name, dx_tag, token, token_offset):
    """Verify that point is tracking well with set point.
        ARGS:
            setpoint_array (list(floats):
    """
    average_setpoint = None
    setpoint_array = [float(pt) for pt in setpoint_array if pt !=0]
    if setpoint_array:
        average_setpoint = sum(setpoint_array)/len(setpoint_array)
        zipper = (setpoint_array, point_array)
        stpt_tracking = [abs(x - y) for x, y in zip(*zipper)]
        stpt_tracking = (sum(stpt_tracking)/len(stpt_tracking))/average_setpoint*100

        if stpt_tracking > allowable_deviation:
            # color_code = 'red'
            msg = ('{pt} is deviating significantly '
                   'from the {pt} set point.'.format(pt=token))
            dx_msg = 1.1 + token_offset
            dx_table = {dx_name + dx_tag: dx_msg}
        else:
            # color_code = 'green'
            msg = 'No problem detected.'
            dx_msg = 0.0 + token_offset
            dx_table = {dx_name + dx_tag: dx_msg}
    else:
        # color_code = 'grey'
        msg = ('{} set point data is not available. '
               'The Set Point Control Loop Diagnostic'
               'requires set point '
               'data.'.format(token))
        dx_msg = 2.2 + token_offset
        dx_table = {dx_name + dx_tag: dx_msg}
    return average_setpoint, dx_table
