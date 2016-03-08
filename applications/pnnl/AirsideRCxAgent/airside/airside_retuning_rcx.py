
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
import datetime
from datetime import timedelta as td
import logging
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
from airside.diagnostics.satemp_rcx import SupplyTempRcx
from airside.diagnostics.stcpr_rcx import DuctStaticRcx
from airside.diagnostics.reset_sched_rcx import SchedResetRcx


class Application(AbstractDrivenAgent):
    '''
    Air-side HVAC Auto-Retuning Diagnostics
    for AHUs.
    '''
    def __init__(self, no_required_data=1, data_window=1, warm_up_time=0,
                 stcpr_retuning=0.15, max_stcpr_stpt=2.5, high_sf_thr=100.0,
                 zn_hdmpr_thr=90.0, zn_lowdmpr_thr=10.0, min_stcpr_stpt=0.5,
                 hdzn_dmpr_thr=30.0, low_sf_thr=20.0, stpt_allowable_dev=10.0,

                 stcpr_reset_thr=0.25, pc_rht_thr=25.0, rht_on_threshold=10.0,
                 sat_reset_threshold=5.0, sat_hdmpr_thr=80.0, pc_dmpr_thr=50.0,
                 min_sat_stpt=50.0, sat_retuning=1.0, rht_valve_thr=50.0,
                 max_sat_stpt=75.0,

                 unocc_time_thr=30.0, unocc_stp_threshold=0.2,
                 mon_sch='5:00;18:30', tues_sch='5:00;18:30',
                 wed_sch='5:00;18:30', thur_sch='5:00;18:30',
                 fri_sch='5:00;18:30', sat_sch='0:00;0:00',
                 sun_sch='0:00;0:00', **kwargs):
        self.pre_msg = []
        self.pre_msg_time = []
        self.warm_up_start = None
        auto_correctflag = True
        self.warm_up_flag = None

        # Pre-requisite messages
        self.pre_msg0 = (
            'Fan Status is not available, could not verify system is ON.')
        self.pre_msg1 = (
            'Supply fan is off, current data will not be used.')
        self.pre_msg2 = ('Missing required data: duct static pressure.')
        self.pre_msg3 = (
            'Missing required data: duct static pressure set point')
        self.pre_msg4 = (
            'Missing required data: terminal-box damper-position (all zones).')
        self.pre_msg5 = ('Missing required data for diagnostic: SAT.')
        self.pre_msg6 = (
            'Missing required data: TB reheat-valve-positions (all zones).')
        self.pre_msg7 = ('Missing required data: SAT set point.')

        # Point names (Configurable)
        def get_or_none(name):
            value = kwargs.get(name, None)
            if value:
                value = value.lower()
            return value

        analysis = kwargs['device']['analysis_name']
        self.fan_status_name = get_or_none('fan_status')
        self.duct_stp_stpt_name = get_or_none('duct_stp_stpt')
        self.duct_stp_name = get_or_none('duct_stp')
        self.sa_temp_name = get_or_none('sa_temp')
        self.sat_stpt_name = get_or_none('sat_stpt')
        self.fansp_name = get_or_none('fan_speedcmd')
        sat_stpt_cname = self.sat_stpt_name
        duct_stp_stpt_cname = self.duct_stp_stpt_name
#         # Optional points
#         self.override_state = 'AUTO'
#         self.fan_speedcmd_priority = get_or_none('fan_speedcmd_priority')
#         self.duct_stp_stpt_priority = get_or_none('duct_stp_stpt_priority')
#         self.ahu_ccoil_priority = get_or_none('ahu_ccoil_priority')
#         self.sat_stpt_priority = get_or_none('sat_stpt_priority')

        # Zone Parameters
        self.zone_damper_name = get_or_none('zone_damper')
        self.zone_reheat_name = get_or_none('zone_reheat')

        # Application thresholds (Configurable)
        self.data_window = float(data_window)
        no_required_data = int(no_required_data)
        self.low_sf_thr = float(low_sf_thr)
        self.high_sf_thr = float(high_sf_thr)
        self.warm_up_time = int(warm_up_time)

        self.static_dx = (
            DuctStaticRcx(data_window, no_required_data, auto_correctflag,
                          stpt_allowable_dev, max_stcpr_stpt, stcpr_retuning,
                          zn_hdmpr_thr, zn_lowdmpr_thr, hdzn_dmpr_thr,
                          min_stcpr_stpt, analysis, duct_stp_stpt_cname))
        self.sat_dx = (
            SupplyTempRcx(data_window, no_required_data, auto_correctflag,
                          stpt_allowable_dev, rht_on_threshold, sat_hdmpr_thr,
                          pc_dmpr_thr, pc_rht_thr, min_sat_stpt, sat_retuning,
                          rht_valve_thr, max_sat_stpt, analysis, sat_stpt_cname))
        self.sched_occ_dx = (
            SchedResetRcx(unocc_time_thr, unocc_stp_threshold, mon_sch,
                          tues_sch, wed_sch, thur_sch, fri_sch, sat_sch,
                          sun_sch, data_window, no_required_data,
                          stcpr_reset_thr, sat_reset_threshold, analysis))

    def run(self, cur_time, points):
        '''Check application pre-quisites and assemble analysis data set.
        Receives mapped data from the DrivenBaseClass. Filters non-relevent
        data and assembles analysis data set for diagnostics.
        '''
        device_dict = {}
        dx_result = Results()

        for key, value in points.items():
            device_dict[key.lower()] = value
        supply_fan_off = False
        fan_stat_data = []
        fan_stat_check = False

        # Verify supply fan data is available and that
        # the supply fan is ON
        for key, value in device_dict.items():
            if key.startswith(self.fan_status_name) and value is not None:
                fan_stat_check = True
                fan_stat_data.append(value)
                if not value:
                    self.warm_up_flag = True
                    self.pre_msg.append(self.pre_msg1)
                    dx_result = self.pre_message(dx_result, cur_time)
                    supply_fan_off = True

        if not fan_stat_check and self.fansp_name is not None:
            for key, value in device_dict.items():
                if key.startswith(self.fansp_name) and value is not None:
                    fan_stat_check = True
                    if value < self.low_sf_thr:
                        self.warm_up_flag = True
                        self.pre_msg.append(self.pre_msg1)
                        dx_result = self.pre_message(dx_result, cur_time)
                        return dx_result
                    fan_stat_data.append(1)
                    supply_fan_off = False

        if not fan_stat_check:
            self.pre_msg.append(self.pre_msg0)
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result

        low_dx_cond = False
        high_dx_cond = False
        static_override_check = False
        sat_override_check = False

        for key, value in device_dict.items():
            if self.fansp_name is not None and self.fansp_name in key:
                if value is not None and value > self.high_sf_thr:
                    low_dx_cond = True
                elif value is not None and value < self.low_sf_thr:
                    high_dx_cond = True

        stc_pr_data = []
        stcpr_sp_data = []
        zn_dmpr_data = []
        satemp_data = []
        rht_data = []
        sat_stpt_data = []
        validate = {}
        sched_val = {}

        # Verify data availability and map to correct array
        for key, value in device_dict.items():
            parts = key.split('_')
            point_name = parts[0]
            tag = ''.join([parts[1], '/', parts[0], '/'])
            if point_name == self.duct_stp_stpt_name and value is not None:
                validate.update({tag: value})
                sched_val.update(validate)
                stcpr_sp_data.append(value)
            elif point_name == self.sat_stpt_name and value is not None:
                validate.update({tag: value})
                sched_val.update(validate)
                sat_stpt_data.append(value)
            elif point_name == self.duct_stp_name and value is not None:
                validate.update({tag: value})
                sched_val.update(validate)
                stc_pr_data.append(value)
            elif point_name == self.sa_temp_name and value is not None:
                validate.update({tag: value})
                sched_val.update(validate)
                satemp_data.append(value)
            elif point_name.startswith(self.zone_reheat_name) and value is not None:
                validate.update({tag: value})
                rht_data.append(value)
            elif point_name.startswith(self.zone_damper_name) and value is not None:
                validate.update({tag: value})
                zn_dmpr_data.append(value)

        if not stc_pr_data:
            self.pre_msg.append(self.pre_msg2)
        if not stcpr_sp_data:
            self.pre_msg.append(self.pre_msg3)
        if not zn_dmpr_data:
            self.pre_msg.append(self.pre_msg4)
        if not (stc_pr_data and zn_dmpr_data and stcpr_sp_data):
            return dx_result

        if not satemp_data:
            self.pre_msg.append(self.pre_msg5)
        if not rht_data:
            self.pre_msg.append(self.pre_msg6)
        if not sat_stpt_data:
            self.pre_msg.append(self.pre_msg7)
        if not satemp_data or not rht_data or not sat_stpt_data:
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result

        dx_result = (
            self.sched_occ_dx.sched_rcx_alg(cur_time, stc_pr_data,
                                            stcpr_sp_data, sat_stpt_data,
                                            fan_stat_data, dx_result,
                                            sched_val))
        if supply_fan_off:
            return dx_result

        if self.warm_up_flag:
            self.warm_up_flag = False
            self.warm_up_start = cur_time
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result

        time_check = td(minutes=self.warm_up_time)
        if (self.warm_up_start is not None and
                (cur_time - self.warm_up_start) < time_check):
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result

        dx_result = (
            self.static_dx.duct_static(cur_time, stcpr_sp_data, stc_pr_data,
                                       zn_dmpr_data, static_override_check,
                                       low_dx_cond, high_dx_cond, dx_result,
                                       validate))
        dx_result = (
            self.sat_dx.sat_rcx(cur_time, satemp_data, sat_stpt_data, rht_data,
                                zn_dmpr_data, dx_result, sat_override_check,
                                validate))
        return dx_result

    def pre_message(self, result, cur_time):
        '''Add meaningful output based to results table if analysis
        cannot be run.
        '''
        self.pre_msg_time.append(cur_time)
        pre_check = self.pre_msg_time[-1] - self.pre_msg_time[0]
        pre_check = pre_check.total_seconds()/60
        pre_check = pre_check if pre_check > 0.0 else 1.0
        if pre_check >= self.data_window:
            msg_lst = \
                [self.pre_msg0, self.pre_msg1, self.pre_msg2, self.pre_msg3,
                 self.pre_msg4, self.pre_msg5, self.pre_msg6, self.pre_msg7]

            for item in msg_lst:
                if (self.pre_msg.count(item) >
                        (0.25) * len(self.pre_msg_time)):
                    result.log(item, logging.DEBUG)
            self.pre_msg = []
            self.pre_msg_time = []
        return result
