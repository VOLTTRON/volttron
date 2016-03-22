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
import re
import logging
from .common import validation_builder
SCHED_VALIDATE = 'Schedule-Reset ACCx'
DUCT_STC_RCX3 = 'No Static Pressure Reset Dx'
SA_TEMP_RCX3 = 'No Supply-air Temperature Reset Dx'
SCHED_RCX = 'Operational Schedule Dx'
DX = '/diagnostic message'
VALIDATE_FILE_TOKEN = 'reset-scheule'
DATA = '/data/'
ST = 'state'

class SchedResetRcx(object):
    '''Schedule, supply-air temperature, and duct static pressure auto-detect
    diagnostics for AHUs or RTUs.
    '''
    def __init__(self, unocc_time_threshold, unocc_stp_threshold,
                 monday_sch, tuesday_sch, wednesday_sch, thursday_sch,
                 friday_sch, saturday_sch, sunday_sch,
                 no_req_data, stpr_reset_threshold, sat_reset_threshold,
                 analysis):

        self.act_sch = []
        self.fanstat_values = []
        self.schedule = {}
        self.stcpr_arr = []
        self.stcpr_stpt_arr = []
        self.sat_stpt_arr = []
        self.timestamp = []
        self.sched_time = []
        self.dx_time = None

        def date_parse(date):
            date = re.sub('[:;]', ',', date)
            return [int(item) for item in (x.strip() for x in date.split(','))]

        self.analysis = analysis
        self.monday_sch = date_parse(monday_sch)
        self.tuesday_sch = date_parse(tuesday_sch)
        self.wednesday_sch = date_parse(wednesday_sch)
        self.thursday_sch = date_parse(thursday_sch)
        self.friday_sch = date_parse(friday_sch)
        self.saturday_sch = date_parse(saturday_sch)
        self.sunday_sch = date_parse(sunday_sch)

        self.schedule = {0: self.monday_sch, 1: self.tuesday_sch,
                         2: self.wednesday_sch, 3: self.thursday_sch,
                         4: self.friday_sch, 5: self.saturday_sch,
                         6: self.sunday_sch}
        self.pre_msg = ('Current time is in the scheduled hours '
                        'unit is operating correctly.')

        # Application thresholds (Configurable)
        self.no_req_data = no_req_data
        self.unocc_time_threshold = float(unocc_time_threshold)
        self.unocc_stp_threshold = float(unocc_stp_threshold)
        self.stpr_reset_threshold = float(stpr_reset_threshold)
        self.sat_reset_threshold = float(sat_reset_threshold)

    def reinitialize(self, avg_sat_stpt, avg_stcpr_stpt, duct_stcpr, fan_status):
        """Reinitialize data arrays"""
        self.sat_stpt_arr = []
        self.stcpr_arr = []
        self.stcpr_stpt_arr = []
        self.fanstat_values = []
        self.sched_time = []
        self.dx_time = None
        if avg_stcpr_stpt is not None:
            self.sat_stpt_arr.append(avg_sat_stpt)
            self.stcpr_stpt_arr.append(avg_stcpr_stpt)
        if fan_status is not None:
            self.fanstat_values.append(fan_status)
            self.stcpr_arr.extend(duct_stcpr)
        self.timestamp = [self.timestamp[-1]]

    def sched_rcx_alg(self, cur_time, stcpr_data, stcpr_stpt_data,
                      sat_stpt_data, fan_stat_data, dx_result,
                      sched_val):
        '''Check schedule status and unit operational status.'''
        fan_status = None
        stcpr_sp_val = None
        schedule = self.schedule[cur_time.weekday()]
        run_diagnostic = False

        if self.timestamp and self.timestamp[-1].date() != cur_time.date():
            self.start_of_next_analysis = self.timestamp[-1].date()
            run_diagnostic = True

        if((cur_time.hour < schedule[0] or
           (cur_time.hour == schedule[0] and cur_time.minute < schedule[1])) or
           (cur_time.hour > schedule[2] or
           (cur_time.hour == schedule[2] and cur_time.minute < schedule[3]))):
            if not run_diagnostic:
                self.stcpr_arr.extend(stcpr_data)
                self.fanstat_values.append(int(max(fan_stat_data)))
                self.sched_time.append(cur_time)
            fan_status = int(max(fan_stat_data))
            duct_stcpr = stcpr_data
        else:
            if int(max(fan_stat_data)):
                if not run_diagnostic:
                    self.stcpr_stpt_arr.append(np.mean(stcpr_stpt_data))
                    self.sat_stpt_arr.append(np.mean(sat_stpt_data))
                avg_stcpr_stpt = np.mean(stcpr_stpt_data)
                avg_sat_stpt = np.mean(sat_stpt_data)
        self.timestamp.append(cur_time)

        data = validation_builder(sched_val, SCHED_VALIDATE, DATA)

        if run_diagnostic and len(self.sched_time) >= self.no_req_data and len(self.sat_stpt_arr) >= self.no_req_data:
            dx_result = self.unocc_fan_operation(dx_result)
            dx_result = self.no_static_pr_reset(dx_result)
            dx_result = self.no_sat_sp_reset(dx_result)
            data.update({SCHED_VALIDATE + DATA + ST: 1})
            self.reinitialize(avg_sat_stpt, avg_stcpr_stpt, duct_stcpr, fan_status)
        elif run_diagnostic:
            dx_msg = 61.2
            dx_table = {SCHED_RCX + DX:  dx_msg}
            dx_result.insert_table_row(self.analysis, dx_table)
            data.update({SCHED_VALIDATE + DATA + ST: 2})
            self.reinitialize(avg_sat_stpt, avg_stcpr_stpt, duct_stcpr, fan_status)
        else:
            data.update({SCHED_VALIDATE + DATA + ST: 0})
        dx_result.insert_table_row(VALIDATE_FILE_TOKEN, data)
        return dx_result

    def unocc_fan_operation(self, result):
        '''If the AHU/RTU is operating during unoccupied periods inform the
        building operator.
        '''
        fanstat_on = [i for i in self.fanstat_values if int(i) == 1]
        if self.fanstat_values:
            percent_on = (len(fanstat_on)/len(self.fanstat_values)) * 100.0
        else:
            percent_on = 0
        if self.stcpr_arr:
            avg_duct_stpr = np.mean(self.stcpr_arr)
        else:
            avg_duct_stpr = 0
        if percent_on > self.unocc_time_threshold:
            msg = 'Supply fan is on during unoccupied times.'
            dx_msg = 63.1
        else:
            if avg_duct_stpr < self.unocc_stp_threshold:
                msg = 'No problems detected.'
                dx_msg = 60.0
            else:
                msg = ('Fan status show the fan is off but the duct static '
                       'pressure is high, check the functionality of the '
                       'pressure sensor.')
                dx_msg = 64.2
        for item in self.sched_time:
            dx_table = {SCHED_RCX + DX:  dx_msg}
            result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def no_static_pr_reset(self, result):
        '''Auto-RCx  to detect whether a static pressure set point

        reset is implemented.
        '''
        if not self.stcpr_stpt_arr:
            return result
        stp_diff = (max(self.stcpr_stpt_arr) - min(self.stcpr_stpt_arr))

        if stp_diff < self.stpr_reset_threshold:
            msg = ('No duct static pressure reset detected. A duct static '
                   'pressure set point reset can save significant energy.')
            dx_msg = 71.1
        else:
            msg = 'No problem detected.'
            dx_msg = 70.0
        dx_table = {DUCT_STC_RCX3 + DX:  dx_msg}
        result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def no_sat_sp_reset(self, result):
        '''Auto-RCx  to detect whether a supply-air temperature set point

        reset is implemented.
        '''
        if not self.sat_stpt_arr:
            return result
        satemp_diff = max(self.sat_stpt_arr) - min(self.sat_stpt_arr)
        if satemp_diff <= self.sat_reset_threshold:
            msg = ('A supply-air temperature reset was not detected. '
                   'This can result in excess energy consumption.')
            dx_msg = 81.1
        else:
            msg = 'No problems detected for this diagnostic.'
            dx_msg = 80.0
        dx_table = {SA_TEMP_RCX3 + DX:  dx_msg}
        result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result
