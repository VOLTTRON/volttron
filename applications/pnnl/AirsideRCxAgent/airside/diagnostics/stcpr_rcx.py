'''
Copyright (c) 2014, Battelle Memorial Institute
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
import numpy as np
import datetime
import logging
import math
from copy import deepcopy

DUCT_STC_RCX = 'Duct Static Pressure Control Loop Dx'
DUCT_STC_RCX1 = 'Low Duct Static Pressure Dx'
DUCT_STC_RCX2 = 'High Duct Static Pressure Dx'
DX = '/diagnostic message'
CORRECT_STC_PR = 'suggested duct static pressure set point'
STCPR_VALIDATE = 'Duct Static Pressure ACCx'
DX = '/diagnostic message'
ST = 'state'
DATA = '/data/'


class DuctStaticRcx(object):
    '''Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    duct static pressure problems.
    '''
    def __init__(self, data_window, no_req_data, auto_correctflag,
                 sp_allowable_dev, max_stcpr_sp, stcpr_retuning,
                 zn_hdmpr_thr, zn_lowdmpr_thr, hdzn_dmpr_thr, min_stcpr_sp,
                 analysis, stcpr_sp_cname):
        # Initialize data arrays
        self.zn_dmpr_arr = []
        self.stcpr_sp_arr = []
        self.stcpr_arr = []
        self.ts = []

        # Initialize configurable thresholds
        self.analysis = analysis
        self.stcpr_sp_cname = stcpr_sp_cname
        self.data_window = float(data_window)
        self.no_req_data = no_req_data
        self.sp_allowable_dev = float(sp_allowable_dev)
        self.max_stcpr_sp = float(max_stcpr_sp)
        self.stcpr_retuning = float(stcpr_retuning)
        self.zn_hdmpr_thr = float(zn_hdmpr_thr)
        self.zn_lowdmpr_thr = float(zn_lowdmpr_thr)
        self.sp_allowable_dev = float(sp_allowable_dev)
        self.auto_correctflag = auto_correctflag
        self.min_stcpr_sp = float(min_stcpr_sp)
        self.hdzn_dmpr_thr = float(hdzn_dmpr_thr)

        self.low_msg = ('The supply fan is running at nearly 100% of full '
                        'speed, data corresponding to {} will not be used.')
        self.high_msg = ('The supply fan is running at the minimum speed, '
                         'data corresponding to {} will not be used.')

    def reinitialize(self):
        '''Reinitialize data arrays.'''
        self.zn_dmpr_arr = []
        self.stcpr_sp_arr = []
        self.stcpr_arr = []
        self.ts = []

    def duct_static(self, cur_time, stcpr_sp_data, stcpr_data, zn_dmpr_data,
                    stc_override_check, low_dx_cond, high_dx_cond, dx_result,
                    validate):
        '''Check duct static pressure RCx pre-requisites

        and assemble the duct static pressure analysis data set.
        '''
        if low_dx_cond:
            dx_result.log(self.low_msg.format(cur_time), logging.DEBUG)
            return dx_result
        if high_dx_cond:
            dx_result.log(self.high_msg.format(cur_time), logging.DEBUG)
            return dx_result

        self.stcpr_arr.append(np.mean(stcpr_data))
        self.zn_dmpr_arr.append(np.mean(zn_dmpr_data))
        self.ts.append(cur_time)

        self.stcpr_sp_arr.append(np.mean(stcpr_sp_data))
        e_time = self.ts[-1] - self.ts[0]
        e_time = e_time.total_seconds()/60
        e_time = e_time if e_time > 0.0 else 1.0

        data = {}
        for key, value in validate.items():
            tag = STCPR_VALIDATE + DATA + key
            data.update({tag: value})

        if e_time >= self.data_window and len(self.ts) >= self.no_req_data:
            avg_stcpr_sp = np.mean(self.stcpr_sp_arr)
            if avg_stcpr_sp > 0 and avg_stcpr_sp < 10.0:
                zipper = (self.stcpr_arr, self.stcpr_sp_arr)
                sp_tracking = [abs(x - y) for x, y in zip(*zipper)]
                sp_tracking = np.mean(sp_tracking)*100
                if sp_tracking > self.sp_allowable_dev:
                    msg = ('The duct static pressure is deviating '
                           'from its set point significantly.')
                    dx_msg = 1.1
                    dx_table = {
                        DUCT_STC_RCX + DX: dx_msg
                    }
                else:
                    msg = 'No problem detected.'
                    dx_msg = 0.0
                    dx_table = {
                        DUCT_STC_RCX + DX: dx_msg
                    }
                dx_result.insert_table_row(self.analysis, dx_table)
                dx_result.log(msg, logging.INFO)

            if e_time > 75:
                dx_result.insert_table_row(
                    self.analysis, {DUCT_STC_RCX1 + DX: 16.2})
                dx_result.insert_table_row(
                    self.analysis, {DUCT_STC_RCX2 + DX: 26.2})
                data.update({STCPR_VALIDATE + DATA + ST: 2})
                dx_result.insert_table_row(self.analysis, data)
                self.reinitialize()
                return dx_result
            dx_result = self.low_stcpr_dx(dx_result, stc_override_check)
            dx_result = self.high_stcpr_dx(dx_result, stc_override_check)
            data.update({STCPR_VALIDATE + DATA + ST: 1})
            dx_result.insert_table_row(self.analysis, data)
            self.reinitialize()
            return dx_result
        data.update({STCPR_VALIDATE + DATA + ST: 0})
        dx_result.insert_table_row(self.analysis, data)
        return dx_result

    def low_stcpr_dx(self, result, stc_override_check):
        '''Diagnostic to identify and correct low duct static pressure

        (correction by modifying duct static pressure set point).
        '''
        zn_dmpr = deepcopy(self.zn_dmpr_arr)
        zn_dmpr.sort(reverse=False)
        zone_damper_lowtemp = \
            zn_dmpr[:int(math.ceil(len(self.zn_dmpr_arr)*0.5))
                    if len(self.zn_dmpr_arr) != 1 else 1]
        zn_dmpr_lavg = np.mean(zone_damper_lowtemp)

        zone_damper_hightemp = (
            zn_dmpr[int(math.ceil(len(self.zn_dmpr_arr)*0.5)) - 1
                    if len(self.zn_dmpr_arr) != 1 else 0:])
        zn_dmpr_havg = np.mean(zone_damper_hightemp)
        avg_stcpr_sp = None
        if self.stcpr_sp_arr:
            avg_stcpr_sp = np.mean(self.stcpr_sp_arr)
        if zn_dmpr_havg > self.zn_hdmpr_thr and zn_dmpr_lavg > self.zn_lowdmpr_thr:
            if avg_stcpr_sp is not None and not stc_override_check:
                if self.auto_correctflag:
                    stcpr_sp = avg_stcpr_sp + self.stcpr_retuning
                    if stcpr_sp <= self.max_stcpr_sp:
                        result.command(self.stcpr_sp_cname, stcpr_sp)
                        stcpr_sp = '%s' % float('%.2g' % stcpr_sp)
                        stcpr_sp = stcpr_sp + ' in. w.g.'
                        msg = ('The duct static pressure was detected to be '
                               'too low. The duct static pressure has been '
                               'increased to: {val}'
                               .format(val=stcpr_sp))
                        dx_msg = 11.1
                    else:
                        result.command(self.stcpr_sp_cname,
                                       self.max_stcpr_sp)
                        stcpr_sp = '%s' % float('%.2g' % self.max_stcpr_sp)
                        stcpr_sp = stcpr_sp + ' in. w.g.'
                        msg = ('The duct static pressure set point is at the '
                               'maximum value configured by the building '
                               'operator: {val})'.format(val=stcpr_sp))
                        dx_msg = 12.1
                else:
                    msg = ('The duct static pressure set point was detected '
                           'to be too low but auto-correction is not enabled.')
                    dx_msg = 13.1
            elif not stc_override_check:
                msg = 'The duct static pressure was detected to be too low.'
                dx_msg = 14.1
            else:
                msg = ('The duct static pressure was detected to be too low '
                       'but an operator override was detected. '
                       'Auto-correction can not be performed when the static '
                       'pressure set point or fan command is in override.')
                dx_msg = 15.1
        else:
            msg = ('No re-tuning opportunity was detected during the low duct '
                   'static pressure diagnostic.')
            dx_msg = 10.0
        dx_table = {
            DUCT_STC_RCX1 + DX: dx_msg
        }
        result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def high_stcpr_dx(self, result, stc_override_check):
        '''Diagnostic to identify and correct high duct static pressure

        (correction by modifying duct static pressure set point)
        '''
        zn_dmpr = deepcopy(self.zn_dmpr_arr)
        zn_dmpr.sort(reverse=True)
        zn_dmpr = zn_dmpr[
            :int(math.ceil(len(self.zn_dmpr_arr)*0.5))
            if len(self.zn_dmpr_arr) != 1 else 1]
        avg_zone_damper = np.mean(zn_dmpr)
        avg_stcpr_sp = None
        if self.stcpr_sp_arr:
            avg_stcpr_sp = np.mean(self.stcpr_sp_arr)
        if avg_zone_damper <= self.hdzn_dmpr_thr:
            if avg_stcpr_sp is not None and not stc_override_check:
                if self.auto_correctflag:
                    stcpr_sp = avg_stcpr_sp - self.stcpr_retuning
                    if stcpr_sp >= self.min_stcpr_sp:
                        result.command(self.stcpr_sp_cname, stcpr_sp)
                        stcpr_sp = '%s' % float('%.2g' % self.min_stcpr_sp)
                        stcpr_sp = stcpr_sp + ' in. w.g.'
                        msg = ('The duct static pressure was detected to be '
                               'too high. The duct static pressure set point '
                               'has been reduced to: {val}'
                               .format(val=stcpr_sp))
                        dx_msg = 21.1
                    else:
                        result.command(self.stcpr_sp_cname, self.min_stcpr_sp)
                        stcpr_sp = '%s' % float('%.2g' % self.min_stcpr_sp)
                        stcpr_sp = stcpr_sp + ' in. w.g.'
                        msg = ('The duct static pressure set point is at the '
                               'minimum value configured by the building '
                               'operator: {val})'.format(val=stcpr_sp))
                        dx_msg = 22.1
                else:
                    msg = ('Duct static pressure set point was detected to be '
                           'too high but auto-correction is not enabled.')
                    dx_msg = 23.1
            elif not stc_override_check:
                msg = 'The duct static pressure was detected to be too high.'
                dx_msg = 24.1
            else:
                msg = ('The duct static pressure was detected to be too high '
                       'but an operator override was detected. Auto-correction'
                       ' can not be performed when the static pressure set '
                       'point or fan speed command is in override.')
                dx_msg = 25.1
        else:
            msg = ('No re-tuning opportunity was detected during the low duct '
                   'static pressure diagnostic.')
            dx_msg = 20.0

        dx_table = {
            DUCT_STC_RCX2 + DX: dx_msg
        }
        result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result
