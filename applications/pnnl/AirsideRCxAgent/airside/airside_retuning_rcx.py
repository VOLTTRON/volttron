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
import re
import math
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
# from openeis.applications import (DrivenApplicationBaseClass,
#                                   OutputDescriptor,
#                                   ConfigDescriptor,
#                                   InputDescriptor,
#                                   Results,
#                                   Descriptor,
#                                   reports)

DUCT_STC_RCx = 'Duct Static Pressure Control Loop Dx'
DUCT_STC_RCx1 = 'Low Duct Static Pressure Dx'
DUCT_STC_RCx2 = 'High Duct Static Pressure Dx'
DUCT_STC_RCx3 = 'No Static Pressure Reset Dx'
SA_TEMP_RCx = 'Supply-air Temperature Control Loop Dx'
SA_TEMP_RCx1 = 'Low Supply-air Temperature Dx'
SA_TEMP_RCx2 = 'High Supply-air Temperature Dx'
SA_TEMP_RCx3 = 'No Supply-air Temperature Reset Dx'
SCHED_RCx = 'Operational Schedule Dx'

CORRECT_STC_PR = 'suggested duct static pressure setpoint'
CORRECT_SAT = 'Suggested SAT setpoint'

dx = '/diagnostic message'


class Application(AbstractDrivenAgent):
    '''
    Air-side HVAC Auto-Retuning Diagnostics
    for AHUs.
    '''
    fan_speedcmd_priority = ''
    duct_stp_stpt_priority = ''
    ahu_ccoil_priority = ''
    sat_stpt_priority = ''

    def __init__(
            self, no_required_data=20, data_window=30, warm_up_time=30,
            duct_stc_retuning=0.15, max_duct_stp_stpt=2.5,
            high_supply_fan_threshold=100.0, zone_high_damper_threshold=90.0,
            zone_low_damper_threshold=10.0, min_duct_stp_stpt=0.5,
            hdzone_damper_threshold=30.0, low_supply_fan_threshold=20.0,
            setpoint_allowable_deviation=10.0, stpr_reset_threshold=0.25,

            percent_reheat_threshold=25.0, rht_on_threshold=10.0,
            sat_reset_threshold=5.0, sat_high_damper_threshold=80.0,
            percent_damper_threshold=50.0, minimum_sat_stpt=50.0,
            sat_retuning=1.0, reheat_valve_threshold=50.0,
            maximum_sat_stpt=75.0,

            unocc_time_threshold=30.0, unocc_stp_threshold=0.2,
            monday_sch='6:30;18:30', tuesday_sch='6:30;18:30',
            wednesday_sch='6:30;18:30', thursday_sch='6:30;18:30',
            friday_sch='6:30;18:30', saturday_sch='0:00;0:00',
            sunday_sch='0:00;0:00', **kwargs):
        # super().__init__(*args, **kwargs)
        Application.pre_requiste_messages = []
        Application.pre_msg_time = []

        # Pre-requisite messages
        self.pre_msg0 = ('Fan Status is not available, '
                         'could not verify system is ON.')
        self.pre_msg1 = ('Supply fan is off, current data will '
                         'not be used for diagnostics.')
        self.pre_msg2 = ('Missing required data: duct static pressure.')
        self.pre_msg3 = ('Missing required data:  '
                         'duct static pressure set point')
        self.pre_msg4 = ('Missing required data:  '
                         'terminal-box damper-position (all zones).')
        self.pre_msg5 = ('Missing required data for diagnostic: SAT.')
        self.pre_msg6 = ('Missing required data: '
                         'terminal-box reheat-valve-positions (all zones).')
        self.pre_msg7 = ('Missing required data: SAT set point.')

        # Point names (Configurable)
        def get_or_none(name):
            value = kwargs.get(name, None)
            if value:
                value = value.lower()
            return value

        Application.analysis = kwargs['device']['analysis_name']
        self.fan_status_name = kwargs['fan_status']
        self.duct_stp_stpt_name = kwargs['duct_stp_stpt']
        self.duct_stp_name = kwargs['duct_stp']
        self.sa_temp_name = kwargs['sa_temp']
        self.sat_stpt_name = kwargs['sat_stpt']
        self.fan_speedcmd_name = get_or_none('fan_speedcmd')
        Application.sat_stpt_cname = self.sat_stpt_name
        Application.duct_stp_stpt_cname = self.duct_stp_stpt_name

        # Optional points
        self.override_state = 'AUTO'
        self.fan_speedcmd_priority = get_or_none('fan_speedcmd_priority')
        self.duct_stp_stpt_priority = get_or_none('duct_stp_stpt_priority')
        self.ahu_ccoil_priority = get_or_none('ahu_ccoil_priority')
        self.sat_stpt_priority = get_or_none('sat_stpt_priority')

        # Zone Parameters
        self.zone_damper_name = get_or_none('zone_damper')
        self.zone_reheat_name = get_or_none('zone_reheat')

        # Application thresholds (Configurable)
        self.data_window = float(data_window)
        no_required_data = int(no_required_data)
        self.low_supply_fan_threshold = float(low_supply_fan_threshold)
        self.high_supply_fan_threshold = float(high_supply_fan_threshold)
        self.warm_up_flag = None
        self.warm_up_time = int(warm_up_time)
        self.warm_up_start = None
        auto_correctflag = True
        self.static_dx = DuctStaticRcx(data_window, no_required_data,
                                       auto_correctflag,
                                       setpoint_allowable_deviation,
                                       max_duct_stp_stpt,
                                       duct_stc_retuning,
                                       zone_high_damper_threshold,
                                       zone_low_damper_threshold,
                                       hdzone_damper_threshold,
                                       min_duct_stp_stpt)
        self.sat_dx = SupplyTempRcx(data_window, no_required_data,
                                    auto_correctflag,
                                    setpoint_allowable_deviation,
                                    rht_on_threshold,
                                    sat_high_damper_threshold,
                                    percent_damper_threshold,
                                    percent_reheat_threshold,
                                    minimum_sat_stpt, sat_retuning,
                                    reheat_valve_threshold,
                                    maximum_sat_stpt)
        self.sched_occ_dx = SchedResetRcx(unocc_time_threshold,
                                          unocc_stp_threshold,
                                          monday_sch, tuesday_sch,
                                          wednesday_sch, thursday_sch,
                                          friday_sch, saturday_sch,
                                          sunday_sch, data_window,
                                          no_required_data,
                                          stpr_reset_threshold,
                                          sat_reset_threshold)

#     OpenEIS METHODS
#     @classmethod
#     def get_config_parameters(cls):
#         '''
#         Generate required configuration
#         parameters with description for user
#         '''
#         dgr_sym = u'\N{DEGREE SIGN}'
#         return {
#             'data_window':
#             ConfigDescriptor(int,
#                              'Minimum Elapsed time for '
#                              'analysis (minutes)',
#                              value_default=15),
#             'no_required_data':
#             ConfigDescriptor(int,
#                              'Number of required data measurements to '
#                              'perform diagnostic',
#                              value_default=10),
#             'warm_up_time':
#             ConfigDescriptor(int,
#                              'When the system starts this much '
#                              'time will be allowed to elapse before adding '
#                              'using data for analysis (minutes)',
#                              value_default=30),
#             'zone_high_damper_threshold':
#             ConfigDescriptor(float,
#                              ('Zone high damper threshold '
#                               'used for detection of duct static '
#                               'pressure problems (%)'),
#                              value_default=90.0),
#             'zone_low_damper_threshold':
#             ConfigDescriptor(float,
#                              ('Zone low damper threshold '
#                               'used for detection of duct static '
#                               'pressure problems (%)'),
#                              value_default=10.0),
#             'max_duct_stp_stpt':
#             ConfigDescriptor(float,
#                              'Maximum duct static pressure set point '
#                              'allowed, when auto-correction is '
#                              'enabled, i.e., the set point chosen by the '
#                              'diagnostic will never exceed this value '
#                              '(inch w.g.)', value_default=2.5),
#             'duct_stc_retuning':
#             ConfigDescriptor(float,
#                              ('Increment/decrement of static pressure '
#                               'set point during auto-correction '
#                               '(inch w.g.)'),
#                              value_default=0.15),
#             'min_duct_stp_stpt':
#             ConfigDescriptor(float,
#                              'Minimum duct static pressure set point '
#                              'allowed, when auto-correction is '
#                              'enabled, i.e., the set point chosen by the '
#                              'diagnostic will never exceed this value '
#                              '(inch w.g.)', value_default=0.25),
#             'hdzone_damper_threshold':
#             ConfigDescriptor(float,
#                              'Threshold for zone damper. If the '
#                              'average value of the zone dampers is less '
#                              'than this threshold the fan is '
#                              'supplying too much air (%)',
#                              value_default=30.0),
#             'low_supply_fan_threshold':
#             ConfigDescriptor(float,
#                              'Value above which the supply fan will be '
#                              'considered at its minimum speed (%)',
#                              value_default=20.0),
#             'high_supply_fan_threshold':
#             ConfigDescriptor(float,
#                              ('Value above which the supply fan will '
#                               'be considered running at its maximum speed. '
#                               'If fan is running at its '
#                               'maximum speed (%)'),
#                              value_default=95.0),
#             'setpoint_allowable_deviation':
#             ConfigDescriptor(float,
#                              'Allowable deviation from set points '
#                              'before a fault message is generated '
#                              '(%)', value_default=10.0),
#             'stpr_reset_threshold':
#             ConfigDescriptor(float,
#                              ('Required difference between minimum and '
#                               'maximum duct static pressure set point '
#                               'detecting a duct static pressure '
#                               'set point reset (inch w.g.)'),
#                              value_default=0.25),
#             'reheat_valve_threshold':
#             ConfigDescriptor(float,
#                              'Zone re-heat valve threshold for SAT '
#                              'RCx, compared to average zone '
#                              're-heat valve (%)',
#                              value_default=50.0),
#             'percent_reheat_threshold':
#             ConfigDescriptor(float,
#                              ('Threshold for average percent of zones '
#                               'where terminal box re-heat is ON (%)'),
#                              value_default=25.0),
#             'maximum_sat_stpt':
#             ConfigDescriptor(float,
#                              'Maximum SAT set point allowed when '
#                              'auto-correction  is enabled, '
#                              'i.e., the set point chosen by the '
#                              'diagnostic will never exceed '
#                              'this value ({drg}F)'
#                              .format(drg=dgr_sym),
#                              value_default=75.0),
#             'rht_on_threshold':
#             ConfigDescriptor(float,
#                              'Value above which zone re-heat is '
#                              'considered ON (%)',
#                              value_default=10.0),
#             'sat_retuning':
#             ConfigDescriptor(float,
#                              'Decrement of supply-air temperature set '
#                              'point during auto-correction ({drg}F)'
#                              .format(drg=dgr_sym),
#                              value_default=1.0),
#             'sat_high_damper_threshold':
#             ConfigDescriptor(float,
#                              'High zone damper threshold for '
#                              'high supply-air temperature '
#                              'auto-correct RCx (%)',
#                              value_default=30),
#             'percent_damper_threshold':
#             ConfigDescriptor(float,
#                              'Threshold for the average % of zone '
#                              'dampers above high damper threshold '
#                              '(%)',
#                              value_default=50.0),
#             'minimum_sat_stpt':
#             ConfigDescriptor(float,
#                              'Maximum supply-air temperature '
#                              'set point allowed, when auto-correction '
#                              'is enabled, i.e., '
#                              'the set point chosen by the '
#                              'diagnostic will never exceed this value '
#                              '({drg}F)'.format(drg=dgr_sym),
#                              value_default=50.0),
#             'sat_reset_threshold':
#             ConfigDescriptor(float,
#                              'Threshold difference required '
#                              'to detect a supply-air temperature '
#                              'set point reset ({drg}F)'.format(drg=dgr_sym),
#                              value_default=3.0),
#
#             'unocc_time_threshold':
#             ConfigDescriptor(float,
#                              'Time threshold used for AHU schedule Dx. '
#                              '(%)', value_default=30.0),
#             'unocc_stp_threshold':
#             ConfigDescriptor(float,
#                              'AHU off static pressure dead-band '
#                              'Detects whether the duct static '
#                              'pressure exceeds this '
#                              'value during non-working scheduled '
#                              'hours (inch w.g.)',
#                              value_default=0.2),
#             'monday_sch':
#             ConfigDescriptor(str,
#                              'Thursday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational)',
#                              value_default='6:30;18:30'),
#             'tuesday_sch':
#             ConfigDescriptor(str,
#                              'Tuesday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational',
#                              value_default='6:30;18:30'),
#             'wednesday_sch':
#             ConfigDescriptor(str,
#                              'Wednesday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational',
#                              value_default='6:30;18:30'),
#             'thursday_sch':
#             ConfigDescriptor(str,
#                              'Thursday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational',
#                              value_default='6:30;18:30'),
#             'friday_sch':
#             ConfigDescriptor(str,
#                              'Friday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational',
#                              value_default='6:30;18:30'),
#             'saturday_sch':
#             ConfigDescriptor(str,
#                              'Saturday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational (unoccupied)',
#                              value_default='0:00;0:00'),
#             'sunday_sch':
#             ConfigDescriptor(str,
#                              'Sunday AHU occupied schedule, '
#                              'Used to detect the '
#                              'time when the supply fan should '
#                              'be operational (unoccupied)',
#                              value_default='0:00;0:00')
#             }
#
#     @classmethod
#     def get_self_descriptor(cls):
#         name = 'Auto-RCx for Air Handling HVAC Systems'
#         desc = 'Automated Retro-commisioning for AHUs'
#         return Descriptor(name=name, description=desc)
#
#     @classmethod
#     def required_input(cls):
#         '''
#         Generate required inputs with description for
#         user.
#         '''
#         return {
#             cls.fan_status_name:
#             InputDescriptor('SupplyFanStatus',
#                             'AHU Supply fan status', count_min=1),
#             cls.fan_speedcmd_name:
#             InputDescriptor('SupplyFanSpeed',
#                             'AHU supply fan speed', count_min=0),
#             cls.zone_reheat_name:
#             InputDescriptor('TerminalBoxReheatValvePosition',
#                             'All terminal-box re-heat valve commands',
#                             count_min=1),
#             cls.zone_damper_name:
#             InputDescriptor('TerminalBoxDamperCommand',
#                             'All terminal-box damper commands', count_min=1),
#             cls.duct_stp_name:
#             InputDescriptor('DuctStaticPressure', 'AHU duct static pressure',
#                             count_min=1),
#             cls.duct_stp_stpt_name:
#             InputDescriptor('DuctStaticPressureSetPoint',
#                             'Duct static pressure set point',
#                             count_min=1),
#             cls.sa_temp_name:
#             InputDescriptor('DischargeAirTemperature', 'AHU supply-air '
#                             '(discharge-air) temperature', count_min=1),
#             cls.sat_stpt_name:
#             InputDescriptor('DischargeAirTemperatureSetPoint',
#                             'Supply-air temperature set-point', count_min=1)
#             }
#
#     def reports(self):
#         '''Called by UI to assemble information for creation of the
#         diagnostic visualization.
#         '''
#         report = reports.Report('Retuning Report')
#         report.add_element(reports.RetroCommissioningOAED(
#             table_name='Airside_RCx'))
#         report.add_element(reports.RetroCommissioningAFDD(
#             table_name='Airside_RCx'))
#         return [report]
#
#     @classmethod
#     def output_format(cls, input_object):
#         '''Describes how the output or results will be formatted
#         Output will have the date-time, error-message, color-code,
#         and energy impact.
#         '''
#         result = super().output_format(input_object)
#         topics = input_object.get_topics()
#         diagnostic_topic = topics[cls.fan_status_name][0]
#         diagnostic_topic_parts = diagnostic_topic.split('/')
#         output_topic_base = diagnostic_topic_parts[:-1]
#         datetime_topic = '/'.join(output_topic_base + ['Airside_RCx',
#                                                        'date'])
#         message_topic = '/'.join(output_topic_base + ['Airside_RCx',
#                                                       'message'])
#         diagnostic_name = '/'.join(output_topic_base + ['Airside_RCx',
#                                                         ' diagnostic'])
#         energy_impact = '/'.join(output_topic_base + ['Airside_RCx',
#                                                       'energy_impact'])
#         color_code = '/'.join(output_topic_base + ['Airside_RCx',
#                                                    'color_code'])
#
#         output_needs = {
#             'Airside_RCx': {
#                 'datetime': OutputDescriptor('string', datetime_topic),
#                 'diagnostic_name': OutputDescriptor('string',
#                                                       diagnostic_name),
#                 'diagnostic_message': OutputDescriptor('string',
#                                                        message_topic),
#                 'energy_impact': OutputDescriptor('float', energy_impact),
#                 'color_code': OutputDescriptor('string', color_code)
#                 }
#             }
#         result.update(output_needs)
#         return result

    def run(self, current_time, points):
        '''Check application pre-quisites and assemble analysis data set.
        Receives mapped data from the DrivenBaseClass. Filters non-relevent
        data and assembles analysis data set for diagnostics.
        '''
        device_dict = {}
        diagnostic_result = Results()
#         topics = self.inp.get_topics()
#         diagnostic_topic = topics[self.fan_status_name][0]
#         current_time = self.inp.localize_sensor_time(diagnostic_topic,
#                                                          current_time)
        for key, value in points.items():
            device_dict[key.lower()] = value
        print device_dict
        supply_fan_off = False
        fan_stat_data = []
        fan_stat_check = False
        for key, value in device_dict.items():
            if key.startswith(self.fan_status_name) and value is not None:
                fan_stat_check = True
                fan_stat_data.append(value)
                if not value:
                    self.warm_up_flag = True
                    Application.pre_requiste_messages.append(self.pre_msg1)
                    diagnostic_result = self.pre_message(diagnostic_result,
                                                         current_time)
                    supply_fan_off = True
        if not fan_stat_check and self.fan_speedcmd_name is not None:
            for key, value in device_dict.items():
                if (key.startswith(self.fan_speedcmd_name) and
                        value is not None):
                    fan_stat_check = True
                    if value < self.low_supply_fan_threshold:
                        self.warm_up_flag = True
                        Application.pre_requiste_messages.append(self.pre_msg1)
                        diagnostic_result = self.pre_message(diagnostic_result,
                                                             current_time)
                        return diagnostic_result
                    fan_stat_data.append(1)
                    supply_fan_off = False
        if not fan_stat_check:
            Application.pre_requiste_messages.append(self.pre_msg0)
            diagnostic_result = self.pre_message(diagnostic_result,
                                                 current_time)
            return diagnostic_result
        low_dx_condition = False
        high_dx_condition = False
        static_override_check = False
        sat_override_check = False

        for key, value in device_dict.items():
            if (self.fan_speedcmd_name is not None and
                    self.fan_speedcmd_name in key):
                if (value is not None and
                        value > self.high_supply_fan_threshold):
                    low_dx_condition = True
                elif (value is not None and
                      value < self.low_supply_fan_threshold):
                    high_dx_condition = True
            if (self.fan_speedcmd_priority and
                    self.fan_speedcmd_priority in key):
                if value == self.override_state:
                    static_override_check = True
            if (self.duct_stp_stpt_priority and
                    self.duct_stp_stpt_priority in key):
                if value == self.override_state:
                    static_override_check = True
            if self.ahu_ccoil_priority and self.ahu_ccoil_priority in key:
                if value == self.override_state:
                    sat_override_check = True
            if self.sat_stpt_priority and self.sat_stpt_priority in key:
                if value == self.override_state:
                    sat_override_check = True
        stc_pr_data = []
        stc_pr_sp_data = []
        zone_damper_data = []
        satemp_data = []
        rht_data = []
        sat_stpt_data = []
        for key, value in device_dict.items():
            if (key.startswith(self.duct_stp_stpt_name) and
                    value is not None):
                stc_pr_sp_data.append(value)
            elif (key.startswith(self.duct_stp_name) and
                  value is not None):
                stc_pr_data.append(value)
            elif (key.startswith(self.zone_damper_name) and
                  value is not None):
                zone_damper_data.append(value)
            elif (key.startswith(self.sat_stpt_name) and
                  value is not None):
                sat_stpt_data.append(value)
            elif (key.startswith(self.sa_temp_name) and
                  value is not None):
                satemp_data.append(value)
            elif (key.startswith(self.zone_reheat_name) and
                  value is not None):
                rht_data.append(value)
        if not stc_pr_data:
            Application.pre_requiste_messages.append(self.pre_msg2)
        if not stc_pr_sp_data:
            Application.pre_requiste_messages.append(self.pre_msg3)
        if not zone_damper_data:
            Application.pre_requiste_messages.append(self.pre_msg4)
        if not (stc_pr_data and zone_damper_data and stc_pr_sp_data):
            return diagnostic_result
        if not satemp_data:
            Application.pre_requiste_messages.append(self.pre_msg5)
        if not rht_data:
            Application.pre_requiste_messages.append(self.pre_msg6)
        if not sat_stpt_data:
            Application.pre_requiste_messages.append(self.pre_msg7)
        if not satemp_data or not rht_data or not sat_stpt_data:
            diagnostic_result = self.pre_message(diagnostic_result,
                                                 current_time)
            return diagnostic_result
        diagnostic_result = self.sched_occ_dx.sched_rcx_alg(
            current_time, stc_pr_data, stc_pr_sp_data,
            sat_stpt_data, fan_stat_data, diagnostic_result)
        if supply_fan_off:
            return diagnostic_result
        if self.warm_up_flag:
            self.warm_up_flag = False
            self.warm_up_start = current_time
            diagnostic_result = self.pre_message(diagnostic_result,
                                                 current_time)
            return diagnostic_result
        time_check = td(minutes=self.warm_up_time)
        if (self.warm_up_start is not None and
                (current_time - self.warm_up_start) < time_check):
            diagnostic_result = self.pre_message(diagnostic_result,
                                                 current_time)
            return diagnostic_result
        diagnostic_result = self.static_dx.duct_static(
            current_time, stc_pr_sp_data, stc_pr_data, zone_damper_data,
            static_override_check, low_dx_condition,
            high_dx_condition, diagnostic_result)
        diagnostic_result = self.sat_dx.sat_rcx(
            current_time, satemp_data, sat_stpt_data, rht_data,
            zone_damper_data, diagnostic_result, sat_override_check)

        return diagnostic_result

    def pre_message(self, result, current_time):
        '''Add meaningful output based to results table if analysis
        cannot be run.
        '''
        Application.pre_msg_time.append(current_time)
        pre_check = ((Application.pre_msg_time[-1] -
                      Application.pre_msg_time[0])
                     .total_seconds()/60)
        pre_check = pre_check if pre_check > 0.0 else 1.0
        if pre_check >= self.data_window:
            msg_lst = [self.pre_msg0, self.pre_msg1, self.pre_msg2,
                       self.pre_msg3, self.pre_msg4, self.pre_msg5,
                       self.pre_msg6, self.pre_msg7]
            for item in msg_lst:
                if (Application.pre_requiste_messages.count(item) >
                        (0.25) * len(Application.pre_msg_time)):
                    result.log(item, logging.DEBUG)
            Application.pre_requiste_messages = []
            Application.pre_msg_time = []
        return result


class DuctStaticRcx(object):
    '''Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    duct static pressure problems.
    '''
    def __init__(self, data_window, no_required_data, auto_correctflag,
                 setpoint_allowable_deviation,
                 max_duct_stp_stpt, duct_stc_retuning,
                 zone_high_damper_threshold,
                 zone_low_damper_threshold,
                 hdzone_damper_threshold, min_duct_stp_stpt):
        # Initialize data lists
        self.zone_damper_values = []
        self.duct_stp_stpt_values = []
        self.duct_stp_values = []
        self.timestamp = []
        # Initialize configurable thresholds
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.setpoint_allowable_deviation = float(setpoint_allowable_deviation)
        self.max_duct_stp_stpt = float(max_duct_stp_stpt)
        self.duct_stc_retuning = float(duct_stc_retuning)
        self.zone_high_damper_threshold = float(zone_high_damper_threshold)
        self.zone_low_damper_threshold = float(zone_low_damper_threshold)
        self.setpoint_allowable_deviation = float(setpoint_allowable_deviation)
        self.auto_correctflag = auto_correctflag
        self.min_duct_stp_stpt = float(min_duct_stp_stpt)
        self.hdzone_damper_threshold = float(hdzone_damper_threshold)

    def duct_static(self, current_time, stc_pr_sp_data, stc_pr_data,
                    zone_dmpr_data, static_override_check, low_dx_condition,
                    high_dx_condition, diagnostic_result):
        '''Check duct static pressure RCx pre-requisites
        and assemble the duct static pressure analysis data set.
        '''
        if low_dx_condition:
            diagnostic_result.log(('The supply fan is running at '
                                   'nearly 100% of full speed, data '
                                   'corresponding to {timestamp} will not be '
                                   'used for diagnostic'.
                                   format(timestamp=str(current_time)),
                                   logging.DEBUG))
            return diagnostic_result
        if high_dx_condition:
            diagnostic_result.log(('The supply fan is running at '
                                   ' the minimum speed, data corresponding '
                                   'to {timestamp} will not be used for '
                                   'diagnostic'.
                                   format(timestamp=str(current_time)),
                                   logging.DEBUG))
            return diagnostic_result
        self.duct_stp_values.append(sum(stc_pr_data)/len(stc_pr_data))
        self.zone_damper_values.append(sum(zone_dmpr_data)/len(zone_dmpr_data))
        self.timestamp.append(current_time)

        self.duct_stp_stpt_values.append(
            sum(stc_pr_sp_data) / len(stc_pr_sp_data))
        elapsed_time = ((self.timestamp[-1] - self.timestamp[0])
                        .total_seconds()/60)
        elapsed_time = elapsed_time if elapsed_time > 0.0 else 1.0
        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            avg_duct_stpr_stpt = (sum(
                self.duct_stp_stpt_values) / len(self.duct_stp_stpt_values))

            if avg_duct_stpr_stpt > 0 and avg_duct_stpr_stpt < 10.0:
                set_point_tracking = [abs(x - y) for
                                      x, y in zip(self.duct_stp_values,
                                                  self.duct_stp_stpt_values)]

                set_point_tracking = (sum(set_point_tracking) /
                                      (len(set_point_tracking) *
                                       avg_duct_stpr_stpt)*100)
                if set_point_tracking > self.setpoint_allowable_deviation:
                    msg = ('The duct static pressure is deviating from its '
                           'set point significantly.')
                    # color_code = 'RED'
                    # energy_impact = None
                    dx_msg = 1.1
                    dx_table = {
                        # 'datetime': str(self.timestamp[-1]),
                        # 'diagnostic_name': DUCT_STC_RCx,
                        # 'diagnostic_message': msg,
                        # 'energy_impact': energy_impact,
                        # 'color_code': color_code
                        DUCT_STC_RCx + dx: dx_msg
                    }

                else:
                    msg = 'No problem detected.'
                    # color_code = 'GREEN'
                    # energy_impact = None
                    dx_msg = 0.0
                    dx_table = {
                        # 'datetime': str(self.timestamp[-1]),
                        # 'diagnostic_name': DUCT_STC_RCx,
                        # 'diagnostic_message': msg,
                        # 'energy_impact': energy_impact,
                        # 'color_code': color_code
                        DUCT_STC_RCx + dx: dx_msg
                    }
                diagnostic_result.insert_table_row(Application.analysis,
                                                   dx_table)
                diagnostic_result.log(msg, logging.INFO)
            if elapsed_time > td(minutes=75):
                diagnostic_result.insert_table_row(Application.analysis,
                                                   {DUCT_STC_RCx1 + dx: 16.2})
                diagnostic_result.insert_table_row(Application.analysis,
                                                   {DUCT_STC_RCx2 + dx: 26.2})
                return diagnostic_result
            diagnostic_result = self.low_ductstatic_pr(diagnostic_result,
                                                       static_override_check)
            diagnostic_result = self.high_ductstatic_pr(diagnostic_result,
                                                        static_override_check)
        return diagnostic_result

    def low_ductstatic_pr(self, result, static_override_check):
        '''Diagnostic to identify and correct low duct static pressure
        (correction by modifying duct static pressure set point).
        '''
        zone_damper_temp = self.zone_damper_values
        zone_damper_temp.sort(reverse=False)
        zone_damper_lowtemp = zone_damper_temp[
            :int(math.ceil(len(self.zone_damper_values)*0.5))
            if len(self.zone_damper_values) != 1 else 1]
        zone_damper_lowavg = (
            sum(zone_damper_lowtemp) / len(zone_damper_lowtemp))

        zone_damper_hightemp = (
            zone_damper_temp[
                int(math.ceil(len(self.zone_damper_values)*0.5)) - 1
                if len(self.zone_damper_values) != 1 else 0:])

        zone_damper_highavg = (
            sum(zone_damper_hightemp) / len(zone_damper_hightemp))
        # energy_impact = None
        avg_duct_stpr_stpt = None
        if self.duct_stp_stpt_values:
            avg_duct_stpr_stpt = (sum(self.duct_stp_stpt_values) /
                                  len(self.duct_stp_stpt_values))

        if (zone_damper_highavg > self.zone_high_damper_threshold and
                zone_damper_lowavg > self.zone_low_damper_threshold):
            # color_code = 'RED'
            if (avg_duct_stpr_stpt is not None and
                    not static_override_check):
                if self.auto_correctflag:
                    duct_stpr_stpt = (avg_duct_stpr_stpt +
                                      self.duct_stc_retuning)
                    if duct_stpr_stpt <= self.max_duct_stp_stpt:
                        result.command(
                            Application.duct_stp_stpt_cname, duct_stpr_stpt)
                        duct_stpr_stpt = '%s' % float('%.2g' % duct_stpr_stpt)
                        duct_stpr_stpt = str(duct_stpr_stpt)
                        duct_stpr_stpt = ''.join([duct_stpr_stpt,
                                                  ' in. w.g.'])
                        msg = ('The duct static pressure was detected to be '
                               'too low. The duct static pressure has been '
                               'increased to: {val}'
                               .format(val=duct_stpr_stpt))
                        dx_msg = 11.1
                    else:
                        result.command(Application.duct_stp_stpt_cname,
                                       self.max_duct_stp_stpt)
                        duct_stpr_stpt = (
                            '%s' % float('%.2g' % self.max_duct_stp_stpt)
                        )
                        duct_stpr_stpt = str(duct_stpr_stpt)
                        duct_stpr_stpt = ''.join([duct_stpr_stpt,
                                                  ' in. w.g.'])
                        msg = ('The duct static pressure set point is at the '
                               'maximum value configured by the building '
                               'operator: {val})'.format(val=duct_stpr_stpt))
                        dx_msg = 12.1
                else:
                    msg = ('The duct static pressure set point was detected '
                           'to be too low but auto-correction is not enabled.')
                    dx_msg = 13.1

            elif not static_override_check:
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
            # color_code = 'GREEN'
            dx_msg = 10.0
        dx_table = {
            # 'datetime': str(self.timestamp[-1]),
            # 'diagnostic_name': DUCT_STC_RCx1,
            # 'diagnostic_message': msg,
            # 'energy_impact': energy_impact,
            # 'color_code': color_code
            DUCT_STC_RCx1 + dx: dx_msg
        }
        result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def high_ductstatic_pr(self, result, static_override_check):
        '''Diagnostic to identify and correct high duct static pressure
        (correction by modifying duct static pressure set point)
        '''
        zone_damper_temp = self.zone_damper_values
        zone_damper_temp.sort(reverse=True)
        zone_damper_temp = zone_damper_temp[
            :int(math.ceil(len(self.zone_damper_values)*0.5))
            if len(self.zone_damper_values) != 1 else 1]
        avg_zone_damper = sum(zone_damper_temp) / len(zone_damper_temp)
        # energy_impact = None
        avg_duct_stpr_stpt = None
        if self.duct_stp_stpt_values:
            avg_duct_stpr_stpt = sum(
                self.duct_stp_stpt_values) / len(self.duct_stp_stpt_values)
        if avg_zone_damper <= self.hdzone_damper_threshold:
            # color_code = 'RED'
            if avg_duct_stpr_stpt is not None and not static_override_check:
                if self.auto_correctflag:
                    duct_stpr_stpt = (avg_duct_stpr_stpt -
                                      self.duct_stc_retuning)
                    if duct_stpr_stpt >= self.min_duct_stp_stpt:
                        result.command(
                            Application.duct_stp_stpt_cname, duct_stpr_stpt)
                        duct_stpr_stpt = '%s' % float('%.2g' % duct_stpr_stpt)
                        duct_stpr_stpt = str(duct_stpr_stpt)
                        duct_stpr_stpt = ''.join([duct_stpr_stpt,
                                                  ' in. w.g.'])
                        msg = ('The duct static pressure was detected to be '
                               'too high. The duct static pressure set point '
                               'has been reduced to: {val}'
                               .format(val=duct_stpr_stpt))
                        dx_msg = 21.1
                    else:
                        result.command(
                            Application.duct_stp_stpt_cname,
                            self.min_duct_stp_stpt)
                        duct_stpr_stpt = (
                            '%s' % float('%.2g' % self.min_duct_stp_stpt)
                        )
                        duct_stpr_stpt = str(duct_stpr_stpt)
                        duct_stpr_stpt = ''.join([duct_stpr_stpt,
                                                  ' in. w.g.'])
                        msg = ('The duct static pressure set point is at the '
                               'minimum value configured by the building '
                               'operator: {val})'.format(val=duct_stpr_stpt))
                        dx_msg = 22.1
                else:
                    msg = ('Duct static pressure set point was detected to be '
                           'too high but auto-correction is not enabled.')
                    dx_msg = 23.1
            elif not static_override_check:
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
            # color_code = 'GREEN'

        dx_table = {
            # 'datetime': str(self.timestamp[-1]),
            # 'diagnostic_name': DUCT_STC_RCx2,
            # 'diagnostic_message': msg,
            # 'energy_impact': energy_impact,
            # 'color_code': color_code
            DUCT_STC_RCx2 + dx: dx_msg
        }
        result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        self.duct_stp_stpt_values = []
        self.duct_stp_values = []
        self.zone_damper_values = []
        self.timestamp = []
        return result


class SupplyTempRcx(object):
    '''Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    supply-air temperature problems.
    '''
    def __init__(self, data_window, no_required_data,
                 auto_correctflag, setpoint_allowable_deviation,
                 rht_on_threshold, high_damper_threshold,
                 percent_damper_threshold, percent_reheat_threshold,
                 minimum_sat_stpt, sat_retuning,
                 reheat_valve_threshold, maximum_sat_stpt):

        self.timestamp = []
        self.sat_stpt_values = []
        self.sa_temp_values = []
        self.rht_values = []
        self.reheat = []
        self.percent_in_reheat = []
        self.percent_damper = []
        # Common RCx parameters
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.auto_correctflag = bool(auto_correctflag)
        self.setpoint_allowable_deviation = float(setpoint_allowable_deviation)
        self.rht_on_threshold = float(rht_on_threshold)
        self.percent_reheat_threshold = float(percent_reheat_threshold)
        self.dgr_sym = u'\N{DEGREE SIGN}'
        # Low SAT RCx thresholds
        self.reheat_valve_threshold = float(reheat_valve_threshold)
        self.maximum_sat_stpt = float(maximum_sat_stpt)
        # High SAT RCx thresholds
        self.high_damper_threshold = float(high_damper_threshold)
        self.percent_damper_threshold = float(percent_damper_threshold)
        self.minimum_sat_stpt = float(minimum_sat_stpt)
        self.sat_retuning = float(sat_retuning)

    def sat_rcx(self, current_time, satemp_data, sat_stpt_data,
                rht_data, zone_damper_data, diagnostic_result,
                sat_override_check):
        '''Check supply-air temperature RCx pre-requisites
        and assemble the supply-air temperature analysis data set.
        '''
        self.sa_temp_values.append(sum(satemp_data) / len(satemp_data))
        self.rht_values.append(sum(rht_data) / len(rht_data))
        self.sat_stpt_values.append(sum(sat_stpt_data) / len(sat_stpt_data))
        total_damper = 0
        count_damper = 0
        total_reheat = 0
        count_reheat = 0
        for value in rht_data:
            if value > self.rht_on_threshold:
                total_reheat += 1
            count_reheat += 1
        for value in zone_damper_data:
            if value > self.high_damper_threshold:
                total_damper += 1
            count_damper += 1

        self.percent_in_reheat.append(total_reheat/count_reheat)
        self.percent_damper.append(total_damper/count_damper)
        self.timestamp.append(current_time)
        elapsed_time = ((self.timestamp[-1] - self.timestamp[0])
                        .total_seconds()/60)
        elapsed_time = elapsed_time if elapsed_time > 0.0 else 1.0
        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            avg_sat_stpt = (sum(self.sat_stpt_values) /
                            len(self.sat_stpt_values))

            set_point_tracking = [abs(x - y) for x, y in
                                  zip(self.sat_stpt_values,
                                      self.sa_temp_values)]

            set_point_tracking = (sum(set_point_tracking) /
                                  len(set_point_tracking) *
                                  avg_sat_stpt) * 100

            if set_point_tracking > self.setpoint_allowable_deviation:
                msg = ('Supply-air temperature is deviating significantly '
                       'from the supply-air temperature set point.')
                # color_code = 'RED'
                # energy_impact = None
                dx_msg = 31.1
                dx_table = {
                    # 'datetime': str(self.timestamp[-1]),
                    # 'diagnostic_name': SA_TEMP_RCx,
                    # 'diagnostic_message': msg,
                    # 'energy_impact': energy_impact,
                    # 'color_code': color_code
                    SA_TEMP_RCx + dx: dx_msg
                }
            else:
                msg = 'No problem detected.'
                # color_code = 'GREEN'
                # energy_impact = None
                dx_msg = 30.0
                dx_table = {
                    # 'datetime': str(self.timestamp[-1]),
                    # 'diagnostic_name': SA_TEMP_RCx,
                    # 'diagnostic_message': msg,
                    # 'energy_impact': energy_impact,
                    # 'color_code': color_code
                    SA_TEMP_RCx + dx: dx_msg
                }
            diagnostic_result.insert_table_row(Application.analysis, dx_table)
            diagnostic_result.log(msg, logging.INFO)
            if elapsed_time > td(minutes=75):
                diagnostic_result.insert_table_row(Application.analysis,
                                                   {SA_TEMP_RCx1 + dx: 46.2})
                diagnostic_result.insert_table_row(Application.analysis,
                                                   {SA_TEMP_RCx2 + dx: 56.2})
                return diagnostic_result
            diagnostic_result = self.low_sat(diagnostic_result,
                                             avg_sat_stpt,
                                             sat_override_check)
            diagnostic_result = self.high_sat(diagnostic_result,
                                              avg_sat_stpt,
                                              sat_override_check)
            self.percent_in_reheat = []
            self.percent_damper = []
            self.rht_values = []
        return diagnostic_result

    def low_sat(self, result, avg_sat_stpt, sat_override_check):
        '''Diagnostic to identify and correct low supply-air temperature
        (correction by modifying SAT set point)
        '''
        avg_zones_reheat = \
            (sum(self.percent_in_reheat) / len(self.percent_in_reheat) * 100)
        reheat_coil_average = (sum(self.rht_values)) / (len(self.rht_values))
        # energy_impact = None
        if (reheat_coil_average > self.reheat_valve_threshold and
                avg_zones_reheat > self.percent_reheat_threshold):
            # color_code = 'RED'
            if (avg_sat_stpt is not None and
                    not sat_override_check):
                if self.auto_correctflag:

                    sat_stpt = avg_sat_stpt + self.sat_retuning
                    # Create diagnostic message for fault
                    # condition with auto-correction
                    if sat_stpt <= self.maximum_sat_stpt:
                        result.command(Application.sat_stpt_cname, sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % sat_stpt)
                        sat_stpt = str(sat_stpt)
                        msg = \
                            ('The SAT has been detected to be too low. '
                             'The SAT set point has been increased to: '
                             '{}{drg}F'.format(self.dgr_sym, sat_stpt))
                        dx_msg = 41.1
                    else:
                        # Create diagnostic message
                        # for fault condition where
                        # the maximum SAT has been reached
                        result.command(Application.sat_stpt_cname,
                                       self.maximum_sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % self.maximum_sat_stpt)
                        sat_stpt = str(sat_stpt)
                        msg = ('The SAT was detected to be too low. '
                               'Auto-correction has increased the SAT set '
                               'point to the maximum configured SAT set '
                               'point: {}{}F)'.format(self.dgr_sym, sat_stpt))
                        dx_msg = 42.1
                else:
                    # Create diagnostic message for fault
                    # condition without auto-correction
                    msg = ('The SAT has been detected to be too low but '
                           'auto-correction is not enabled.')
                    dx_msg = 43.1
            elif not sat_override_check:
                msg = 'The SAT has been detected to be too low.'
                dx_msg = 44.1
            else:
                msg = ('The SAT has been detected to be too low but '
                       'auto-correction cannot be performed because the SAT '
                       'set-point is in an override state.')
                dx_msg = 45.1
        else:
            msg = 'No problem detected'
            # color_code = 'GREEN'
            dx_msg = 40.0
        dx_table = {
            # 'datetime': str(self.timestamp[-1]),
            # 'diagnostic_name': SA_TEMP_RCx1,
            # 'diagnostic_message': msg,
            # 'energy_impact': energy_impact,
            # 'color_code': color_code
            SA_TEMP_RCx1 + dx: dx_msg
        }
        result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def high_sat(self, result, avg_sat_stpt, sat_override_check):
        '''Diagnostic to identify and correct high supply-air temperature
        (correction by modifying SAT set point)
        '''
        avg_zones_reheat = (sum(self.percent_in_reheat) /
                            len(self.percent_in_reheat) * 100)
        avg_zone_damper = (sum(self.percent_damper) /
                           len(self.percent_damper) * 100)
        # energy_impact = None
        if (avg_zone_damper > self.percent_damper_threshold and
                avg_zones_reheat < self.percent_reheat_threshold):
            # color_code = 'RED'
            if (avg_sat_stpt is not None and
                    not sat_override_check):
                if self.auto_correctflag:
                    sat_stpt = avg_sat_stpt - self.sat_retuning
                    # Create diagnostic message for fault condition
                    # with auto-correction
                    if sat_stpt >= self.minimum_sat_stpt:
                        result.command(Application.sat_stpt_cname, sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % sat_stpt)
                        sat_stpt = str(sat_stpt)
                        msg = ('The SAT has been detected to be too high. The '
                               'SAT set point has been increased to: '
                               '{}{}F'.format(self.dgr_sym, sat_stpt))
                        dx_msg = 51.1
                    else:
                        # Create diagnostic message for fault condition
                        # where the maximum SAT has been reached
                        result.command(
                            Application.sat_stpt_cname, self.minimum_sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % self.minimum_sat_stpt)
                        sat_stpt = str(sat_stpt)
                        msg = ('The SAT was detected to be too high, '
                               'auto-correction has increased the SAT to the '
                               'minimum configured SAT: {}{}F'
                               .format(self.dgr_sym, sat_stpt))
                        dx_msg = 52.1
                else:
                    # Create diagnostic message for fault condition
                    # without auto-correction
                    msg = ('The SAT has been detected to be too high but '
                           'auto-correction is not enabled.')
                    dx_msg = 53.1
            elif not sat_override_check:
                msg = 'The SAT has been detected to be too high.'
                dx_msg = 54.1
            else:
                msg = ('The SAT has been detected to be too high but '
                       'auto-correction cannot be performed because the '
                       'SAT set point is in an override state.')
                dx_msg = 55.1
        else:
            msg = 'No problem detected.'
            # color_code = 'GREEN'
            dx_msg = 50.0
        dx_table = {
            # 'datetime': str(self.timestamp[-1]),
            # 'diagnostic_name': SA_TEMP_RCx2,
            # 'diagnostic_message': msg,
            # 'energy_impact': energy_impact,
            # 'color_code': color_code
            SA_TEMP_RCx2 + dx: dx_msg
        }
        result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        self.sat_stpt_values = []
        self.sa_temp_values = []
        self.timestamp = []
        temp1 = []
        temp2 = []
        for message in range(0, len(Application.pre_requiste_messages) - 1):
            if SCHED_RCx in Application.pre_requiste_messages[message]:
                temp1.append(Application.pre_requiste_messages[message])
                temp2.append(Application.pre_msg_time[message])
        Application.pre_requiste_messages = temp1
        Application.pre_msg_time = temp2
        return result


class SchedResetRcx(object):
    '''Schedule, supply-air temperature, and duct static pressure auto-detect
    diagnostics for AHUs or RTUs.
    '''
    def __init__(self, unocc_time_threshold, unocc_stp_threshold,
                 monday_sch, tuesday_sch, wednesday_sch, thursday_sch,
                 friday_sch, saturday_sch, sunday_sch, data_window,
                 no_required_data, stpr_reset_threshold, sat_reset_threshold):

        self.active_sch = []
        self.fan_status_values = []
        self.schedule = {}
        self.duct_stp_values = []
        self.duct_stp_stpt_values = []
        self.sat_stpt_values = []
        self.timestamp = []
        self.sched_time = []
        self.dx_time = None
        self.monday_sch = re.sub('[:;]', ',', monday_sch)
        self.monday_sch = [int(item) for item in (x.strip()
                                                  for x in
                                                  self.monday_sch.split(','))]
        self.tuesday_sch = re.sub('[:;]', ',', tuesday_sch)
        self.tuesday_sch = [int(item) for item
                            in (x.strip() for x in
                                self.tuesday_sch.split(','))]
        self.wednesday_sch = re.sub('[:;]', ',', wednesday_sch)
        self.wednesday_sch = [int(item) for item
                              in(x.strip()for x in
                                 self.wednesday_sch.split(','))]
        self.thursday_sch = re.sub('[:;]', ',', thursday_sch)
        self.thursday_sch = [int(item) for item
                             in (x.strip() for x in
                                 self.thursday_sch.split(','))]
        self.friday_sch = re.sub('[:;]', ',', friday_sch)
        self.friday_sch = [int(item) for item
                           in (x.strip() for x in
                               self.friday_sch.split(','))]
        self.saturday_sch = re.sub('[:;]', ',', saturday_sch)
        self.saturday_sch = [int(item) for item
                             in (x.strip() for x in
                                 self.saturday_sch.split(','))]
        self.sunday_sch = re.sub('[:;]', ',', sunday_sch)
        self.sunday_sch = [int(item) for item
                           in (x.strip() for x in
                               self.sunday_sch.split(','))]
        self.schedule = {0: self.monday_sch, 1: self.tuesday_sch,
                         2: self.wednesday_sch, 3: self.thursday_sch,
                         4: self.friday_sch, 5: self.saturday_sch,
                         6: self.sunday_sch}
        self.pre_msg = ('Current time is in the scheduled hours '
                        'unit is operating correctly.')
        # Application thresholds (Configurable)
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.unocc_time_threshold = float(unocc_time_threshold)
        self.unocc_stp_threshold = float(unocc_stp_threshold)
        self.stpr_reset_threshold = float(stpr_reset_threshold)
        self.sat_reset_threshold = float(sat_reset_threshold)

    def sched_rcx_alg(self, current_time, stc_pr_data, stc_pr_sp_data,
                      sat_stpt_data, fan_stat_data, diagnostic_result):
        '''Check schedule status and unit operational status.'''
        def clear_old():
            '''Clear old data'''
            self.dx_time = None
            self.sat_stpt_values = []
            self.duct_stp_stpt_values = []
            self.duct_stp_values = []
            self.fan_status_values = []
            Application.pre_requiste_messages = []
            Application.pre_msg_time = []
            self.sched_time = []
            if duct_stp_stpt_values is not None:
                self.sat_stpt_values.append(sat_stpt_values)
                self.duct_stp_stpt_values.append(duct_stp_stpt_values)
            if fan_stat is not None:
                self.fan_status_values.append(fan_stat)
                self.duct_stp_values.append(duct_stp)
            self.timestamp = [self.timestamp[-1]]

        fan_stat = None
        duct_stp_stpt_values = None
        active_sch = self.schedule[current_time.weekday()]
        if((current_time.hour < active_sch[0] or
                (current_time.hour == active_sch[0] and
                 current_time.minute < active_sch[1])) or
           (current_time.hour > active_sch[2] or
            (current_time.hour == active_sch[2] and
             current_time.minute < active_sch[3]))):
            self.duct_stp_values.extend(stc_pr_data)
            self.fan_status_values.append(int(max(fan_stat_data)))
            fan_stat = self.fan_status_values[-1]
            duct_stp = self.duct_stp_values[-1]
            self.sched_time.append(current_time)
        else:
            if int(max(fan_stat_data)):
                self.duct_stp_stpt_values.append(sum(stc_pr_sp_data) /
                                                 len(stc_pr_sp_data))
                duct_stp_stpt_values = self.duct_stp_stpt_values[-1]
                self.sat_stpt_values.append(sum(sat_stpt_data) /
                                            len(sat_stpt_data))
                sat_stpt_values = self.sat_stpt_values[-1]
        run = False
        if self.timestamp and self.timestamp[-1].date() != current_time.date():
            self.dx_time = self.timestamp[-1].date()
            run = True
        self.timestamp.append(current_time)
        if run and len(self.timestamp) >= self.no_required_data:
            diagnostic_result = self.unocc_fan_operation(diagnostic_result)
            diagnostic_result = self.no_static_pr_reset(diagnostic_result)
            diagnostic_result = self.no_sat_sp_reset(diagnostic_result)
            clear_old()
        elif run:
            # msg = ('Inconclusive diagnostic, '
            # insufficient data to perform RCx.')
            # color_code = 'GREY'
            # energy_impact = None
            dx_msg = 61.2
            dx_table = {
                # 'datetime': self.dx_time,
                # 'diagnostic_name': SCHED_RCx,
                # 'diagnostic_message': msg,
                # 'energy_impact': energy_impact,
                # 'color_code': color_code
                SCHED_RCx + dx:  dx_msg
            }
            diagnostic_result.insert_table_row(Application.analysis, dx_table)
            clear_old()
        return diagnostic_result

    def unocc_fan_operation(self, result):
        '''If the AHU/RTU is operating during unoccupied periods inform the
        building operator.
        '''
        no_times_fan_status_on = [i for i in self.fan_status_values
                                  if int(i) == 1]
        if self.fan_status_values:
            per_times_fan_status_on = (len(no_times_fan_status_on) /
                                       len(self.fan_status_values)) * 100.0
        else:
            per_times_fan_status_on = 0
        if self.duct_stp_values:
            avg_duct_stpr = (sum(self.duct_stp_values) /
                             len(self.duct_stp_values))
        else:
            avg_duct_stpr = 0
        # energy_impact = None
        if per_times_fan_status_on > self.unocc_time_threshold:
            msg = 'Supply fan is on during unoccupied times.'
            # color_code = 'RED'
            dx_msg = 63.1
        else:
            if avg_duct_stpr < self.unocc_stp_threshold:
                msg = 'No problems detected.'
                # color_code = 'GREEN'
                dx_msg = 60.0
            else:
                msg = ('Fan status show the fan is off but the duct static '
                       'pressure is high, check the functionality of the '
                       'pressure sensor.')
                # color_code = 'GREY'
                dx_msg = 64.2
        for item in self.sched_time:
            dx_table = {
                # 'datetime': str(item),
                # 'diagnostic_name': SCHED_RCx,
                # 'diagnostic_message': msg,
                # 'energy_impact': energy_impact,
                # 'color_code': color_code
                SCHED_RCx + dx:  dx_msg
            }
            result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def no_static_pr_reset(self, result):
        '''Auto-RCx  to detect whether a static pressure set point
        reset is implemented.
        '''
        if not self.duct_stp_stpt_values:
            return result
        stp_diff = (max(self.duct_stp_stpt_values) -
                    min(self.duct_stp_stpt_values))
        # energy_impact = None

        if stp_diff < self.stpr_reset_threshold:
            msg = ('No duct static pressure reset detected. A duct static '
                   'pressure set point reset can save significant energy.')
            # color_code = 'RED'
            dx_msg = 71.1
        else:
            msg = 'No problem detected.'
            # color_code = 'GREEN'
            dx_msg = 70.0
        dx_table = {
            # 'datetime': str(self.dx_time),
            # 'diagnostic_name': DUCT_STC_RCx3,
            # 'diagnostic_message': msg,
            # 'energy_impact': energy_impact,
            # 'color_code': color_code
            DUCT_STC_RCx3 + dx:  dx_msg
        }
        result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def no_sat_sp_reset(self, result):
        '''Auto-RCx  to detect whether a supply-air temperature set point
        reset is implemented.
        '''
        if not self.sat_stpt_values:
            return result
        satemp_diff = max(self.sat_stpt_values) - min(self.sat_stpt_values)
        # energy_impact = None
        if satemp_diff <= self.sat_reset_threshold:
            msg = ('A supply-air temperature reset was not detected. This can '
                   'result in excess energy consumption.')
            # color_code = 'RED'
            dx_msg = 81.1
        else:
            msg = 'No problems detected for this diagnostic.'
            # color_code = 'GREEN'
            dx_msg = 80.0
        dx_table = {
            # 'datetime': str(self.dx_time),
            # 'diagnostic_name': SA_TEMP_RCx3,
            # 'diagnostic_message': msg,
            # 'energy_impact': energy_impact,
            # 'color_code': color_code
            SA_TEMP_RCx3 + dx:  dx_msg
        }
        result.insert_table_row(Application.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result
