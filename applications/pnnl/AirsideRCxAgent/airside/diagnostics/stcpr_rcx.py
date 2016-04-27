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
import logging
import math
from copy import deepcopy
from .common import check_date, validation_builder, check_run_status, setpoint_control_check
from volttron.platform.agent.math_utils import mean

DUCT_STC_RCX = 'Duct Static Pressure Control Loop Dx'
DUCT_STC_RCX1 = 'Low Duct Static Pressure Dx'
DUCT_STC_RCX2 = 'High Duct Static Pressure Dx'
DX = '/diagnostic message'
CORRECT_STC_PR = 'suggested duct static pressure set point'
STCPR_VALIDATE = 'Duct Static Pressure ACCx'
VALIDATE_FILE_TOKEN = 'stcpr-rcx'
DX = '/diagnostic message'
ST = 'state'
DATA = '/data/'
STCPR_NAME = 'duct static pressure'


def create_table_key(table_name, timestamp):
    return '&'.join([table_name, timestamp.strftime('%m-%d-%y %H:%M')])


class DuctStaticRcx(object):
    """Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    duct static pressure problems.
    """
    def __init__(self, no_req_data, auto_correct_flag, stpt_allowable_dev,
                 max_stcpr_stpt, stcpr_retuning, zone_high_dmpr_threshold,
                 zone_low_dmpr_threshold, hdzn_dmpr_thr, min_stcpr_stpt,
                 analysis, stcpr_stpt_cname):
        # Initialize data arrays
        self.table_key = None
        self.file_key = None
        self.zn_dmpr_arr = []
        self.stcpr_stpt_arr = []
        self.stcpr_arr = []
        self.timestamp_arr = []
        self.data = {}
        self.dx_table = {}

        # Initialize configurable thresholds
        self.analysis = analysis + '-' + VALIDATE_FILE_TOKEN
        self.file_name_id = analysis + '-' + VALIDATE_FILE_TOKEN
        self.stcpr_stpt_cname = stcpr_stpt_cname
        self.no_req_data = no_req_data
        self.stpt_allowable_dev = float(stpt_allowable_dev)
        self.max_stcpr_stpt = float(max_stcpr_stpt)
        self.stcpr_retuning = float(stcpr_retuning)
        self.zone_high_dmpr_threshold = float(zone_high_dmpr_threshold)
        self.zone_low_dmpr_threshold = float(zone_low_dmpr_threshold)
        self.sp_allowable_dev = float(stpt_allowable_dev)
        self.auto_correct_flag = auto_correct_flag
        self.min_stcpr_stpt = float(min_stcpr_stpt)
        self.hdzn_dmpr_thr = float(hdzn_dmpr_thr)
        self.token_offset = 0.0

        self.low_msg = ('The supply fan is running at nearly 100% of full '
                        'speed, data corresponding to {} will not be used.')
        self.high_msg = ('The supply fan is running at the minimum speed, '
                         'data corresponding to {} will not be used.')

    def reinitialize(self):
        """Reinitialize data arrays"""
        self.table_key = None
        self.file_key = None
        self.zn_dmpr_arr = []
        self.stcpr_stpt_arr = []
        self.stcpr_arr = []
        self.timestamp_arr = []
        self.data = {}
        self.dx_table = {}

    def duct_static(self, current_time, stcpr_stpt_data, stcpr_data,
                    zn_dmpr_data, low_dx_cond, high_dx_cond, dx_result,
                    validate):
        """Check duct static pressure RCx pre-requisites and assemble the

        duct static pressure analysis data set.
        """
        if check_date(current_time, self.timestamp_arr):
            self.reinitialize()
            return dx_result

        if low_dx_cond:
            dx_result.log(self.low_msg.format(current_time), logging.DEBUG)
            return dx_result
        if high_dx_cond:
            dx_result.log(self.high_msg.format(current_time), logging.DEBUG)
            return dx_result

        file_key = create_table_key(VALIDATE_FILE_TOKEN, current_time)
        data = validation_builder(validate, STCPR_VALIDATE, DATA)
        run_status = check_run_status(self.timestamp_arr, current_time, self.no_req_data)

        if run_status is None:
            dx_result.log('Current analysis data set has insufficient data '
                          'to produce a valid diagnostic result.')
            self.reinitialize()
            return dx_result

        if run_status:
            self.table_key = create_table_key(self.analysis, self.timestamp_arr[-1])
            avg_stcpr_stpt, dx_table = setpoint_control_check(self.stcpr_stpt_arr,
                                                              self.stcpr_arr,
                                                              self.stpt_allowable_dev,
                                                              DUCT_STC_RCX, DX,
                                                              STCPR_NAME, self.token_offset)

            self.dx_table.update(dx_table)
            dx_result = self.low_stcpr_dx(dx_result, avg_stcpr_stpt)
            dx_result = self.high_stcpr_dx(dx_result, avg_stcpr_stpt)
            dx_result.insert_table_row(self.table_key, self.dx_table)
            self.data.update({STCPR_VALIDATE + DATA + ST: 1})
            dx_result.insert_table_row(self.file_key, self.data)
            self.reinitialize()

        self.stcpr_stpt_arr.append(mean(stcpr_data))
        self.stcpr_arr.append(mean(stcpr_stpt_data))
        self.zn_dmpr_arr.append(mean(zn_dmpr_data))
        self.timestamp_arr.append(current_time)

        if self.data:
            self.data.update({STCPR_VALIDATE + DATA + ST: 0})
            dx_result.insert_table_row(self.file_key, self.data)
        self.data = data
        self.file_key = file_key
        return dx_result

    def low_stcpr_dx(self, dx_result, avg_stcpr_stpt):
        """Diagnostic to identify and correct low duct static pressure

        (correction by modifying duct static pressure set point).
        """
        zn_dmpr = deepcopy(self.zn_dmpr_arr)
        zn_dmpr.sort(reverse=False)
        zone_dmpr_lowtemp = zn_dmpr[:int(math.ceil(len(self.zn_dmpr_arr)*0.5)) if len(self.zn_dmpr_arr) != 1 else 1]
        zn_dmpr_low_avg = mean(zone_dmpr_lowtemp)

        zone_dmpr_hightemp = zn_dmpr[int(math.ceil(len(self.zn_dmpr_arr)*0.5)) - 1 if len(self.zn_dmpr_arr) != 1 else 0:]
        zn_dmpr_high_avg = mean(zone_dmpr_hightemp)
        if zn_dmpr_high_avg > self.zone_high_dmpr_threshold and zn_dmpr_low_avg > self.zone_low_dmpr_threshold:
            if avg_stcpr_stpt is None:
                # Create diagnostic message for fault
                # when duct static pressure set point
                # is not available.
                msg = ('The duct static pressure set point has been '
                       'detected to be too low but but supply-air'
                       'temperature set point data is not available.')
                dx_msg = 14.1
            elif self.auto_correct_flag:
                auto_correct_stcpr_stpt = avg_stcpr_stpt + self.stcpr_retuning
                if auto_correct_stcpr_stpt <= self.max_stcpr_stpt:
                    dx_result.command(self.stcpr_stpt_cname, auto_correct_stcpr_stpt)
                    new_stcpr_stpt = '%s' % float('%.2g' % auto_correct_stcpr_stpt)
                    new_stcpr_stpt = new_stcpr_stpt + ' in. w.g.'
                    msg = ('The duct static pressure was detected to be '
                           'too low. The duct static pressure has been '
                           'increased to: {}'
                           .format(new_stcpr_stpt))
                    dx_msg = 11.1
                else:
                    dx_result.command(self.stcpr_stpt_cname, self.max_stcpr_stpt)
                    new_stcpr_stpt = '%s' % float('%.2g' % self.max_stcpr_stpt)
                    new_stcpr_stpt = new_stcpr_stpt + ' in. w.g.'
                    msg = ('The duct static pressure set point is at the '
                           'maximum value configured by the building '
                           'operator: {})'.format(new_stcpr_stpt))
                    dx_msg = 12.1
            else:
                msg = ('The duct static pressure set point was detected '
                       'to be too low but auto-correction is not enabled.')
                dx_msg = 13.1
        else:
            msg = ('No re-tuning opportunity was detected during the low duct '
                   'static pressure diagnostic.')
            dx_msg = 10.0

        self.dx_table.update({DUCT_STC_RCX1 + DX: dx_msg})
        dx_result.log(msg, logging.INFO)
        return dx_result

    def high_stcpr_dx(self, dx_result, avg_stcpr_stpt):
        """Diagnostic to identify and correct high duct static pressure

        (correction by modifying duct static pressure set point)
        """
        zn_dmpr = deepcopy(self.zn_dmpr_arr)
        zn_dmpr.sort(reverse=True)
        zn_dmpr = zn_dmpr[:int(math.ceil(len(self.zn_dmpr_arr)*0.5))if len(self.zn_dmpr_arr) != 1 else 1]
        avg_zone_damper = mean(zn_dmpr)

        if avg_zone_damper <= self.hdzn_dmpr_thr:
            if avg_stcpr_stpt is None:
                # Create diagnostic message for fault
                # when duct static pressure set point
                # is not available.
                msg = ('The duct static pressure set point has been '
                       'detected to be too high but but duct static '
                       'pressure set point data is not available.'
                       'temperature set point data is not available.')
                dx_msg = 24.1
            elif self.auto_correct_flag:
                auto_correct_stcpr_stpt = avg_stcpr_stpt - self.stcpr_retuning
                if auto_correct_stcpr_stpt >= self.min_stcpr_stpt:
                    dx_result.command(self.stcpr_stpt_cname, auto_correct_stcpr_stpt)
                    new_stcpr_stpt = '%s' % float('%.2g' % auto_correct_stcpr_stpt)
                    new_stcpr_stpt = new_stcpr_stpt + ' in. w.g.'
                    msg = ('The duct static pressure was detected to be '
                           'too high. The duct static pressure set point '
                           'has been reduced to: {}'
                           .format(new_stcpr_stpt))
                    dx_msg = 21.1
                else:
                    dx_result.command(self.stcpr_stpt_cname, self.min_stcpr_stpt)
                    new_stcpr_stpt = '%s' % float('%.2g' % self.min_stcpr_stpt)
                    new_stcpr_stpt = new_stcpr_stpt + ' in. w.g.'
                    msg = ('The duct static pressure set point is at the '
                           'minimum value configured by the building '
                           'operator: {})'.format(new_stcpr_stpt))
                    dx_msg = 22.1
            else:
                msg = ('Duct static pressure set point was detected to be '
                       'too high but auto-correction is not enabled.')
                dx_msg = 23.1
        else:
            msg = ('No re-tuning opportunity was detected during the high duct '
                   'static pressure diagnostic.')
            dx_msg = 20.0

        self.dx_table.update({DUCT_STC_RCX2 + DX: dx_msg})
        dx_result.log(msg, logging.INFO)
        return dx_result
