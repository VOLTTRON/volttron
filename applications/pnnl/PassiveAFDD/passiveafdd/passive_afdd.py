# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
import math
import datetime
from datetime import timedelta as td, datetime as dt
import sys
from os.path import join, basename, splitext, isdir, isfile
from os import makedirs
import logging
import csv
import dateutil.parser
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from collections import OrderedDict
__version__ = "2.0.0"
NO_TREND = ['not measured', 'none']


def passiveafdd(config_path, **kwargs):
    '''Passive fault detection application for AHU/RTU economizer systems'''
    config = utils.load_config(config_path)
    rtu_path = OrderedDict((key, config[key])
                           for key in ['campus', 'building', 'unit'])
    rtu_tag = ''
    for key in rtu_path:
        rtu_tag += rtu_path[key] + '-'
    device_topic = topics.DEVICES_VALUE(**rtu_path) + '/all'
    utils.setup_logging()
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')

    class PassiveAFDD(Agent):

        def __init__(self, **kwargs):
            '''Input and initialize user configurable parameters.'''
            super(PassiveAFDD, self).__init__(**kwargs)
            # Agent Configuration parameters
            self.agent_id = config.get('agentid', 'passiveafdd')
            self.matemp = []
            self.oatemp = []
            self.ratemp = []
            self.cool_call = []
            self.compressor_status = []
            self.heating_status = []
            self.oa_damper = []
            self.fan_status = []
            self.timestamp = []
            self.data_status = {}
            self.first_data_scrape = True
            self.cool_call_measured = True

            # supported economizer types.
            self.economizer_type = config.get('economizer type',
                                              'differential_ddb').lower()
            self.economizer_types = ['differential_ddb', 'highlimit']

            # Temperature sensor diagnostic thresholds
            self.mat_low = float(config.get('mat_low', 50.0))
            self.mat_high = float(config.get('mat_high', 90.0))
            self.oat_low = float(config.get('oat_low', 30.0))
            self.oat_high = float(config.get('oat_high', 120.0))
            self.rat_low = float(config.get('rat_low', 50.0))
            self.rat_high = float(config.get('rat_high', 90.0))
            self.temp_sensor_threshold = float(config.get('temperature sensor threshold', 5.0))
            self.uncertainty_band = config.get('uncertainty deadband', 2.5)

            # Economizer diagnostic thresholds and parameters
            self.high_limit = float(config.get('high_limit', 60.0))
            self.min_oa_damper = float(config.get('minimum oad command', 15.0))
            self.minimum_oa = float(config.get('minimum oa', 10.0))
            self.oae2_damper_threshold = float(config.get('oae2_damper_threshold', 30.0))
            self.temperature_diff_requirement = float(config.get('temperature difference requirement', 5.0))
            self.oae2_oaf_threshold = float(config.get('oae2_oaf_threshold', 25.0))
            self.oae4_oaf_threshold = float(config.get('oae4_oaf_threshold', 25.0))
            self.oae5_oaf_threshold = float(config.get('oae5_oaf_threshold', 0))
            self.damper_deadband = config.get('oad uncertainty band', 10.0)

            data_pts = config['points']
            self.oatemp_name = data_pts['oat_point_name']
            self.ratemp_name = data_pts['rat_point_name']
            self.oa_damper_name = data_pts['damper_point_name']
            self.fan_status_name = data_pts['fan_status_point_name']
            self.matemp_name = data_pts.get('mat_point_name', 'not measured')
            self.timestamp_name = data_pts.get('timestamp_name', 'Date')
            self.cool_call_name = data_pts['cool_call_point_name']

            self.cool_cmd_name = data_pts['cool_cmd_point_name']
            if self.cool_call_name.lower() == 'not measured':
                if self.cool_cmd_name.lower() == 'not measured':
                    _log.debug('One cooling status point must be '
                               'available for diagnostics.')
                    sys.exit()
                self.cool_call_name = self.cool_cmd_name
                self.cool_call_measured = False

            self.heat_cmd_name = data_pts['heat_cmd_point_name']
            self.data_pts = data_pts.values()

            # RTU rated parameters (e.g., capacity)
            self.eer = float(config.get('EER', 10))
            tonnage = float(config.get('tonnage'))
            if tonnage:
                self.cfm = 300*tonnage

            self.csv_input = config.get('csv_input', False)

            # Misc. data configuration parameters
            mat_missing = config.get('mat not measured'.lower(), [False, ''])
            if mat_missing and self.cool_cmd_name.lower() == 'not measured':
                _log.debug('If the mixed-air temperature is not measured then '
                           'the units compressor command must be available.')
                sys.exit()
            if mat_missing and self.heat_cmd_name.lower() == 'not measured':
                _log.debug('If the mixed-air temperature is not measured then '
                           'the units heat command must to run diagnostic')
            if mat_missing[0]:
                try:
                    self.matemp_name = mat_missing[1]
                except:
                    _log.debug('If the mixed-air temperature is not '
                               'specified the discharge-air temperature '
                               'must be available or the diagnostic '
                               'cannot proceed.')
                    sys.exit()
            self.matemp_missing = mat_missing[0]

            if self.heat_cmd_name.lower() in NO_TREND:
                self.heat_cmd_name = False
            if self.cool_cmd_name.lower() in NO_TREND:
                self.heat_cmd_name = False

            # Device occupancy schedule
            sunday = config.get('Sunday')
            monday = config.get('Monday')
            tuesday = config.get('Tuesday')
            wednesday = config.get('Wednesday')
            thursday = config.get('Thursday')
            friday = config.get('Friday')
            saturday = config.get('Saturday')
            self.schedule_dict = dict({0: sunday, 1: monday, 2: tuesday,
                                       3: wednesday, 4: thursday, 5: friday,
                                       6: saturday})

            # Create status list to that determines RTU mode of operation.
            self.status_lst = config.get('status list')
            self.data_status = self.data_status.fromkeys(self.status_lst, None)

            input_file_name = ''
            if self.csv_input:
                self.input_file = config['input file']
                input_file_name = basename(splitext(self.input_file)[0])
            results_file_name = rtu_tag + '-' + input_file_name

            output_directory = config.get('results directory', __file__)
            if not isdir(output_directory):
                try:
                    makedirs(output_directory)
                except:
                    _log.debug('Cannot create results directory, '
                               'check user permissions.')
                    sys.exit()
            i = 0
            now = datetime.date.today()
            file_path = join(output_directory, results_file_name + '({ts}).csv'.format(ts=now))
            while isfile(file_path):
                i += 1
                file_path = join(output_directory, results_file_name + '({})-{}.csv'.format(now, i))
            self.result_file_path = file_path

        @Core.receiver('onstart')
        def startup(self, sender, **kwargs):
            '''Startup method.'''
            if self.csv_input:
                device_data = self.run_from_csv()
                self.process_file_data(device_data)
                return

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=device_topic,
                                      callback=self.new_data)

        def run_from_csv(self):
            '''Enter location for the data file if using text csv.
            Entry can be through file entry window using TKinter or
            through configuration file as input_file.
            '''
            if not self.input_file:
                _log.error('No csv file not found ...')
                raise Exception
            print self.input_file

            if(not isfile(self.input_file)):
                raise Exception

            _, filextension = splitext(self.input_file)
            if filextension != '.csv' and filextension != '':
                _log.error('Input file must be a csv.')
                raise Exception

            bldg_data = self.read_oae_pandas()
            return bldg_data

        def read_oae_pandas(self):
            '''Parse metered data for RTU or AHU and provide to diagnostic algorithms.
            Uses panda library to efficiently parse the csv data and returns a
            panda time-series.
            '''
            import pandas
            data = pandas.read_csv(self.input_file,
                                   error_bad_lines=False,
                                   sep=',')
            data = data.dropna()
            return data

        def process_file_data(self, device_data):
            '''Format parsed data from csv file.'''
            data = {}
            for _, row in device_data.iterrows():
                data[self.fan_status_name] = row[self.fan_status_name]
                data[self.oatemp_name] = row[self.oatemp_name]
                data[self.ratemp_name] = row[self.ratemp_name]
                data[self.matemp_name] = row[self.matemp_name]
                data[self.oa_damper_name] = row[self.oa_damper_name]
                data[self.cool_call_name] = row[self.cool_call_name]
                data[self.timestamp_name] = dateutil.parser.parse(row[self.timestamp_name])

                if self.cool_cmd_name:
                    data[self.cool_cmd_name] = row[self.cool_cmd_name]
                if self.heat_cmd_name:
                    data[self.heat_cmd_name] = row[self.heat_cmd_name]

                if self.first_data_scrape:
                    for key in self.data_status:
                        self.data_status[key] = data[key]
                    self.first_data_scrape = False

                self.check_device_status(data)
                self.update_device_status(data)

        def new_data(self, peer, sender, bus, topic, headers, message):
            '''Receive real-time device data.'''
            _log.info('Data Received')
            data = message[0]
            _log.info(data)

            if self.first_data_scrape:
                for key in self.data_status:
                    self.data_status[key] = data[key]
                self.first_data_scrape = False

            current_time_stamp = dateutil.parser.parse(headers['Date'])
            data.update({self.timestamp_name: current_time_stamp})

            self.check_device_status(data)
            self.update_device_status(data)

        def check_device_status(self, device_data):
            '''Check if the device status has changed from last measurement.'''
            for key, value in self.data_status.items():
                if device_data[key] != value or (self.timestamp and device_data[self.timestamp_name].hour != self.timestamp[-1].hour):
                    self.run_diagnostics()
                    break
            self.data_collector(device_data)

        def update_device_status(self, device_data):
            '''Update the device status (cooling, heating, ventilating.'''
            for key, _ in self.data_status.items():
                self.data_status[key] = device_data[key]

        def data_collector(self, device_data):
            '''Store data by state and timestamp.'''
            self.oatemp.append(device_data[self.oatemp_name])
            self.ratemp.append(device_data[self.ratemp_name])
            self.matemp.append(device_data[self.matemp_name])
            self.oa_damper.append(device_data[self.oa_damper_name])
            self.cool_call.append(device_data[self.cool_call_name])
            self.fan_status.append(device_data[self.fan_status_name])
            self.timestamp.append(device_data[self.timestamp_name])

            if self.heat_cmd_name:
                self.heating_status.append(device_data[self.heat_cmd_name])
            if self.cool_cmd_name:
                self.compressor_status.append(device_data[self.cool_cmd_name])

        def run_diagnostics(self):
            '''Use aggregated data to run diagnostics.'''
            oatemp = sum(self.oatemp)/len(self.oatemp)
            matemp = sum(self.matemp)/len(self.matemp)
            ratemp = sum(self.ratemp)/len(self.ratemp)
            oa_damper = sum(self.oa_damper)/len(self.oa_damper)
            cooling = max(self.cool_call)
            heating = max(self.heating_status) if self.heating_status else False
            compressor = max(self.compressor_status) if self.compressor_status else False
            fan_status = max(self.fan_status)
            beginning = self.timestamp[0]
            end = self.timestamp[-1]
            try:
                if fan_status:
                    oaf = [(m - r)/(o - r) for o, r, m in zip(self.oatemp,
                                                              self.ratemp,
                                                              self.matemp)]
                    oaf = sum(oaf)/len(oaf)*100.0
                else:
                    oaf = 'OFF'
            except:
                oaf = None
            self.reinit()
            _log.info('Performing Diagnostic')
            oae_1 = self.sensor_diagnostic(cooling, heating, matemp, ratemp, oatemp) if fan_status else 29
            oae_2 = self.economizer_diagnostic1(oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf) if fan_status else 39
            oae_3 = self.economizer_diagnostic2(oatemp, ratemp, cooling, oa_damper) if fan_status else 49
            oae_4 = self.excess_oa_intake(oatemp, ratemp, matemp, cooling, compressor, heating, oa_damper, oaf) if fan_status else 59
            oae_5 = self.insufficient_ventilation(oatemp, ratemp, matemp, cooling, compressor, heating, oa_damper, oaf) if fan_status else 69
            oae_6 = self.schedule_diagnostic(cooling, fan_status, end)
            energy_impact = self.calculate_energy_impact(oae_2, oae_3, oae_4, oatemp, ratemp, matemp) if fan_status else 'OFF'
            if oaf != 'OFF':
                if oaf < 0:
                    oaf = 0 if oaf > -5 else 'inconclusive'
                if oaf > 100:
                    oaf = 100 if oaf < 115 else 'inconclusive'
            results = [beginning, end, oae_1, oae_2, oae_3,
                       oae_4, oae_5, oae_6, energy_impact, oaf]
            _log.debug('results: {}'.format(results))
            self.result_writer(results)

        def reinit(self):
            self.oatemp = []
            self.ratemp = []
            self.matemp = []
            self.oa_damper = []
            self.cool_call = []
            self.heating_status = []
            self.compressor_status = []
            self.timestamp = []
            self.fan_status = []
            self.first_data_scrape = True
            self.data_status = self.data_status.fromkeys(self.status_lst, None)

        def sensor_diagnostic(self, cooling, heating, matemp, ratemp, oatemp):
            '''RTU temperature sensor diagnostic.'''
            # RAT sensor outside of expected operating range.
            if ratemp < self.rat_low or ratemp > self.rat_high:
                return 24

            # OAT sensor outside of expected operating range.
            if oatemp < self.oat_low or oatemp > self.oat_high:
                return 25

            # Conditions not favorable for diagnostic.
            if self.matemp_missing and (cooling or heating):
                return 22

            # MAT sensor outside of expected operating range.
            if matemp < self.mat_low or matemp > self.mat_high:
                return 23

            # Temperature sensor problem detected.
            if (matemp - ratemp > self.temp_sensor_threshold and
                    matemp - oatemp > self.temp_sensor_threshold):
                return 21

            # Temperature sensor problem detected.
            if (ratemp - matemp > self.temp_sensor_threshold and
                    oatemp - matemp > self.temp_sensor_threshold):
                return 21

            return 20

        def economizer_diagnostic1(self, oatemp, ratemp, matemp, cooling,
                                   compressor, oa_damper, oaf):
            # unit is not cooling.
            if not cooling:
                return 31

            # economizer_type is not properly configured.
            if self.economizer_type not in self.economizer_types:
                return 32

            if self.economizer_type == 'differential_ddb':
                # Outdoor conditions are not conducive to diagnostic.
                if ratemp - oatemp < self.uncertainty_band:
                    return 33

            if self.economizer_type == 'highlimit':
                # Outdoor conditions are not conducive to diagnostic.
                if self.high_limit - oatemp < self.uncertainty_band:
                    return 33

            # Outdoor damper is not open fully to utilize economizing.
            if 100.0 - oa_damper > self.oae2_damper_threshold:
                return 34

            # OAT and RAT  are too close for conclusive diagnostic.
            if math.fabs(oatemp - ratemp) < self.temperature_diff_requirement:
                return 35

            # MAT sensor is not measured and mechanical cooling is ON.
            # OA damper is open for economizing (NF).
            if self.matemp_missing and compressor:
                return 35

            # OAF calculation resulted in an unexpected value.
            if oaf is None or oaf < - 0.1 or oaf > 125:
                return 36

            # OAF is too low.
            if 100.0 - oaf > self.oae2_oaf_threshold:
                return 32
            return 30

        def economizer_diagnostic2(self, oatemp, ratemp, cooling, oa_damper):
            '''Unit is cooling.'''
            if cooling or not self.cool_call_measured:
                if self.economizer_type not in self.economizer_types:
                    return 41

                if self.economizer_type == 'differential_ddb':
                    if oatemp - ratemp < self.uncertainty_band:
                        return 42

                if self.economizer_type == 'highlimit':
                    if oatemp - self.hightlimit < self.uncertainty_band:
                        return 42

            if oa_damper > self.min_oa_damper*1.25:
                return 43

            return 40

        def excess_oa_intake(self, oatemp, ratemp, matemp, cooling,
                             compressor, heating, oa_damper, oaf):
            if cooling or not self.cool_call_measured:
                # econmozier_type is not properly configured.
                if self.economizer_type not in self.economizer_types:
                    return 51

                if self.economizer_type == 'differential_ddb':
                    # Outdoor conditions are not conducive to diagnostic.
                    if oatemp - ratemp < self.uncertainty_band:
                        return 52

                if self.economizer_type == 'highlimit':
                    # Outdoor conditions are not conducive to diagnostic.
                    if oatemp - self.high_limit < self.uncertainty_band:
                        return 52

            # Outdoor damper is not open fully to utilize economizing.
            if oa_damper > self.min_oa_damper*1.25:
                return 53

            # OAT and RAT  are too close for conclusive diagnostic.
            if math.fabs(oatemp - ratemp) < self.temperature_diff_requirement:
                return 54

            # MAT sensor is not measured and mechanical cooling/heating is ON.
            if self.matemp_missing and (compressor or heating):
                return 54

            # OAF calculation resulted in an unexpected value.
            if oaf is None or oaf < -0.1 or oaf > 125:
                return 55

            # Unit is brining in excess OA.
            if oaf > self.minimum_oa*1.25:
                return 56

            # No problems detected.
            return 50

        def insufficient_ventilation(self, oatemp, ratemp, matemp, cooling,
                                     compressor, heating, oa_damper, oaf):
            # Damper is significantly below the minimum damper set point (F).
            if self.min_oa_damper - oa_damper > self.damper_deadband:
                return 61

            # Conditions are not favorable for OAF calculation (No Fault).
            if math.fabs(oatemp - ratemp) < self.temperature_diff_requirement:
                return 62

            # Unexpected result for OAF calculation (No Fault).
            if oaf is None or oaf < -0.1 or oaf > 125:
                return 68

            # MAT sensor is not measured and mechanical cooling/heating is ON.
            if self.matemp_missing and (compressor or heating):
                return 62

            # Unit is bringing in insufficient OA (Fault)
            if self.minimum_oa - oaf > self.oae5_oaf_threshold:
                return 61

            return 60

        def schedule_diagnostic(self, cooling, fan_status, end_time):
            '''Simple Schedule diagnostic.'''
            if cooling or fan_status:
                day = end_time.weekday()
                sched = self.schedule_dict[day]
                start = int(sched[0])
                end = int(sched[1])
                if end_time.hour < start or end_time.hour > end:

                    return 71
            return 70

        def calculate_energy_impact(self, oae_2, oae_3, oae_4, oatemp, ratemp, matemp):
            '''Estimate energy impact.'''
            energy_impact = None

            if oae_2 == 32 or oae_2 == 33 and matemp > oatemp:
                energy_impact = (1.08*self.cfm*(matemp - oatemp)/(1000*self.eer))

            if oae_3 == 41 or oae_4 == 51 or oae_4 == 53 and oatemp > matemp:

                ei = 1.08*self.cfm/(1000*self.eer)
                ei = ei*(matemp - (oatemp*self.minimum_oa + ratemp*(1 - self.minimum_oa)))
                energy_impact = ei if ei > energy_impact else energy_impact

            if energy_impact is None or energy_impact < 0:
                energy_impact = 'inconclusive'
            return energy_impact

        def result_writer(self, contents):
            '''Data is aggregated into hourly or smaller intervals based on compressor
            status, heating status, and supply fan status for analysis.
            result_writer receives the diagnostic results and associated energy
            impact and writes the values to csv.
            '''
            try:
                if not isfile(self.result_file_path):
                    ofile = open(self.result_file_path, 'a+')
                    outs = csv.writer(ofile, dialect='excel')
                    writer = csv.DictWriter(ofile, fieldnames=['Beginning',
                                                               'End', 'OAE1',
                                                               'OAE2', 'OAE3',
                                                               'OAE4', 'OAE5',
                                                               'OAE6',
                                                               'Energy_Impact',
                                                               'OAF'],
                                            delimiter=',')
                    writer.writeheader()
                else:
                    ofile = open(self.result_file_path, 'a+')
                outs = csv.writer(ofile, dialect='excel')
                outs.writerow(contents)
                ofile.close()
            except IOError:
                print('Output error please close results file and rerun.')
                return

    return PassiveAFDD(**kwargs)


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(passiveafdd)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
