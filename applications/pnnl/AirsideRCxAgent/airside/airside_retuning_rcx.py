"""
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
"""

from datetime import timedelta as td
import sys
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
from diagnostics.satemp_rcx import SupplyTempRcx
from diagnostics.stcpr_rcx import DuctStaticRcx
from diagnostics.reset_sched_rcx import SchedResetRcx


class Application(AbstractDrivenAgent):
    """
    Air-side HVAC Auto-Retuning Diagnostics
    for AHUs.

    Note:
        All configurable threshold have default threshold that work well with most equipment/configurations.

    Args:
        no_required_data (int): minimum number of measurements required for
            conclusive analysis.
        warm_up_time (int): Number of minutes after equipment startup prior
            to beginning data collection for analysis.
        duct_stcpr_retuning (float): Amount to increment or decrement the duct
            static pressure set point high/low duct static pressure set point
            problem is detected (assumed to be in inches water column (gauge)).
        max_duct_stcpr_stpt (float): Maximum value for the duct static pressure set
            point when applying auto-correction.
        high_sf_threshold (float): Auto-correction for low duct static pressure set point
            will not be effective if the supply fan for the AHU is operating at or near 100%
            of full speed. Auto-correction will not be applied if this condition exists.
        zone_high_damper_threshold (float):
        zone_low_damper_threshold (float):
        min_duct_stcpr_stpt (float): Minimum value for the duct static pressure set
            point when applying auto-correction.
        low_sf_threshold (float): Auto-correction for high duct static pressure set point
            will not be effective if the supply fan for the AHU is operating at or near its
            minimum SupplyFanSpeed. Auto-correction will not be applied if this condition exists.
            If the SupplyFanStatus is not available, the supply fan speed can be used
            to determine if the supply fan is operating. The supply fan will be considered
            ON when operating at speeds above the minimum SupplyFanSpeed.
        setpoint_allowable_deviation (float): Maximum acceptable deviation set point for the supply-air
            temperature and the duct static pressure (averaged over an analysis period, typically one hour).
        stcpr_reset_threshold (float):
        percent_reheat_threshold (float):
        rht_on_threshold (float):
        sat_reset_threshold (float):
        sat_high_damper_threshold (float):
        percent_damper_threshold (float):
        min_sat_stpt (float):
        sat_retuning (float):
        reheat_valve_threshold (float):
        max_sat_stpt (float):

    """
    def __init__(
            self, no_required_data=10, warm_up_time=15,
            duct_stcpr_retuning=0.15, max_duct_stcpr_stpt=2.5,
            high_sf_threshold=100.0, zone_high_damper_threshold=90.0,
            zone_low_damper_threshold=10.0, min_duct_stcpr_stpt=0.5,
            hdzone_damper_threshold=30.0, low_sf_threshold=20.0,
            setpoint_allowable_deviation=10.0, stcpr_reset_threshold=0.25,

            percent_reheat_threshold=25.0, rht_on_threshold=10.0,
            sat_reset_threshold=5.0, sat_high_damper_threshold=80.0,
            percent_damper_threshold=50.0, min_sat_stpt=50.0,
            sat_retuning=1.0, reheat_valve_threshold=50.0,
            max_sat_stpt=75.0,

            unocc_time_threshold=30.0, unocc_stp_threshold=0.2,
            monday_sch=['5:30', '18:30'], tuesday_sch=['5:30', '18:30'],
            wednesday_sch=['5:30', '18:30'], thursday_sch=['5:30', '18:30'],
            friday_sch=['5:30', '18:30'], saturday_sch=['0:00', '0:00'],
            sunday_sch=['0:00', '0:00'], auto_correct_flag=False,
            analysis_name='', **kwargs):

        self.warm_up_start = None
        self.warm_up_flag = True

        # Point names (Configurable)
        def get_or_none(name):
            value = kwargs.get(name, None)
            if value:
                value = value.lower()
            return value

        analysis = analysis_name
        self.fan_status_name = get_or_none('fan_status')
        self.fansp_name = get_or_none('fan_speedcmd')
        if self.fansp_name  is None and self.fan_status_name is None:
            raise Exception('SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.')
        self.duct_stp_stpt_name = get_or_none('duct_stp_stpt')
        self.duct_stp_name = get_or_none('duct_stp')
        self.sa_temp_name = get_or_none('sa_temp')
        self.sat_stpt_name = get_or_none('sat_stpt')
        sat_stpt_cname = self.sat_stpt_name
        duct_stp_stpt_cname = self.duct_stp_stpt_name
        # Zone Parameters
        self.zone_damper_name = get_or_none('zone_damper')
        self.zone_reheat_name = get_or_none('zone_reheat')

        no_required_data = int(no_required_data)
        self.low_sf_threshold = float(low_sf_threshold)
        self.high_sf_threshold = float(high_sf_threshold)
        self.warm_up_time = int(warm_up_time)
        self.static_dx = (
            DuctStaticRcx(no_required_data, auto_correct_flag,
                          setpoint_allowable_deviation, max_duct_stcpr_stpt,
                          duct_stcpr_retuning, zone_high_damper_threshold,
                          zone_low_damper_threshold, hdzone_damper_threshold,
                          min_duct_stcpr_stpt, analysis, duct_stp_stpt_cname))
        self.sat_dx = (
            SupplyTempRcx(no_required_data, auto_correct_flag,
                          setpoint_allowable_deviation, rht_on_threshold,
                          sat_high_damper_threshold, percent_damper_threshold,
                          percent_reheat_threshold, min_sat_stpt, sat_retuning,
                          reheat_valve_threshold, max_sat_stpt, analysis, sat_stpt_cname))
        self.sched_occ_dx = (
            SchedResetRcx(unocc_time_threshold, unocc_stp_threshold,
                          monday_sch, tuesday_sch, wednesday_sch, thursday_sch,
                          friday_sch, saturday_sch, sunday_sch,
                          no_required_data, stcpr_reset_threshold,
                          sat_reset_threshold, analysis))

    def run(self, cur_time, points):
        device_dict = {}
        dx_result = Results()
        fan_status_data = []
        supply_fan_off = False
        low_dx_cond = False
        high_dx_cond = False

        for key, value in points.items():
            point_device = [_name.lower() for _name in key.split('&')]
            if point_device[0] not in device_dict:
                device_dict[point_device[0]] = [(point_device[1], value)]
            else:
                device_dict[point_device[0]].append((point_device[1], value))

        if self.fan_status_name in device_dict:
            fan_status = device_dict[self.fan_status_name]
            fan_status = [point[1] for point in fan_status]
            fan_status = [status for status in fan_status if status is not None]
            if fan_status_data:
                fan_status_data.append(min(fan_status))
                if not int(fan_status_data[0]):
                    supply_fan_off = True
                    self.warm_up_flag = True

        if self.fansp_name in device_dict:
            fan_speed = device_dict[self.fansp_name]
            fan_speed = mean([point[1] for point in fan_speed])
            if self.fan_status_name is None:
                if not int(fan_speed):
                    supply_fan_off = True
                    self.warm_up_flag = True
                fan_status_data.append(bool(int(fan_speed)))

            if fan_speed > self.high_sf_threshold:
                low_dx_cond = True
            elif fan_speed < self.low_sf_threshold:
                high_dx_cond = True

        stc_pr_data = []
        stcpr_sp_data = []
        zn_dmpr_data = []
        satemp_data = []
        rht_data = []
        sat_stpt_data = []
        validate = {}
        sched_val = {}

        def validate_builder(value_tuple, point_name):
            value_list = []
            for item in value_tuple:
                tag = item[0] + '/' + point_name
                validate.update({tag: item[1]})
                value_list.append(item[1])
            return value_list

        for key, value in device_dict.items():
            data_name = key
            if value is None:
                continue
            if data_name == self.duct_stp_stpt_name:
                stcpr_sp_data = validate_builder(value, data_name)
                sched_val.update(validate)
            elif data_name == self.sat_stpt_name:
                sat_stpt_data = validate_builder(value, data_name)
                sched_val.update(validate)
            elif data_name == self.duct_stp_name:
                sched_val.update(validate)
                stc_pr_data = validate_builder(value, data_name)
                sched_val.update(validate)
            elif data_name == self.sa_temp_name:
                satemp_data = validate_builder(value, data_name)
                sched_val.update(validate)
            elif data_name == self.zone_reheat_name:
                rht_data = validate_builder(value, data_name)
            elif data_name == self.zone_damper_name:
                zn_dmpr_data = validate_builder(value, data_name)

        missing_data = []
        if not satemp_data:
            missing_data.append(self.sa_temp_name)
        if not rht_data:
            missing_data.append(self.zone_reheat_name)
        if not sat_stpt_data:
            dx_result.log('Supply-air temperature set point data is '
                          'missing. This will limit the effectiveness of '
                          'the supply-air temperature diagnostics.')
        if not stc_pr_data:
            missing_data.append(self.duct_stp_name)
        if not stcpr_sp_data:
            dx_result.log('Duct static pressure set point data is '
                          'missing. This will limit the effectiveness of '
                          'the duct static pressure diagnostics.')
        if not zn_dmpr_data:
            missing_data.append(self.zone_damper_name)
        if not fan_status:
            missing_data.append(self.fan_status_name)
        if missing_data:
            raise Exception('Missing required data: {}'.format(missing_data))
            return dx_result
        dx_result = (
            self.sched_occ_dx.sched_rcx_alg(cur_time, stc_pr_data,
                                            stcpr_sp_data, sat_stpt_data,
                                            fan_status, dx_result,
                                            sched_val))
        if supply_fan_off:
            dx_result.log('Supply fan is off. Data will not be used for '
                          'retuning diagnostics.')
            return dx_result
        if self.warm_up_flag:
            self.warm_up_flag = False
            self.warm_up_start = cur_time
            return dx_result
        time_check = td(minutes=self.warm_up_time)
        if (self.warm_up_start is not None and
                (cur_time - self.warm_up_start) < time_check):
            dx_result.log('Unit is in warm-up. Data will not be analyzed.')
            return dx_result
        dx_result = (
            self.static_dx.duct_static(cur_time, stcpr_sp_data, stc_pr_data,
                                       zn_dmpr_data, low_dx_cond, high_dx_cond,
                                       dx_result, validate))
        dx_result = (
            self.sat_dx.sat_rcx(cur_time, satemp_data, sat_stpt_data, rht_data,
                                zn_dmpr_data, dx_result, validate))
        return dx_result
