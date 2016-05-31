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
import logging
from volttron.platform.agent.math_utils import mean
from .common import check_date, validation_builder, check_run_status, setpoint_control_check

SA_VALIDATE = 'Supply-air Temperature ACCx'
SA_TEMP_RCX = 'Supply-air Temperature Set Point Control Loop Dx'
SA_TEMP_RCX1 = 'Low Supply-air Temperature Dx'
SA_TEMP_RCX2 = 'High Supply-air Temperature Dx'
DX = '/diagnostic message'
ST = 'State'
CORRECT_SAT = 'Suggested SAT setpoint'
VALIDATE_FILE_TOKEN = 'satemp-rcx'
DATA = '/data/'
SAT_NAME = 'supply-air temperature'

def create_table_key(table_name, timestamp):
    return '&'.join([table_name, timestamp.strftime('%m-%d-%y %H:%M')])


class SupplyTempRcx(object):
    """Air-side HVAC Self-Correcting Diagnostic: Detect and correct supply-air
    temperature problems.

    Args:
        timestamp_arr (List[datetime]): timestamps for analysis period.
        sat_stpt_arr (List[float]): supply-air temperature set point
            for analysis period.
        satemp_arr (List[float]): supply-air temperature for analysis period.
        rht_arr (List[float]): terminal box reheat command for analysis period.

    """
    def __init__(self, no_req_data, auto_correct_flag, stpt_allowable_dev,
                 rht_on_thr, high_dmpr_thr, percent_dmpr_thr, percent_rht_thr,
                 min_sat_stpt, sat_retuning, rht_valve_thr, max_sat_stpt,
                 analysis, sat_stpt_cname):
        self.timestamp_arr = []
        self.sat_stpt_arr = []
        self.satemp_arr = []
        self.rht_arr = []
        self.percent_rht = []
        self.percent_dmpr = []
        self.table_key = None
        self.file_key = None
        self.data = {}
        self.dx_table = {}

        # Common RCx parameters
        self.analysis = analysis + '-' + VALIDATE_FILE_TOKEN
        self.sat_stpt_cname = sat_stpt_cname
        self.no_req_data = no_req_data
        self.auto_correct_flag = bool(auto_correct_flag)
        self.stpt_allowable_dev = float(stpt_allowable_dev)
        self.rht_on_thr = float(rht_on_thr)
        self.percent_rht_thr = float(percent_rht_thr)
        self.dgr_sym = u'\N{DEGREE SIGN}'

        # Low SAT RCx thresholds
        self.rht_valve_thr = float(rht_valve_thr)
        self.max_sat_stpt = float(max_sat_stpt)

        # High SAT RCx thresholds
        self.high_dmpr_thr = float(high_dmpr_thr)
        self.percent_dmpr_thr = float(percent_dmpr_thr)
        self.min_sat_stpt = float(min_sat_stpt)
        self.sat_retuning = float(sat_retuning)
        self.token_offset = 30.0

    def reinitialize(self):
        """Reinitialize data arrays."""
        self.table_key = None
        self.file_key = None
        self.timestamp_arr = []
        self.sat_stpt_arr = []
        self.satemp_arr = []
        self.rht_arr = []
        self.percent_rht = []
        self.percent_dmpr = []
        self.data = {}
        self.dx_table = {}

    def sat_rcx(self, current_time, sat_data, sat_stpt_data,
                zone_rht_data, zone_dmpr_data, dx_result):
        """Manages supply-air diagnostic data sets.

        Args:
            current_time (datetime): current timestamp for trend data.
            sat_data (lst of floats): supply-air temperature measurement for
                AHU.
            sat_stpt_data (List[floats]): supply-air temperature set point
                data for AHU.
            zone_rht_data (List[floats]): reheat command for terminal boxes
                served by AHU.
            zone_dmpr_data (List[floats]): damper command for terminal boxes
                served by AHU.
            dx_result (Object): Object for interacting with platform and devices.

        Returns:
            Results object (dx_result) to Application.
            Status of diagnostic (dx_status)

        """
        dx_status = 1
        if check_date(current_time, self.timestamp_arr):
            self.reinitialize()
            dx_status = 0
            return dx_status, dx_result

        tot_rht = sum(1 if val > self.rht_on_thr else 0 for val in zone_rht_data)
        count_rht = len(zone_rht_data)
        tot_dmpr = sum(1 if val > self.high_dmpr_thr else 0 for val in zone_dmpr_data)
        count_damper = len(zone_dmpr_data)

        run_status = check_run_status(self.timestamp_arr, current_time, self.no_req_data)

        if run_status is None:
            dx_result.log('Current analysis data set has insufficient data '
                          'to produce a valid diagnostic result.')
            self.reinitialize()
            dx_status = 0
            return dx_status, dx_result

        if run_status:
            self.table_key = create_table_key(self.analysis, self.timestamp_arr[-1])
            avg_sat_stpt, dx_table = setpoint_control_check(self.sat_stpt_arr,
                                                            self.satemp_arr,
                                                            self.stpt_allowable_dev,
                                                            SA_TEMP_RCX,
                                                            DX, SAT_NAME,
                                                            self.token_offset)
            self.dx_table.update(dx_table)
            dx_result = self.low_sat(dx_result, avg_sat_stpt)
            dx_result = self.high_sat(dx_result, avg_sat_stpt)
            dx_result.insert_table_row(self.table_key, self.dx_table)
            dx_status = 2
            self.reinitialize()

        self.satemp_arr.append(mean(sat_data))
        self.rht_arr.append(mean(zone_rht_data))
        self.sat_stpt_arr.append(mean(sat_stpt_data))
        self.percent_rht.append(tot_rht/count_rht)
        self.percent_dmpr.append(tot_dmpr/count_damper)
        self.timestamp_arr.append(current_time)

        return dx_status, dx_result

    def low_sat(self, dx_result, avg_sat_stpt):
        """Diagnostic to identify and correct low supply-air temperature

        (correction by modifying SAT set point)
        """
        avg_zones_rht = mean(self.percent_rht)*100
        rht_avg = mean(self.rht_arr)
        if rht_avg > self.rht_valve_thr and avg_zones_rht > self.percent_rht_thr:
            if avg_sat_stpt is None:
                # Create diagnostic message for fault
                # when supply-air temperature set point
                # is not available.
                msg = ('The SAT has been detected to be too low but '
                       'but supply-air temperature set point data '
                       'is not available.')
                dx_msg = 43.1
            elif self.auto_correct_flag:
                autocorrect_sat_stpt = avg_sat_stpt + self.sat_retuning
                if autocorrect_sat_stpt <= self.max_sat_stpt:
                    dx_result.command(self.sat_stpt_cname, autocorrect_sat_stpt)
                    sat_stpt = '%s' % float('%.2g' % autocorrect_sat_stpt)
                    msg = ('The SAT has been detected to be too low. '
                           'The SAT set point has been increased to: '
                           '{}{}F'.format(self.dgr_sym, sat_stpt))
                    dx_msg = 41.1
                else:
                    dx_result.command(self.sat_stpt_cname, self.max_sat_stpt)
                    sat_stpt = '%s' % float('%.2g' % self.max_sat_stpt)
                    sat_stpt = str(sat_stpt)
                    msg = (
                        'The supply-air temperautre was detected to be '
                        'too low. Auto-correction has increased the '
                        'supply-air temperature set point to the maximum '
                        'configured supply-air tempeature set point: '
                        '{}{}F)'.format(self.dgr_sym, sat_stpt))
                    dx_msg = 42.1
            else:
                msg = ('The SAT has been detected to be too low but'
                       'auto-correction is not enabled.')
                dx_msg = 44.1
        else:
            msg = ('No problem detected for Low Supply-air '
                   'Temperature diagnostic.')
            dx_msg = 40.0
        self.dx_table.update({SA_TEMP_RCX1 + DX: dx_msg})
        dx_result.log(msg, logging.INFO)
        return dx_result

    def high_sat(self, dx_result, avg_sat_stpt):
        """Diagnostic to identify and correct high supply-air temperature

        (correction by modifying SAT set point)
        """
        avg_zones_rht = mean(self.percent_rht)*100
        avg_zone_dmpr_data = mean(self.percent_dmpr)*100

        if avg_zone_dmpr_data > self.percent_dmpr_thr and avg_zones_rht < self.percent_rht_thr:
            if avg_sat_stpt is None:
                # Create diagnostic message for fault
                # when supply-air temperature set point
                # is not available.
                msg = ('The SAT has been detected to be too high but '
                       'but supply-air temperature set point data '
                       'is not available.')
                dx_msg = 54.1
            elif self.auto_correct_flag:
                autocorrect_sat_stpt = avg_sat_stpt - self.sat_retuning
                # Create diagnostic message for fault condition
                # with auto-correction
                if autocorrect_sat_stpt >= self.min_sat_stpt:
                    dx_result.command(self.sat_stpt_cname, autocorrect_sat_stpt)
                    sat_stpt = '%s' % float('%.2g' % autocorrect_sat_stpt)
                    msg = ('The SAT has been detected to be too high. The '
                           'SAT set point has been increased to: '
                           '{}{}F'.format(self.dgr_sym, sat_stpt))
                    dx_msg = 51.1
                else:
                    # Create diagnostic message for fault condition
                    # where the maximum SAT has been reached
                    dx_result.command(self.sat_stpt_cname, self.min_sat_stpt)
                    sat_stpt = '%s' % float('%.2g' % self.min_sat_stpt)
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
        else:
            msg = ('No problem detected for High Supply-air '
                   'Temperature diagnostic.')
            dx_msg = 50.0
        self.dx_table.update({SA_TEMP_RCX2 + DX: dx_msg})
        dx_result.log(msg, logging.INFO)
        return dx_result


