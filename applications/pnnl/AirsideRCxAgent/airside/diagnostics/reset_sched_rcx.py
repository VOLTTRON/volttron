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
from volttron.platform.agent.math_utils import mean
import datetime
from datetime import datetime
import logging
from dateutil.parser import parse
from .common import validation_builder

SCHED_VALIDATE = 'Schedule-Reset ACCx'
DUCT_STC_RCX3 = 'No Static Pressure Reset Dx'
SA_TEMP_RCX3 = 'No Supply-air Temperature Reset Dx'
SCHED_RCX = 'Operational Schedule Dx'
DX = '/diagnostic message'
VALIDATE_FILE_TOKEN = 'reset-schedule'
RESET_FILE_TOKEN = 'reset'
SCHEDULE_FILE_TOKEN = 'schedule'
DATA = '/data/'
ST = 'state'

def create_table_key(table_name, timestamp):
    return '&'.join([table_name, timestamp.strftime('%m-%d-%y %H:%M')])


class SchedResetRcx(object):
    """Schedule, supply-air temperature, and duct static pressure auto-detect
    diagnostics for AHUs or RTUs.
    """
    def __init__(self, unocc_time_threshold, unocc_stp_threshold,
                 monday_sch, tuesday_sch, wednesday_sch, thursday_sch,
                 friday_sch, saturday_sch, sunday_sch,
                 no_req_data, stpr_reset_threshold, sat_reset_threshold,
                 analysis):
        self.fanstat_values = []
        self.schedule = {}
        self.stcpr_arr = []
        self.stcpr_stpt_arr = []
        self.sat_stpt_arr = []
        self.timestamp = []
        self.sched_time = []
        self.dx_table = {}

        def date_parse(dates):
            return [parse(timestamp).time() for timestamp in dates]

        self.analysis = analysis
        self.sched_file_name_id = analysis + '-' + SCHEDULE_FILE_TOKEN
        self.reset_file_name_id = analysis + '-' + RESET_FILE_TOKEN
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

    def reinitialize(self, start_new_analysis_time, start_new_analysis_sat_stpt,
                     start_new_analysis_stcpr_stpt, stcpr_data, fan_status):
        """Reinitialize data arrays"""
        self.sat_stpt_arr = []
        self.stcpr_arr = []
        self.stcpr_stpt_arr = []
        self.fanstat_values = []
        self.sched_time = []
        self.dx_table = {}
        if start_new_analysis_stcpr_stpt is not None:
            self.sat_stpt_arr.append(start_new_analysis_sat_stpt)
            self.stcpr_stpt_arr.append(start_new_analysis_stcpr_stpt)
        if fan_status is not None:
            self.fanstat_values.append((start_new_analysis_time,fan_status))
            self.stcpr_arr.extend(stcpr_data)
        self.timestamp = [start_new_analysis_time]

    def sched_rcx_alg(self, current_time, stcpr_data, stcpr_stpt_data,
                      sat_stpt_data, fan_stat_data, dx_result):
        """Check schedule status and unit operational status."""
        dx_status = 1
        fan_status = None
        schedule = self.schedule[current_time.weekday()]
        run_diagnostic = False
        start_new_analysis_sat_stpt = None
        start_new_analysis_stcpr_stpt = None

        if self.timestamp and self.timestamp[-1].date() != current_time.date():
            start_new_analysis_time = current_time
            run_diagnostic = True

        if not run_diagnostic:
            if current_time.time() < schedule[0] or current_time.time() > schedule[1]:
                self.stcpr_arr.extend(stcpr_data)
                self.fanstat_values.append((current_time, int(max(fan_stat_data))))
                self.sched_time.append(current_time)
            if int(max(fan_stat_data)):
                self.stcpr_stpt_arr.append(mean(stcpr_stpt_data))
                self.sat_stpt_arr.append(mean(sat_stpt_data))
        fan_status = int(max(fan_stat_data))
        start_new_analysis_sat_stpt = mean(stcpr_stpt_data)
        start_new_analysis_stcpr_stpt = mean(sat_stpt_data)
        self.timestamp.append(current_time)

        reset_key = create_table_key(self.reset_file_name_id, self.timestamp[0])
        schedule_key = create_table_key(self.sched_file_name_id, self.timestamp[0])
        file_key = create_table_key(VALIDATE_FILE_TOKEN, current_time)
        if run_diagnostic and len(self.timestamp) >= self.no_req_data:
            dx_result = self.unocc_fan_operation(dx_result)
            if len(self.stcpr_stpt_arr) >= self.no_req_data:
                dx_result = self.no_static_pr_reset(dx_result)
                dx_status += 1
            if len(self.sat_stpt_arr) >= self.no_req_data:
                dx_result = self.no_sat_stpt_reset(dx_result)
                dx_status += 2
            if self.dx_table:
                dx_result.insert_table_row(reset_key, self.dx_table)
            
            self.reinitialize(start_new_analysis_time, start_new_analysis_sat_stpt,
                              start_new_analysis_stcpr_stpt, stcpr_data, fan_status)
        elif run_diagnostic:
            dx_msg = 61.2
            dx_table = {SCHED_RCX + DX:  dx_msg}
            dx_result.insert_table_row(schedule_key, dx_table)
            
            self.reinitialize(start_new_analysis_time, start_new_analysis_sat_stpt,
                              start_new_analysis_stcpr_stpt, stcpr_data, fan_status)
            dx_status = 0

        return dx_status, dx_result

    def unocc_fan_operation(self, dx_result):
        """If the AHU/RTU is operating during unoccupied periods inform the
        building operator.
        """
        avg_duct_stcpr = 0
        percent_on = 0
        fanstat_on = [(fan[0].hour, fan[1]) for fan in self.fanstat_values if int(fan[1]) == 1]
        fanstat = [(fan[0].hour, fan[1]) for fan in self.fanstat_values]
        hourly_counter = []

        for counter in range(24):
            fan_on_count = [fan_status_time[1] for fan_status_time in fanstat_on if fan_status_time[0] == counter]
            fan_count = [fan_status_time[1] for fan_status_time in fanstat if fan_status_time[0] == counter]
            if len(fan_count):
                hourly_counter.append(fan_on_count.count(1)/len(fan_count)*100)
            else:
                hourly_counter.append(0)

        if self.sched_time:
            if self.fanstat_values:
                percent_on = (len(fanstat_on)/len(self.fanstat_values)) * 100.0
            if self.stcpr_arr:
                avg_duct_stcpr = mean(self.stcpr_arr)

            if percent_on > self.unocc_time_threshold:
                msg = 'Supply fan is on during unoccupied times.'
                dx_msg = 63.1
            else:
                if avg_duct_stcpr < self.unocc_stp_threshold:
                    msg = 'No problems detected for schedule diagnostic.'
                    dx_msg = 60.0
                else:
                    msg = ('Fan status show the fan is off but the duct static '
                           'pressure is high, check the functionality of the '
                           'pressure sensor.')
                    dx_msg = 64.2
        else:
            msg = 'No problems detected for schedule diagnostic.'
            dx_msg = 60.0

        if dx_msg != 64.2:
            for _hour in range(24):
                push_time = self.timestamp[0].date()
                push_time = datetime.combine(push_time, datetime.min.time())
                push_time = push_time.replace(hour=_hour)
                dx_table = {SCHED_RCX + DX: 60.0}
                if hourly_counter[_hour] > self.unocc_time_threshold:
                    dx_table = {SCHED_RCX + DX:  dx_msg}
                table_key = create_table_key(self.sched_file_name_id, push_time)
                dx_result.insert_table_row(table_key, dx_table)
        else:
            push_time = self.timestamp[0].date()
            table_key = create_table_key(self.sched_file_name_id, push_time)
            dx_result.insert_table_row(table_key, {SCHED_RCX + DX:  dx_msg})
        dx_result.log(msg, logging.INFO)
        return dx_result

    def no_static_pr_reset(self, dx_result):
        """Auto-RCx  to detect whether a static pressure set point

        reset is implemented.
        """
        if not self.stcpr_stpt_arr:
            return dx_result

        stcpr_daily_range = (max(self.stcpr_stpt_arr) - min(self.stcpr_stpt_arr))

        if stcpr_daily_range < self.stpr_reset_threshold:
            msg = ('No duct static pressure reset detected. A duct static '
                   'pressure set point reset can save significant energy.')
            dx_msg = 71.1
        else:
            msg = ('No problems detected for duct static pressure set point '
                   'reset diagnostic.')
            dx_msg = 70.0
        dx_table = {DUCT_STC_RCX3 + DX:  dx_msg}
        self.dx_table = dx_table
        dx_result.log(msg, logging.INFO)
        return dx_result

    def no_sat_stpt_reset(self, dx_result):
        """Auto-RCx  to detect whether a supply-air temperature set point

        reset is implemented.
        """
        if not self.sat_stpt_arr:
            return dx_result

        satemp_daily_range = max(self.sat_stpt_arr) - min(self.sat_stpt_arr)
        if satemp_daily_range <= self.sat_reset_threshold:
            msg = ('A supply-air temperature reset was not detected. '
                   'This can result in excess energy consumption.')
            dx_msg = 81.1
        else:
            msg = ('No problems detected for supply-air temperature set point '
                   'reset diagnostic.')
            dx_msg = 80.0
        dx_table = {SA_TEMP_RCX3 + DX:  dx_msg}
        self.dx_table.update(dx_table)
        dx_result.log(msg, logging.INFO)
        return dx_result
