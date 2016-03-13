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

SA_VALIDATE = 'Supply-air Temperature ACCx'
SA_TEMP_RCX = 'Supply-air Temperature Control Loop Dx'
SA_TEMP_RCX1 = 'Low Supply-air Temperature Dx'
SA_TEMP_RCX2 = 'High Supply-air Temperature Dx'
DX = '/diagnostic message'
ST = 'State'
CORRECT_SAT = 'Suggested SAT setpoint'
DATA = '/data/'


class SupplyTempRcx(object):
    '''Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    supply-air temperature problems.
    '''
    def __init__(self, data_window, no_req_data, auto_correctflag,
                 stpt_allowable_dev, rht_on_thr, high_dmpr_thr, pc_dmpr_thr,
                 pc_rht_thr, min_sat_stpt, sat_retuning, rht_valve_thr,
                 max_sat_stpt, analysis, sat_stpt_cname):
        self.ts = []
        self.sat_stpt_arr = []
        self.satemp_arr = []
        self.rht_arr = []
        self.rht = []
        self.percent_rht = []
        self.percent_dmpr = []

        # Common RCx parameters
        self.analysis = analysis
        self.sat_stpt_cname = sat_stpt_cname
        self.data_window = float(data_window)
        self.no_req_data = no_req_data
        self.auto_correctflag = bool(auto_correctflag)
        self.stpt_allowable_dev = float(stpt_allowable_dev)
        self.rht_on_thr = float(rht_on_thr)
        self.pc_rht_thr = float(pc_rht_thr)
        self.dgr_sym = u'\N{DEGREE SIGN}'

        # Low SAT RCx thresholds
        self.rht_valve_thr = float(rht_valve_thr)
        self.max_sat_stpt = float(max_sat_stpt)

        # High SAT RCx thresholds
        self.high_dmpr_thr = float(high_dmpr_thr)
        self.pc_dmpr_thr = float(pc_dmpr_thr)
        self.min_sat_stpt = float(min_sat_stpt)
        self.sat_retuning = float(sat_retuning)

    def reinitialize(self):
        '''Reinitialize data arrays.'''
        self.ts = []
        self.sat_stpt_arr = []
        self.satemp_arr = []
        self.rht_arr = []
        self.rht = []
        self.percent_rht = []
        self.percent_dmpr = []

    def sat_rcx(self, current_time, sat_data, sat_stpt_data,
                rht_data, zn_dmpr, dx_result,
                sat_override_check, validate):
        '''Check supply-air temperature RCx pre-requisites

        and assemble the supply-air temperature analysis data set.
        '''
        self.satemp_arr.append(np.mean(sat_data))
        self.rht_arr.append(np.mean(rht_data))
        self.sat_stpt_arr.append(np.mean(sat_stpt_data))
        tot_rht = sum(1 if val > self.rht_on_thr else 0 for val in rht_data)
        count_rht = len(rht_data)
        tot_dmpr = sum(1 if val > self.high_dmpr_thr else 0 for val in zn_dmpr)
        count_damper = len(zn_dmpr)

        self.percent_rht.append(tot_rht/count_rht)
        self.percent_dmpr.append(tot_dmpr/count_damper)
        self.ts.append(current_time)
        e_time = self.ts[-1] - self.ts[0]
        e_time = e_time.total_seconds()/60
        e_time = e_time if e_time > 0.0 else 1.0

        data = {}
        for key, value in validate.items():
            tag = SA_VALIDATE + DATA + key
            data.update({tag: value})

        if e_time >= self.data_window and len(self.ts) >= self.no_req_data:
            avg_sat_stpt = np.mean(self.sat_stpt_arr)
            zipper = (self.sat_stpt_arr, self.satemp_arr)
            stpt_tracking = [abs(x - y) for x, y in zip(*zipper)]
            stpt_tracking = np.mean(stpt_tracking)/avg_sat_stpt*100

            if stpt_tracking > self.stpt_allowable_dev:
                msg = ('Supply-air temperature is deviating significantly '
                       'from the supply-air temperature set point.')
                dx_msg = 31.1
                dx_table = {
                    SA_TEMP_RCX + DX: dx_msg
                }
            else:
                msg = 'No problem detected.'
                dx_msg = 30.0
                dx_table = {
                    SA_TEMP_RCX + DX: dx_msg
                }
            dx_result.insert_table_row(self.analysis, dx_table)
            dx_result.log(msg, logging.INFO)
            if e_time > 75:
                dx_result.insert_table_row(self.analysis,
                                           {SA_TEMP_RCX1 + DX: 46.2})
                dx_result.insert_table_row(self.analysis,
                                           {SA_TEMP_RCX2 + DX: 56.2})
                data.update({SA_VALIDATE + DATA + ST: 2})
                dx_result.insert_table_row(self.analysis, data)
                self.reinitialize()
                return dx_result
            dx_result = self.low_sat(dx_result, avg_sat_stpt,
                                     sat_override_check)
            dx_result = self.high_sat(dx_result, avg_sat_stpt,
                                      sat_override_check)
            self.reinitialize()
            data.update({SA_VALIDATE + DATA + ST: 1})
            dx_result.insert_table_row(self.analysis, data)
            return dx_result
        data.update({SA_VALIDATE + DATA + ST: 0})
        dx_result.insert_table_row(self.analysis, data)
        return dx_result

    def low_sat(self, result, avg_sat_stpt, sat_override_check):
        '''Diagnostic to identify and correct low supply-air temperature
        (correction by modifying SAT set point)
        '''
        avg_zones_rht = np.mean(self.percent_rht)*100
        rht_avg = np.mean(self.rht_arr)
        if (rht_avg > self.rht_valve_thr and
                avg_zones_rht > self.pc_rht_thr):
            if avg_sat_stpt is not None and not sat_override_check:
                if self.auto_correctflag:
                    if avg_sat_stpt <= self.max_sat_stpt:
                        sat_stpt = avg_sat_stpt + self.sat_retuning
                        result.command(self.sat_stpt_cname, sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % sat_stpt)
                        msg = ('The SAT has been detected to be too low. '
                               'The SAT set point has been increased to: '
                               '{}{drg}F'.format(self.dgr_sym, sat_stpt))
                        dx_msg = 41.1
                    else:
                        result.command(self.sat_stpt_cname,
                                       self.max_sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % self.max_sat_stpt)
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
            dx_msg = 40.0
        dx_table = {
            SA_TEMP_RCX1 + DX: dx_msg
        }
        result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result

    def high_sat(self, result, avg_sat_stpt, sat_override_check):
        '''Diagnostic to identify and correct high supply-air temperature

        (correction by modifying SAT set point)
        '''
        avg_zones_rht = np.mean(self.percent_rht)*100
        avg_zn_dmpr = np.mean(self.percent_dmpr)*100

        if avg_zn_dmpr > self.pc_dmpr_thr and avg_zones_rht < self.pc_rht_thr:
            if avg_sat_stpt is not None and not sat_override_check:
                if self.auto_correctflag:
                    sat_stpt = avg_sat_stpt - self.sat_retuning
                    # Create diagnostic message for fault condition
                    # with auto-correction
                    if sat_stpt >= self.min_sat_stpt:
                        result.command(self.sat_stpt_cname, sat_stpt)
                        sat_stpt = '%s' % float('%.2g' % sat_stpt)
                        msg = ('The SAT has been detected to be too high. The '
                               'SAT set point has been increased to: '
                               '{}{}F'.format(self.dgr_sym, sat_stpt))
                        dx_msg = 51.1
                    else:
                        # Create diagnostic message for fault condition
                        # where the maximum SAT has been reached
                        result.command(
                            self.sat_stpt_cname, self.min_sat_stpt)
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
            dx_msg = 50.0
        dx_table = {
            SA_TEMP_RCX2 + DX: dx_msg
        }
        result.insert_table_row(self.analysis, dx_table)
        result.log(msg, logging.INFO)
        return result
