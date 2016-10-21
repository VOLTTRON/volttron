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
or favoring by the United States Government or any agency thereof,
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
from zmq.utils import jsonapi
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod, topics

__version__ = '3.1'

ECON1 = 'Temperature Sensor Dx'
ECON2 = 'Not Economizing When Unit Should Dx'
ECON3 = 'Economizing When Unit Should Not Dx'
ECON4 = 'Excess Outdoor-air Intake Dx'
ECON5 = 'Insufficient Outdoor-air Intake Dx'
DX = '/diagnostic message'
EI = '/energy impact'
DATA = '/data/'

RAT = 'ReturnAirTemperature'
MAT = 'MixedAirTemperature'
OAT = 'OutsideAirTemperature'
OAD = 'OutsideDamperSignal'
CC = 'CoolCall'
FS = 'SupplyFanSpeed'
EC = 'EconomizerCondition'
ST = 'State'


class Application(AbstractDrivenAgent):
    '''Application to detect and correct operational problems for AHUs/RTUs.

    This application uses metered data from zones server by an AHU/RTU
    to detect operational problems and where applicable correct these problems
    by modifying set points.  When auto-correction cannot be applied then
    a message detailing the diagnostic results will be made available to
    the building operator.
    '''
    # Diagnostic Point Names (Must match OpenEIS data-type names)

    def __init__(self, economizer_type='DDB', econ_hl_temp=65.0,
                 device_type='AHU', temp_deadband=1.0,
                 data_window=30, no_required_data=20,
                 open_damper_time=5,
                 low_supply_fan_threshold=20.0,
                 mat_low_threshold=50.0, mat_high_threshold=90.0,
                 oat_low_threshold=30.0, oat_high_threshold=100.0,
                 rat_low_threshold=50.0, rat_high_threshold=90.0,
                 temp_difference_threshold=4.0, oat_mat_check=5.0,
                 open_damper_threshold=90.0, oaf_economizing_threshold=25.0,
                 oaf_temperature_threshold=4.0,
                 cooling_enabled_threshold=5.0,
                 minimum_damper_setpoint=15.0, excess_damper_threshold=20.0,
                 excess_oaf_threshold=20.0, desired_oaf=10.0,
                 ventilation_oaf_threshold=5.0,
                 insufficient_damper_threshold=15.0,
                 temp_damper_threshold=90.0, rated_cfm=6000.0, eer=10.0,
                 **kwargs):
        # initialize user configurable parameters.
        # super(Application, self).__init__(**kwargs)
        Application.analysis = kwargs['device']['analysis_name']
        self.fan_status_name = kwargs['fan_status']
        self.oat_name = kwargs['oa_temp']
        self.rat_name = kwargs['ra_temp']
        self.mat_name = kwargs['ma_temp']
        self.oad_sig_name = kwargs['damper_signal']
        self.cool_call_name = kwargs['cool_call']
        self.fan_sp_name = kwargs['fan_speedcmd']
        data_window = int(data_window)
        open_damper_time = int(open_damper_time)

        self.device_type = device_type.lower()
        self.economizer_type = economizer_type.lower()
        if self.economizer_type == 'hl':
            self.econ_hl_temp = float(econ_hl_temp)
        Application.pre_requiste_messages = []
        Application.pre_msg_time = []
        self.oaf_temp_thr = float(oaf_temperature_threshold)
        # Application thresholds (Configurable)
        self.data_window = float(data_window)
        no_required_data = int(no_required_data)
        self.mat_low_threshold = float(mat_low_threshold)
        self.mat_high_threshold = float(mat_high_threshold)
        self.oat_low_threshold = float(oat_low_threshold)
        self.oat_high_threshold = float(oat_high_threshold)
        self.rat_low_threshold = float(rat_low_threshold)
        self.rat_high_threshold = float(rat_high_threshold)
        self.temp_deadband = float(temp_deadband)
        self.low_supply_fan_threshold = float(low_supply_fan_threshold)
        self.cooling_enabled_threshold = float(cooling_enabled_threshold)
        cfm = float(rated_cfm)
        eer = float(eer)
        # Pre-requisite messages
        self.pre_msg1 = ('Supply fan is off, current data will '
                         'not be used for diagnostics.')
        self.pre_msg2 = ('Supply fan status data is missing '
                         'from input(device or csv), could '
                         'not verify system was ON.')
        self.pre_msg3 = ('Missing required data for diagnostic: '
                         'Check BACnet configuration or CSV file '
                         'input for outside-air temperature.')
        self.pre_msg4 = ('Missing required data for diagnostic: '
                         'Check BACnet configuration or CSV file '
                         'input for return-air temperature.')
        self.pre_msg5 = ('Missing required data for diagnostic: '
                         'Check BACnet configuration or CSV '
                         'file input for mixed-air temperature.')
        self.pre_msg6 = ('Missing required data for diagnostic: '
                         'Check BACnet configuration or CSV '
                         'file input for damper signal.')
        self.pre_msg7 = ''.join(['Missing required data for diagnostic: ',
                                 'Check BACnet configuration or CSV file '
                                 'input for cooling call (AHU cooling coil,'
                                 'RTU cooling call or compressor command).'])
        self.pre_msg8 = ('Outside-air temperature is outside high/low '
                         'operating limits, check the functionality of '
                         'the temperature sensor.')
        self.pre_msg9 = ('Return-air temperature is outside high/low '
                         'operating limits, check the functionality of '
                         'the temperature sensor.')
        self.pre_msg10 = ('Mixed-air temperature is outside high/low '
                          'operating limits, check the functionality '
                          'of the temperature sensor.')
        self.econ1 = TempSensorDx(data_window, no_required_data,
                                  temp_difference_threshold, open_damper_time,
                                  oat_mat_check, temp_damper_threshold)
        self.econ2 = EconCorrectlyOn(oaf_economizing_threshold,
                                     open_damper_threshold,
                                     data_window, no_required_data, cfm, eer)
        self.econ3 = EconCorrectlyOff(data_window, no_required_data,
                                      minimum_damper_setpoint,
                                      excess_damper_threshold,
                                      cooling_enabled_threshold,
                                      desired_oaf, cfm, eer)
        self.econ4 = ExcessOA(data_window, no_required_data,
                              excess_oaf_threshold,
                              minimum_damper_setpoint,
                              excess_damper_threshold,
                              desired_oaf, cfm, eer)
        self.econ5 = InsufficientOA(data_window, no_required_data,
                                    ventilation_oaf_threshold,
                                    minimum_damper_setpoint,
                                    insufficient_damper_threshold,
                                    desired_oaf)

    def run(self, cur_time, points):
        '''Main run method that is called by the DrivenBaseClass.

        run receives a dictionary of data 'points' and an associated timestamp
        for the data cur_time'.  run then passes the appropriate data to
        each diagnostic when calling
        the diagnostic message.
        '''
        device_dict = {}
        dx_result = Results()
        for key, value in points.items():
            device_dict[key.lower()] = value

        fan_check = False
        for key, value in device_dict.items():
            if key.startswith(self.fan_status_name):
                if value is not None and not int(value):
                    Application.pre_requiste_messages.append(self.pre_msg1)
                    dx_result = self.pre_message(dx_result, cur_time)
                    return dx_result
                elif value is not None:
                    fan_check = True
        if not fan_check and self.fan_sp_name is not None:
            for key, value in device_dict.items():
                if key.startswith(self.fan_sp_name):
                    fan_check = True
                    if value < self.low_supply_fan_threshold:
                        Application.pre_requiste_messages.append(self.pre_msg1)
                        dx_result = self.pre_message(dx_result, cur_time)
                        return dx_result
        if not fan_check:
            Application.pre_requiste_messages.append(self.pre_msg2)
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result
        damper_data = []
        oat_data = []
        mat_data = []
        rat_data = []
        cooling_data = []
        fan_sp_data = []
        for key, value in device_dict.items():
            if key.startswith(self.oad_sig_name) and value is not None:
                damper_data.append(value)
            elif key.startswith(self.oat_name) and value is not None:
                oat_data.append(value)
            elif key.startswith(self.mat_name) and value is not None:
                mat_data.append(value)
            elif key.startswith(self.rat_name) and value is not None:
                rat_data.append(value)
            elif key.startswith(self.cool_call_name) and value is not None:
                cooling_data.append(value)
            elif key.startswith(self.fan_sp_name) and value is not None:
                fan_sp_data.append(value)
        if not oat_data:
            Application.pre_requiste_messages.append(self.pre_msg3)
        if not rat_data:
            Application.pre_requiste_messages.append(self.pre_msg4)
        if not mat_data:
            Application.pre_requiste_messages.append(self.pre_msg5)
        if not damper_data:
            Application.pre_requiste_messages.append(self.pre_msg6)
        if not cooling_data:
            Application.pre_requiste_messages.append(self.pre_msg7)
        if not (oat_data and rat_data and mat_data and
                damper_data and cooling_data):
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result
        oatemp = (sum(oat_data) / len(oat_data))
        ratemp = (sum(rat_data) / len(rat_data))
        matemp = (sum(mat_data) / len(mat_data))
        damper_signal = (sum(damper_data) / len(damper_data))
        fan_speedcmd = None
        if fan_sp_data:
            fan_speedcmd = sum(fan_sp_data)/len(fan_sp_data)
        limit_check = False
        if oatemp < self.oat_low_threshold or oatemp > self.oat_high_threshold:
            Application.pre_requiste_messages.append(self.pre_msg8)
            limit_check = True
        if ratemp < self.rat_low_threshold or ratemp > self.rat_high_threshold:
            Application.pre_requiste_messages.append(self.pre_msg9)
            limit_check = True
        if matemp < self.mat_low_threshold or matemp > self.mat_high_threshold:
            Application.pre_requiste_messages.append(self.pre_msg10)
            limit_check = True
        if limit_check:
            dx_result = self.pre_message(dx_result, cur_time)
            return dx_result

        if abs(oatemp - ratemp) < self.oaf_temp_thr:
            dx_result.log('OAT and RAT are too close, economizer diagnostic '
                          'will not use data corresponding to: {timestamp} '
                          .format(timestamp=str(cur_time)), logging.DEBUG)
            return dx_result
        device_type_error = False
        if self.device_type == 'ahu':
            cooling_valve = sum(cooling_data) / len(cooling_data)
            if cooling_valve > self.cooling_enabled_threshold:
                cooling_call = True
            else:
                cooling_call = False
        elif self.device_type == 'rtu':
            cooling_call = int(max(cooling_data))
        else:
            device_type_error = True
            dx_result.log('device_type must be specified as "AHU" or "RTU" '
                          'Check Configuration input.', logging.INFO)
        if device_type_error:
            return dx_result
        if self.economizer_type == 'ddb':
            econ_condition = (oatemp < (ratemp - self.temp_deadband))
        else:
            econ_condition = \
                oatemp < (self.econ_hl_temp - self.temp_deadband)
        dx_result = self.econ1.econ_alg1(dx_result, oatemp, ratemp, matemp,
                                         damper_signal, cur_time)
        if (TempSensorDx.temp_sensor_problem is not None and
                TempSensorDx.temp_sensor_problem is False):
            dx_result = self.econ2.econ_alg2(dx_result, cooling_call, oatemp,
                                             ratemp, matemp, damper_signal,
                                             econ_condition, cur_time,
                                             fan_speedcmd)
            dx_result = self.econ3.econ_alg3(dx_result, oatemp, ratemp, matemp,
                                             damper_signal, econ_condition,
                                             cur_time, fan_speedcmd,
                                             cooling_call)
            dx_result = self.econ4.econ_alg4(dx_result, oatemp, ratemp, matemp,
                                             damper_signal, econ_condition,
                                             cur_time, fan_speedcmd,
                                             cooling_call)
            dx_result = self.econ5.econ_alg5(dx_result, oatemp, ratemp, matemp,
                                             damper_signal, econ_condition,
                                             cur_time, cooling_call)
        else:
            dx_result = self.econ2.clear_data(dx_result)
            dx_result = self.econ3.clear_data(dx_result)
            dx_result = self.econ4.clear_data(dx_result)
            dx_result = self.econ5.clear_data(dx_result)
            TempSensorDx.temp_sensor_problem = None
        return dx_result

    def pre_message(self, dx_result, cur_time):
        '''Handle reporting of diagnostic pre-requisite messages.

        Report to user when conditions are not favorable for a diagnostic.
        '''
        Application.pre_msg_time.append(cur_time)
        pre_check = ((Application.pre_msg_time[-1] -
                      Application.pre_msg_time[0])
                     .total_seconds()/60)
        pre_check = pre_check if pre_check > 0.0 else 1.0
        if pre_check >= self.data_window:
            msg_lst = [self.pre_msg1, self.pre_msg2, self.pre_msg3,
                       self.pre_msg4, self.pre_msg5, self.pre_msg6,
                       self.pre_msg7, self.pre_msg8, self.pre_msg9,
                       self.pre_msg10]
            for item in msg_lst:
                if (Application.pre_requiste_messages.count(item) >
                        (0.25) * len(Application.pre_msg_time)):
                    dx_result.log(item, logging.DEBUG)
            Application.pre_requiste_messages = []
            Application.pre_msg_time = []
        return dx_result


class TempSensorDx(object):
    '''Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.

    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    '''
    def __init__(self, data_window, no_required_data,
                 temp_diff_thr, open_damper_time,
                 oat_mat_check, temp_damper_threshold):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        self.open_oat = []
        self.open_mat = []
        self.econ_check = False
        self.steady_state_st = None
        self.open_damper_time = int(open_damper_time)
        self.econ_time_check = td(minutes=self.open_damper_time - 1)
        TempSensorDx.temp_sensor_problem = None
        self.max_dx_time = 60

        '''Application thresholds (Configurable)'''
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.temp_diff_thr = float(temp_diff_thr)
        self.oat_mat_check = float(oat_mat_check)
        self.temp_damper_threshold = float(temp_damper_threshold)

    def econ_alg1(self, dx_result, oatemp,
                  ratemp, matemp, damper_signal, cur_time):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if (damper_signal) > self.temp_damper_threshold:
            if not self.econ_check:
                self.econ_check = True
                self.steady_state_st = cur_time
            if (cur_time - self.steady_state_st) >= self.econ_time_check:
                self.open_oat.append(oatemp)
                self.open_mat.append(matemp)
        else:
            self.econ_check = False

        self.oat_values.append(oatemp)
        self.mat_values.append(matemp)
        self.rat_values.append(ratemp)

        if (self.timestamp and
                ((cur_time - self.timestamp[-1])
                 .total_seconds()/60) > 5.0):
            self.econ_check = False
        self.timestamp.append(cur_time)
        elapsed_time = ((self.timestamp[-1] - self.timestamp[0])
                        .total_seconds()/60)
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(Application.analysis,
                                           {ECON1 + DX: 3.2})
                dx_result = self.clear_data(dx_result)
                data = {
                    ECON1 + DATA + RAT: ratemp,
                    ECON1 + DATA + MAT: matemp,
                    ECON1 + DATA + OAT: oatemp,
                    ECON1 + DATA + OAD: damper_signal,
                    ECON1 + DATA + ST: 2
                }
                dx_result.insert_table_row(Application.analysis, data)
                return dx_result
            dx_result = self.temperature_sensor_dx(dx_result, cur_time)
            data = {
                ECON1 + DATA + RAT: ratemp,
                ECON1 + DATA + MAT: matemp,
                ECON1 + DATA + OAT: oatemp,
                ECON1 + DATA + OAD: damper_signal,
                ECON1 + DATA + ST: 1
            }
        else:
            data = {
                ECON1 + DATA + RAT: ratemp,
                ECON1 + DATA + MAT: matemp,
                ECON1 + DATA + OAT: oatemp,
                ECON1 + DATA + OAD: damper_signal,
                ECON1 + DATA + ST: 0
            }
        dx_result.insert_table_row(Application.analysis, data)
        return dx_result

    def temperature_sensor_dx(self, dx_result, cur_time):
        '''
        If the detected problems(s) are
        consistent then generate a fault message(s).
        '''
        oa_ma = [(x - y)
                 for x, y in zip(self.oat_values, self.mat_values)]
        ra_ma = [(x - y)
                 for x, y in zip(self.rat_values, self.mat_values)]
        ma_oa = [(y - x)
                 for x, y in zip(self.oat_values, self.mat_values)]
        ma_ra = [(y - x)
                 for x, y in zip(self.rat_values, self.mat_values)]
        avg_oa_ma = sum(oa_ma) / len(oa_ma)
        avg_ra_ma = sum(ra_ma) / len(ra_ma)
        avg_ma_oa = sum(ma_oa) / len(ma_oa)
        avg_ma_ra = sum(ma_ra) / len(ma_ra)
        # color_code = 'GREEN'
        Application.pre_requiste_messages = []
        Application.pre_msg_time = []
        dx_table = {}

        if len(self.open_oat) > self.no_required_data:
            mat_oat_diff_list = \
              [abs(x - y) for x, y in zip(self.open_oat, self.open_mat)]
            open_damper_check = sum(mat_oat_diff_list) / len(mat_oat_diff_list)
            if open_damper_check > self.oat_mat_check:
                TempSensorDx.temp_sensor_problem = True
                msg = ('The OAT and MAT sensor readings are not consistent '
                       'when the outdoor-air damper is fully open.')
                # color_code = 'RED'
                dx_msg = 0.1
                dx_table = {
                    # 'datetime': cur_time,
                    # 'diagnostic_name': ECON1,
                    ECON1 + DX: dx_msg,
                    ECON1 + EI: 0.0
                    # 'color_code': color_code
                }
                dx_result.log(msg, logging.INFO)
                dx_result.insert_table_row(Application.analysis, dx_table)
            self.open_oat = []
            self.open_mat = []

        if avg_oa_ma > self.temp_diff_thr and avg_ra_ma > self.temp_diff_thr:
            msg = ('Temperature sensor problem detected. Mixed-air '
                   'temperature is less than outdoor-air and return-air'
                   'temperatures.')
            # color_code = 'RED'
            dx_msg = 1.1
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON1,
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
                # 'color_code': color_code
            }
            TempSensorDx.temp_sensor_problem = True
        elif((avg_ma_oa) > self.temp_diff_thr and
             (avg_ma_ra) > self.temp_diff_thr):
            msg = ('Temperature sensor problem detected Mixed-air '
                   'temperature is greater than outdoor-air and return-air '
                   'temperatures.')
            TempSensorDx.temp_sensor_problem = True
            # color_code = 'RED'
            dx_msg = 2.1
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON1,
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
                # 'color_code': color_code
            }
        elif (TempSensorDx.temp_sensor_problem is None or not
              TempSensorDx.temp_sensor_problem):
            msg = 'No problems were detected.'
            TempSensorDx.temp_sensor_problem = False
            # color_code = 'GREEN'
            dx_msg = 0.0
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON1,
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
                # 'color_code': color_code
            }
        else:
            msg = 'Diagnostic was inconclusive.'
            TempSensorDx.temp_sensor_problem = False
            # color_code = 'GREY'
            dx_msg = 3.2
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON1,
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
                # 'color_code': color_code
            }
        dx_result.insert_table_row(Application.analysis, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''
        reinitialize class insufficient_oa data
        '''
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return dx_result


class EconCorrectlyOn(object):
    '''Air-side HVAC economizer diagnostic for AHU/RTU systems.

    EconCorrectlyOn uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should.
    '''
    def __init__(self, oaf_economizing_threshold, open_damper_threshold,
                 data_window, no_required_data, cfm, eer):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.oad_values = []
        self.timestamp = []
        self.output_no_run = []
        self.open_damper_threshold = float(open_damper_threshold)
        self.oaf_economizing_threshold = float(oaf_economizing_threshold)
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = 60

        '''Application result messages'''
        self.alg_result_messages = [
            'Conditions are favorable for economizing but the '
            'damper is frequently below 100% open.',
            'No problems detected.',
            'Conditions are favorable for economizing and the '
            'damper is 100% open but the OAF indicates the unit '
            'is not brining in near 100% OA.'
        ]

    def econ_alg2(self, dx_result, cooling_call, oatemp, ratemp,
                  matemp, damper_signal, econ_condition, cur_time,
                  fan_sp):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if not cooling_call:
            dx_result.log('The unit is not cooling, data corresponding to '
                          '{timestamp} will not be used for {name} diagnostic.'
                          .format(timestamp=str(cur_time), name=ECON2),
                          logging.DEBUG)
            self.output_no_run.append(cur_time)
            if ((self.output_no_run[-1] - self.output_no_run[0]) >=
                    td(minutes=(self.data_window))):
                dx_result.log(
                    '{name}: the unit is not cooling or economizing, keep '
                    'collecting data.'.format(name=ECON2), logging.DEBUG)
                self.output_no_run = []
            return dx_result

        if not econ_condition:
            dx_result.log(
                '{name}: Conditions are not favorable for economizing, '
                'data corresponding to {ts} will not be used.'
                .format(ts=str(cur_time), name=ECON2), logging.DEBUG)
            self.output_no_run.append(cur_time)
            if ((self.output_no_run[-1] - self.output_no_run[0]) >=
                    td(minutes=(self.data_window))):
                dx_result.log(
                    '{name}: the unit is not cooling or economizing, keep '
                    'collecting data.'.format(name=ECON2), logging.DEBUG)
                self.output_no_run = []
            return dx_result

        self.oat_values.append(oatemp)
        self.mat_values.append(matemp)
        self.rat_values.append(ratemp)
        self.timestamp.append(cur_time)
        self.oad_values.append(damper_signal)

        fan_sp = fan_sp/100.0 if fan_sp is not None else 1.0
        self.fan_speed_values.append(fan_sp)
        self.timestamp.append(cur_time)
        elapsed_time = ((self.timestamp[-1] - self.timestamp[0])
                        .total_seconds()/60)
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(Application.analysis,
                                           {ECON2 + DX: 13.2})
                dx_result = self.clear_data(dx_result)
                data = {
                    ECON2 + DATA + RAT: ratemp,
                    ECON2 + DATA + MAT: matemp,
                    ECON2 + DATA + OAT: oatemp,
                    ECON2 + DATA + OAD: damper_signal,
                    ECON2 + DATA + CC: cooling_call,
                    ECON2 + DATA + FS: fan_sp,
                    ECON2 + DATA + EC: econ_condition,
                    ECON2 + DATA + ST: 2
                }
                dx_result.insert_table_row(Application.analysis, data)
                return dx_result
            dx_result = \
                self.not_economizing_when_needed(dx_result, cur_time)
            data = {
                ECON2 + DATA + RAT: ratemp,
                ECON2 + DATA + MAT: matemp,
                ECON2 + DATA + OAT: oatemp,
                ECON2 + DATA + OAD: damper_signal,
                ECON2 + DATA + CC: cooling_call,
                ECON2 + DATA + FS: fan_sp,
                ECON2 + DATA + EC: econ_condition,
                ECON2 + DATA + ST: 1
            }
        else:
            data = {
                ECON2 + DATA + RAT: ratemp,
                ECON2 + DATA + MAT: matemp,
                ECON2 + DATA + OAT: oatemp,
                ECON2 + DATA + OAD: damper_signal,
                ECON2 + DATA + CC: cooling_call,
                ECON2 + DATA + FS: fan_sp,
                ECON2 + DATA + EC: econ_condition,
                ECON2 + DATA + ST: 0
            }
        dx_result.insert_table_row(Application.analysis, data)
        return dx_result

    def not_economizing_when_needed(self, dx_result, cur_time):
        '''If the detected problems(s) are consistent then generate a fault
        message(s).
        '''
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values,
                                                    self.rat_values,
                                                    self.mat_values)]
        avg_step = (
            (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
            if len(self.timestamp) > 1 else 1)
        avg_oaf = sum(oaf) / len(oaf) * 100.0
        avg_damper_signal = sum(self.oad_values)/len(self.oad_values)
        energy_impact = 0.0
        if avg_damper_signal < self.open_damper_threshold:
            msg = (self.alg_result_messages[0])
            color_code = 'RED'
            dx_msg = 11.1
        else:
            if (100.0 - avg_oaf) <= self.oaf_economizing_threshold:
                msg = (self.alg_result_messages[1])
                color_code = 'GREEN'
                energy_impact = 0.0
                dx_msg = 10.0
            else:
                msg = (self.alg_result_messages[2])
                color_code = 'RED'
                dx_msg = 12.1

        energy_calc = \
            [1.08 * spd * self.cfm * (ma - oa) / (1000.0 * self.eer)
             for ma, oa, spd in zip(self.mat_values, self.oat_values,
                                    self.fan_speed_values)
             if (ma - oa) > 0 and color_code == 'RED']
        if energy_calc:
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            energy_impact = \
                (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            energy_impact = round(energy_impact, 2)
            # energy_impact = '%s' % float('%.2g' % energy_impact)
            # energy_impact = str(energy_impact)
            # energy_impact = ''.join([energy_impact, ' kWh/h'])
        dx_table = {
            # 'datetime': cur_time,
            # 'diagnostic_name': ECON2,
            ECON2 + DX: dx_msg,
            ECON2 + EI: energy_impact
            # 'color_code': color_code
            }
        dx_result.insert_table_row(Application.analysis, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''
        reinitialize class insufficient_oa data.
        '''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.timestamp = []
        return dx_result


class EconCorrectlyOff(object):
    '''Air-side HVAC economizer diagnostic for AHU/RTU systems.

    EconCorrectlyOff uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should not.
    '''

    def __init__(self, data_window, no_required_data, min_damper_sp,
                 excess_damper_threshold, cooling_enabled_threshold,
                 desired_oaf, cfm, eer):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.cool_call_values = []
        self.cfm = cfm
        self.eer = eer
        self.fan_speed_values = []
        self.timestamp = []

        # Application result messages
        self.alg_result_messages = \
            ['The outdoor-air damper should be at the minimum position but is '
             'significantly above that value.',
             'No problems detected.',
             'The diagnostic led to inconclusive results, could not '
             'verify the status of the economizer.']
        self.max_dx_time = 60
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.min_damper_sp = float(min_damper_sp)
        self.excess_damper_threshold = float(excess_damper_threshold)
        self.cooling_enabled_threshold = float(cooling_enabled_threshold)
        self.desired_oaf = float(desired_oaf)

    def econ_alg3(self, dx_result, oatemp, ratemp, matemp,
                  damper_signal, econ_condition, cur_time,
                  fan_sp, cooling_call):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if econ_condition:
            dx_result.log(self.alg_result_messages[2]
                          .join(['Data for to {ts} will not be used for this '
                                 'diagnostic.'.format(ts=str(cur_time))]),
                          logging.DEBUG)
            return dx_result
        else:
            self.oad_values.append(damper_signal)
            self.oat_values.append(oatemp)
            self.mat_values.append(matemp)
            self.rat_values.append(ratemp)
            self.timestamp.append(cur_time)
            fan_sp = fan_sp/100.0 if fan_sp is not None else 1.0
            self.fan_speed_values.append(fan_sp)

        elapsed_time = ((self.timestamp[-1] - self.timestamp[0])
                        .total_seconds()/60)
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(Application.analysis,
                                           {ECON3 + DX: 23.2})
                dx_result = self.clear_data(dx_result)
                data = {
                    ECON3 + DATA + RAT: ratemp,
                    ECON3 + DATA + MAT: matemp,
                    ECON3 + DATA + OAT: oatemp,
                    ECON3 + DATA + OAD: damper_signal,
                    ECON3 + DATA + CC: cooling_call,
                    ECON3 + DATA + FS: fan_sp,
                    ECON3 + DATA + EC: econ_condition,
                    ECON3 + DATA + ST: 2
                }
                dx_result.insert_table_row(Application.analysis, data)
                return dx_result
            dx_result = self.economizing_when_not_needed(dx_result, cur_time)
            data = {
                ECON3 + DATA + RAT: ratemp,
                ECON3 + DATA + MAT: matemp,
                ECON3 + DATA + OAT: oatemp,
                ECON3 + DATA + OAD: damper_signal,
                ECON3 + DATA + CC: cooling_call,
                ECON3 + DATA + FS: fan_sp,
                ECON3 + DATA + EC: econ_condition,
                ECON3 + DATA + ST: 1
            }
        else:
            data = {
                ECON3 + DATA + RAT: ratemp,
                ECON3 + DATA + MAT: matemp,
                ECON3 + DATA + OAT: oatemp,
                ECON3 + DATA + OAD: damper_signal,
                ECON3 + DATA + CC: cooling_call,
                ECON3 + DATA + FS: fan_sp,
                ECON3 + DATA + EC: econ_condition,
                ECON3 + DATA + ST: 0
            }
        dx_result.insert_table_row(Application.analysis, data)
        return dx_result

    def economizing_when_not_needed(self, dx_result, cur_time):
        '''If the detected problems(s)
        are consistent then generate a
        fault message(s).
        '''
        avg_step = ((self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
                    if len(self.timestamp) > 1 else 1)
        desired_oaf = self.desired_oaf / 100.0
        energy_impact = 0.0
        energy_calc = [
            (1.08 * spd * self.cfm * (ma - (oa * desired_oaf +
                                            (ra * (1.0 - desired_oaf))))) /
            (1000.0 * self.eer)
            for ma, oa, ra, spd in zip(self.mat_values,
                                       self.oat_values,
                                       self.rat_values,
                                       self.fan_speed_values)
            if (ma - (oa * desired_oaf + (ra * (1.0 - desired_oaf)))) > 0]

        avg_damper = sum(self.oad_values) / len(self.oad_values)
        if (avg_damper - self.min_damper_sp) > self.excess_damper_threshold:
            msg = self.alg_result_messages[0]
            color_code = 'RED'
            dx_msg = 21.1
        else:
            msg = 'No problems detected.'
            color_code = 'GREEN'
            energy_impact = 0.0
            dx_msg = 20.0
        if energy_calc and color_code == 'RED':
            dx_time = (len(energy_calc) - 1) * \
                avg_step if len(energy_calc) > 1 else 1.0
            energy_impact = (
                (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time))
            energy_impact = round(energy_impact, 2)
            # energy_impact = '%s' % float('%.2g' % energy_impact)
            # energy_impact = str(energy_impact)
            # energy_impact = ''.join([energy_impact, ' kWh/h'])
        dx_table = {
            # 'datetime': cur_time,
            # 'diagnostic_name': ECON3,
            ECON3 + DX: dx_msg,
            ECON3 + EI: energy_impact
            # 'color_code': color_code
            }
        dx_result.insert_table_row(Application.analysis, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''
        reinitialize class insufficient_oa data
        '''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.timestamp = []
        return dx_result


class ExcessOA(object):
    ''' Air-side HVAC ventilation diagnostic.

    ExcessOA uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing excess outdoor air.
    '''
    def __init__(self, data_window, no_required_data, excess_oaf_threshold,
                 min_damper_sp, excess_damper_threshold, desired_oaf,
                 cfm, eer):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.cool_call_values = []
        self.timestamp = []
        self.fan_speed_values = []
        # Application thresholds (Configurable)
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = 60
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.excess_oaf_threshold = float(excess_oaf_threshold)
        self.min_damper_sp = float(min_damper_sp)
        self.desired_oaf = float(desired_oaf)
        self.excess_damper_threshold = float(excess_damper_threshold)

    def econ_alg4(self, dx_result, oatemp, ratemp, matemp,
                  damper_signal, econ_condition, cur_time,
                  fan_sp, cooling_call):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if econ_condition:
            dx_result.log('The unit may be economizing, '
                          'data corresponding to {timestamp} '
                          'will not be used for this diagnostic.'
                          .format(timestamp=str(cur_time)), logging.DEBUG)
            return dx_result
        self.oad_values.append(damper_signal)
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.timestamp.append(cur_time)
        fan_sp = fan_sp/100.0 if fan_sp is not None else 1.0
        self.fan_speed_values.append(fan_sp)

        elapsed_time = \
            (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0
        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(Application.analysis,
                                           {ECON4 + DX: 35.2})
                dx_result = self.clear_data(dx_result)
                data = {
                    ECON4 + DATA + RAT: ratemp,
                    ECON4 + DATA + MAT: matemp,
                    ECON4 + DATA + OAT: oatemp,
                    ECON4 + DATA + OAD: damper_signal,
                    ECON4 + DATA + CC: cooling_call,
                    ECON4 + DATA + FS: fan_sp,
                    ECON4 + DATA + EC: econ_condition,
                    ECON4 + DATA + ST: 2
                }
                dx_result.insert_table_row(Application.analysis, data)
                return dx_result
            dx_result = self.excess_oa(dx_result, cur_time)
            data = {
                ECON4 + DATA + RAT: ratemp,
                ECON4 + DATA + MAT: matemp,
                ECON4 + DATA + OAT: oatemp,
                ECON4 + DATA + OAD: damper_signal,
                ECON4 + DATA + CC: cooling_call,
                ECON4 + DATA + FS: fan_sp,
                ECON4 + DATA + EC: econ_condition,
                ECON4 + DATA + ST: 1
            }
        else:
            data = {
                ECON4 + DATA + RAT: ratemp,
                ECON4 + DATA + MAT: matemp,
                ECON4 + DATA + OAT: oatemp,
                ECON4 + DATA + OAD: damper_signal,
                ECON4 + DATA + CC: cooling_call,
                ECON4 + DATA + FS: fan_sp,
                ECON4 + DATA + EC: econ_condition,
                ECON4 + DATA + ST: 0
            }
        dx_result.insert_table_row(Application.analysis, data)
        return dx_result

    def excess_oa(self, dx_result, cur_time):
        '''If the detected problems(s) are
        consistent generate a fault message(s).
        '''
        avg_step = (
            (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
            if len(self.timestamp) > 1 else 1)
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values,
                                                    self.rat_values,
                                                    self.mat_values)]

        avg_oaf = sum(oaf) / len(oaf) * 100
        avg_damper = sum(self.oad_values) / len(self.oad_values)
        desired_oaf = self.desired_oaf / 100.0
        energy_calc = [
            (1.08 * spd * self.cfm * (ma - (oa * desired_oaf +
                                            (ra * (1.0 - desired_oaf))))) /
            (1000.0 * self.eer)
            for ma, oa, ra, spd in zip(self.mat_values,
                                       self.oat_values,
                                       self.rat_values,
                                       self.fan_speed_values)
            if (ma - (oa * desired_oaf + (ra * (1.0 - desired_oaf)))) > 0]
        # color_code = 'GREY'
        energy_impact = 0.0
        msg = ''
        dx_msg = 30.0
        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ('Inconclusive result, the OAF calculation led to an '
                   'unexpected value: {oaf}'.format(oaf=avg_oaf))
            # color_code = 'GREY'
            dx_msg = 31.2
            dx_result.log(msg, logging.INFO)
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON4,
                ECON4 + DX: dx_msg,
                ECON4 + EI: 0.0
                # 'color_code': color_code
            }
            dx_result.insert_table_row(Application.analysis, dx_table)
            dx_result = self.clear_data(dx_result)
            return dx_result

        if (avg_damper - self.min_damper_sp) > self.excess_damper_threshold:
            msg = ('The OAD should be at the minimum position for ventilation '
                   'but is significantly higher than this value.')
            # color_code = 'RED'
            dx_msg = 32.1

            if energy_calc:
                dx_time = \
                    (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
                energy_impact = (
                    sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
        if avg_oaf - self.desired_oaf > self.excess_oaf_threshold:
            if dx_msg > 30.0:
                msg += ('Excess outdoor-air is being provided, this could '
                        'increase heating and cooling energy consumption.')
                dx_msg = 34.1
            else:
                msg = ('Excess outdoor air is being provided, this could '
                       'increase heating and cooling energy consumption.')
                dx_msg = 33.1
            # color_code = 'RED'
            if energy_calc:
                dx_time = \
                    (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
                energy_impact = (
                    sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
                # energy_impact = '%s' % float('%.2g' % energy_impact)
                # energy_impact = str(energy_impact)
                # energy_impact = ''.join([energy_impact, ' kWh/h'])
        elif not dx_msg:
            msg = ('The calculated outdoor-air fraction is within '
                   'configured limits.')
            # color_code = 'GREEN'
            energy_impact = 0.0
            dx_msg = 30.0
        energy_impact = round(energy_impact, 2)
        dx_table = {
            # 'datetime': cur_time,
            # 'diagnostic_name': ECON4,
            ECON4 + DX: dx_msg,
            ECON4 + EI: energy_impact
            # 'color_code': color_code
        }
        dx_result.insert_table_row(Application.analysis, dx_table)
        dx_result.log(msg, logging.INFO)

        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''reinitialize class insufficient_oa data.'''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.timestamp = []
        return dx_result


class InsufficientOA(object):
    ''' Air-side HVAC ventilation diagnostic.

    insufficient_oa_intake uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing inadequate ventilation.
    '''
    def __init__(self, data_window, no_required_data,
                 ventilation_oaf_threshold, min_damper_sp,
                 insufficient_damper_threshold, desired_oaf):

        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.cool_call_values = []
        self.timestamp = []

        '''Application thresholds (Configurable)'''
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.max_dx_time = 60
        self.ventilation_oaf_threshold = float(ventilation_oaf_threshold)
        self.insufficient_damper_threshold = float(
            insufficient_damper_threshold)
        self.min_damper_sp = float(min_damper_sp)
        self.desired_oaf = float(desired_oaf)

    def econ_alg5(self, dx_result, oatemp, ratemp, matemp, damper_signal,
                  econ_condition, cur_time, cooling_call):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.oad_values.append(damper_signal)

        self.timestamp.append(cur_time)
        elapsed_time = ((self.timestamp[-1] - self.timestamp[0])
                        .total_seconds()/60)
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if (elapsed_time >= self.data_window and
                len(self.timestamp) >= self.no_required_data):
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(Application.analysis,
                                           {ECON5 + DX: 44.2})
                dx_result = self.clear_data(dx_result)
                data = {
                    ECON5 + DATA + RAT: ratemp,
                    ECON5 + DATA + MAT: matemp,
                    ECON5 + DATA + OAT: oatemp,
                    ECON5 + DATA + OAD: damper_signal,
                    ECON5 + DATA + CC: cooling_call,
                    ECON5 + DATA + EC: econ_condition,
                    ECON5 + DATA + ST: 2
                }
                dx_result.insert_table_row(Application.analysis, data)
                return dx_result
            dx_result = self.insufficient_oa(
                dx_result, cur_time)
            data = {
                ECON5 + DATA + RAT: ratemp,
                ECON5 + DATA + MAT: matemp,
                ECON5 + DATA + OAT: oatemp,
                ECON5 + DATA + OAD: damper_signal,
                ECON5 + DATA + CC: cooling_call,
                ECON5 + DATA + EC: econ_condition,
                ECON5 + DATA + ST: 1
            }
        else:
            data = {
                ECON5 + DATA + RAT: ratemp,
                ECON5 + DATA + MAT: matemp,
                ECON5 + DATA + OAT: oatemp,
                ECON5 + DATA + OAD: damper_signal,
                ECON5 + DATA + CC: cooling_call,
                ECON5 + DATA + EC: econ_condition,
                ECON5 + DATA + ST: 0
            }
        dx_result.insert_table_row(Application.analysis, data)
        return dx_result

    def insufficient_oa(self, dx_result, cur_time):
        '''If the detected problems(s) are
        consistent generate a fault message(s).
        '''
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values,
                                                    self.rat_values,
                                                    self.mat_values)]
        avg_oaf = sum(oaf) / len(oaf) * 100.0
        avg_damper_signal = sum(self.oad_values) / len(self.oad_values)
        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ('Inconclusive result, the OAF calculation led to an '
                   'unexpected value: {oaf}'.format(oaf=avg_oaf))
            # color_code = 'GREY'
            dx_result.log(msg, logging.INFO)
            dx_msg = 41.2
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON5,
                ECON5 + DX: dx_msg,
                ECON5 + EI: 0.0
                # 'color_code': color_code
            }
            dx_result.insert_table_row(Application.analysis, dx_table)
            dx_result = self.clear_data(dx_result)
            return dx_result
        msg = ''
        # Current deployment has minimum outdoor-air damper and
        # economizer damper.  Ventilation is not dependent on economizer damper.
#         if (
#                 (self.min_damper_sp - avg_damper_signal) >
#                 self.insufficient_damper_threshold):
#             msg = ('Outdoor-air damper is '
#                                   'significantly below the minimum '
#                                   'configured damper position.')
#             # color_code = 'RED'
#             dx_msg = 42.1
#             dx_table = {
#                 # 'datetime': cur_time,
#                 # 'diagnostic_name': ECON5,
#                 ECON5 + DX: dx_msg,
#                 ECON5 + EI: 0.0
#                 # 'color_code': color_code
#             }
#             dx_result.log(msg, logging.INFO)
#             dx_result.insert_table_row(Application.analysis, dx_table)
#             dx_result = self.clear_data(dx_result)
#             return dx_result

        if (self.desired_oaf - avg_oaf) > self.ventilation_oaf_threshold:
            msg = 'Insufficient outdoor-air is being provided for ventilation.'
            # color_code = 'RED'
            dx_msg = 43.1
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON5,
                ECON5 + DX: dx_msg,
                ECON5 + EI: 0.0
                # 'color_code': color_code
            }
        else:
            msg = ('The calculated outdoor-air fraction was within '
                   'acceptable limits.')
            # color_code = 'GREEN'
            dx_msg = 40.0
            dx_table = {
                # 'datetime': cur_time,
                # 'diagnostic_name': ECON5,
                ECON5 + DX: dx_msg,
                ECON5 + EI: 0.0
                # 'color_code': color_code
            }
        dx_result.insert_table_row(Application.analysis, dx_table)
        dx_result.log(msg, logging.INFO)
        Application.pre_msg_time = []
        Application.pre_requiste_messages = []
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''reinitialize class insufficient_oa data.'''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return dx_result
