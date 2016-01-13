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
'''
'''
This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed
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
import math
import calendar
from datetime import timedelta as td, datetime as dt
import sys
import logging
import csv
import dateutil.parser
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
logging.captureWarnings(True)
 
def passiveafdd(config_path, **kwargs):
    '''Passive fault detection application for AHU/RTU economizer systems'''
    config = utils.load_config(config_path)
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
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
            self.cooling_status = []
            self.heating_status = []
            self.oa_damper= []
            self.fan_status= []
            self.data_status = {}
            self.first_data_scrape = True
            # supported economizer types.
            self.economizer_type = config.get("economizer type", "differential_ddb").lower()
            self.economizer_types = ['differential_ddb', 'highlimit']

            # Temperature sensor diagnostic thresholds
            self.mat_low = float(config.get("mat_low", 50.0))
            self.mat_high = float(config.get("mat_high", 90.0))
            self.oat_low = float(config.get("oat_low", 30.0))
            self.oat_high = float(config.get("oat_high", 120.0))
            self.rat_low = float(config.get("rat_low", 50.0))
            self.rat_high = float(config.get("rat_high", 90.0))
            self.temp_sensor_threshold = float(config.get("temperature_sensor_threshold", 5.0))
            self.uncertainty_band = config.get('uncertainty deadband', 2.5)
 
            # Economizer diagnostic thresholds and parameters
            self.high_limit = float(config.get("high_limit", 60.0))
            self.oa_damper_minimum = float(config.get("minimum oad command", 15.0))
            self.minimum_oa = float(config.get("minimum oa", 10.0))
            self.oae2_damper_threshold = float(config.get("oae2_damper_threshold", 30.0))
            self.oae2_oaf_threshold = float(config.get("oae2_oaf_threshold", 25.0))
            self.oae4_oaf_threshold = float(config.get("oae4_oaf_threshold", 25.0))
            self.oae5_oaf_threshold = float(config.get("oae5_oaf_threshold", 0))
            self.damper_deadband = config.get("oad uncertainty band", 10.0)
 
            # RTU rated parameters (e.g., capacity)
            self.eer = float(config.get("EER", 10))
            tonnage = float(config.get("tonnage"))
            if tonnage:
                self.cfm = 300*tonnage
            self.csv_input = config.get('csv_input', False)
 
            # Point names for input file (CSV) or BACnet config
            self.timestamp_name = config.get('timestamp_name')
            self.input_file = config.get('input_file', 'CONFIG_ERROR')
 
            # Misc. data configuration parameters
            self.sampling_rate = config.get('sampling_rate')
            self.mat_missing = config.get('mixed_air_sensor_missing', False)
           
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
            # Initialize final data arrays used during diagnostics
            self.status_list = config.get("status list")
            self.data_status = self.data_status.fromkeys(self.status_list, None)
            print self.data_status
            if self.csv_input:
                self.file = config['input file']
            self.data_array = None
       
        @Core.receiver("onstart")
        def startup(self, sender, **kwargs):
            if self.csv_input:
                import pandas
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
            if self.file_path == '':
                _log.error('No csv file not found ...')
                raise Exception
            if(not os.path.isfile(input_file)):
                raise Exception
            _, filextension = os.path.splitext(file_path)
            if filextension != '.csv' and filextension != '':
                _log.error('Input file must be a csv.')
                raise Exception
            bldg_data = read_oae_pandas(self.file_path, data_tags)
            return bldg_data
 
        def read_oae_pandas(input_file, data_tags):
            '''Parse metered data for RTU or AHU and provide to diagnostic algorithms.
 
            Uses panda library to efficiently parse the csv data and returns a
            panda time-serires.
            '''
            data = pandas.read_csv(mainFileFullName, error_bad_lines=False, sep=',')
            data = data.dropna()
            return data
 
        def process_file_data(device_data):
            data = {}
            for index, row in device_data.iterrows():
                data[self.oatemp_name] = row[self.oatemp_name]
                data[self.ratemp_name] = row[self.ratemp_name]
                data[self.matemp_name] = row[self.matemp_name]
 
                data[self.coooling_name] = row[self.cooling_name]
                data[self.heating_name] = row[self.heating_name]
                self.check_device_status(data)
                self.update_device_status(data)
                
        def new_data(self, peer, sender, bus, topic, headers, message):
            '''Generate static configuration inputs for
 
            priority calculation.
            '''
            _log.info('Data Received')
            device_data = message[0]
            if self.first_data_scrape:
                for key in self.data_status:
                    self.data_status[key] = message[key]
                self.first_data_scrape = False
                return
            self.check_device_status(device_data)
            self.update_device_status(device_data)
 
        def check_device_status(device_data):
            for key, value in self.data_status.items():
                if device_data[key] != value:
                    self.run_diagnostics()
                    break
            self.data_collector(device_data)
       
        def update_device_status(device_data):
            for key, value in data_status.items():
                self.data_status[key] = device_data[key]
 
        def data_collector(device_data):
            self.oatemp.append(device_data[self.oatemp_name])
            self.ratemp.append(device_data[self.ratemp_name])
            self.matemp.append(device_data[self.matemp_name])
            self.oa_damper.append(device_data[self.oa_damper_name])
            self.cooling.append(device_data[self.cooling_name])
            self.heating.append(device_data[self.heating_name])
 
        def run_diagnostics():
            oatemp = sum(self.oatemp)/len(self.oatemp)
            matemp = sum(self.matemp)/len(self.matemp)
            ratemp = sum(self.ratemp)/len(self.oatemp)
            oa_damper = sum(self.oa_damper)/len(self.oa_damper)
            cooling = max(self.cooling)
            heating = max(self.heating)
            fan_status = max(self.fan_status)

            self.reinit()

            if self.fan_status:
                try:
                    oaf = (oatemp -ratemp)/(ratemp - matemp)*100.0
                except:
                    oaf = None
                _log.info('Performing Diagnostic')
                oae_1 = self.sensor_diagnostic(cooling, heating, matemp, ratemp, oatemp)
                oae_2 = self.economizer_diagnostic1(oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf)
                oae_3 = self.economizer_diagnostic2(oatemp, ratemp, cooling, oa_damper)
                oae_4 = self.excess_oa_intake(oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf)
                oae_5 = self.insufficient_ventilation(oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf)
                oae_6 = self.schedule_diagnostic()
            else:
                return 19, 29, 39, 49, 59, 
            # return oae1_result, oae2_result, oae3_result, oae4_result oae5_result, oae6_result, energy_impact
#             energy_impact = self.calculate_energy_impact(oae_2, oae_3, oae_4)
#             contents = [self.timestamp, oae_1, oae_2, oae_3, oae_4, oae_5,
#                         oae_6, energy_impact, self.oaf]
#             result_writer(contents)
            _log.info('Processing Done!')
 
        def reinit():
            self.oatemp = []
            self.ratemp = []
            self.matemp = []
            self.oa_damper = []
            self.cooling = []
            self.heating = []
 
        def sensor_diagnostic(cooling, heating, matemp, ratemp, oatemp):
            '''RTU temperature sensor diagnostic.'''
            if (bool(self.matemp_missing) and cooling) or heating:
                return 22
            if matemp < self.mat_low or matemp > self.mat_high:
                return 23
            if ratemp < self.rat_low or ratemp > self.rat_high:
                return 24
            if oatemp < self.oat_low or oatemp > self.oat_high:
                return 25
            if (matemp - ratemp > self.temp_sensor_threshold and
                    matemp- oatemp> self.temp_sensor_threshold):
                return 21
            if (matemp - ratemp > self.temp_sensor_threshold and
                    oatemp- matemp > self.temp_sensor_threshold):
                return 21
            return 20       
 
        def economizer_diagnostic1(self, oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf):
            # unit is not cooling.
            if not cooling:
                return 31

            # econmozier_type is not properly configured.
            if self.economizer_type not in self.economizer_types:
                return 31

            if self.economizer_type == 'differential_ddb':
                # Outdoor conditions are not conducive to diagnostic.
                if ratemp - oatemp < self.uncertainty_band:
                    return 31

            if self.economizer_type == 'highlimit':
                # Outdoor conditions are not conducive to diagnostic.
                if self.high_limit - oatemp < self.uncertainty_band:
                    return 31

            # Outdoor damper is not open fully to utilize economizing.
            if 100.0 - oa_damper > self.oae2_damper_threshold:
                return 33

            # OAT and RAT  are too close for conclusive diagnostic.
            if math.fabs(oatemp - ratemp) < self.tempereature_diff_requirement:
                return 36

            # MAT sensor is not measured and mechanical cooling or heating is active.
            if self.matemp_missing and (compressor or compressor == None):
                return 38

            # OAF calculation resulted in an unexpected value.
            if oaf == None or oaf < -0.1 or oaf > 1.25:
                return 38

            # OAF is too low.
            if 100.0 - oaf > self.oae2_oaf_threshold:
                return 32
            return 30
 
        def economizer_diagnostic2(self, oatemp, ratemp, cooling, oa_damper):
            if cooling:
                if self.economizer_type not in self.economizer_types:
                    return 44
                if self.economizer_type == 'differential_ddb':
                    if oatemp - ratemp < self.uncertainty_band:
                        return 43
                if self.economizer_type == 'highlimit':
                    if oatemp - self.hightlimit < self.uncertainty_band:
                        return 43
            if oa_damper > self.oa_damper_minimum*1.25:
                return 41
            return 40
 
        def excess_oa_intake(self, oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf):
            if cooling:
            # econmozier_type is not properly configured.
                if self.economizer_type not in self.economizer_types:
                    return 54

                if self.economizer_type == 'differential_ddb':
                    # Outdoor conditions are not conducive to diagnostic.
                    if oatemp - ratemp < self.uncertainty_band:
                        return 56
                if self.economizer_type == 'highlimit':
                    # Outdoor conditions are not conducive to diagnostic.
                    if oatemp - self.high_limit < self.uncertainty_band:
                        return 56

            # Outdoor damper is not open fully to utilize economizing.      return 31
            if oa_damper > self.oa_damper_minimum*1.25:
                return 53

            # OAT and RAT  are too close for conclusive diagnostic.
            if math.fabs(oatemp - ratemp) < self.tempereature_diff_requirement:
                return 52

            # MAT sensor is not measured and mechanical cooling or heating is active.
            if self.matemp_missing and ((compressor or heating) or compressor == None):
                return 52

            oaf = calculate_oaf()
            # OAF calculation resulted in an unexpected value.
            if oaf == None or oaf < -0.1 or oaf > 1.25:
                return 58
            
            # Unit is brining in excess OA.
            if oaf > self.minimum_oa*1.25:
                return 51

            # No problems detected.
            return 50
                            
 
        def insufficient_ventilation(self, oatemp, ratemp, matemp, cooling, compressor, oa_damper, oaf):
            oae5_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if int(self.fan_status[points]):
                        if (self.cooling[points] != -99 and
                           self.oaf[points] != -99 and
                           self.damper[points] != -99):
                            if (self.damper_minimum - self.damper[points] <=
                                    self.damper_deadband):
                                if ((math.fabs(self.oatemp[points] -
                                               self.ratemp[points]) > 5.0) and
                                   not self.matemp_missing):
                                    if ((self.minimum_oa - self.oaf[points]) >
                                        self.oae5_oaf_threshold and
                                       self.oaf[points] > 0 and
                                       self.oaf[points] < 1.25):
                                        # Unit is bringing in insufficient
                                        # OA (Fault)
                                        oae5_result.append(61)
                                    elif (
                                        self.minimum_oa - self.oaf[points] <
                                        self.oae5_oaf_threshold and
                                        self.oaf[points] > 0 and
                                            self.oaf[points] < 1.25):
                                        # No problem detected.
                                        oae5_result.append(60)
                                    else:
                                        # Unexpected result for OAF calculation
                                        # (No Fault)
                                        oae5_result.append(68)
                                elif (math.fabs(self.oatemp[points] -
                                                self.ratemp[points]) > 5.0 and
                                      self.matemp_missing and not
                                      int(self.cooling[points]) and
                                      int(self.heating[points])):
                                    if ((self.minimum_oa - self.oaf[points]) >
                                        self.oae5_oaf_threshold and
                                       self.oaf[points] > 0 and
                                       self.oaf[points] < 1.25):
                                        oae5_result.append(61)
                                    # Insufficient OA (Fault)
                                    elif ((self.minimum_oa -
                                           self.oaf[points]) <
                                          self.oae5_oaf_threshold and
                                          self.oaf[points] > 0 and
                                          self.oaf[points] < 1.25):
                                        oae5_result.append(60)  # No Fault
                                    else:
                                        # Unexpected result for OAF calculation
                                        # (No Fault).
                                        oae5_result.append(68)
                                else:
                                    # Conditions are not favorable for
                                    # OAF calculation (No Fault).
                                    oae5_result.append(62)
                            else:
                                # Damper is significantly below the minimum
                                # damper set point (Fault)
                                oae5_result.append(63)
                        else:
                            # Missing required data (No fault)
                            oae5_result.append(67)
                    else:
                        # Unit is off (No fault).
                        oae5_result.append(69)
                else:
                    oae5_result.append(67)  # Missing data (No Fault)
            return oae5_result
 
        def schedule_diagnostic(self):
            oae6_result = []
            for points in xrange(0, self.newdata):
                if (self.fan_status[points] != -99 and
                   self.cooling[points] != -99):
                    if (int(self.fan_status[points]) or
                       int(self.cooling[points])):
                        day = self.timestamp[points].weekday()
                        sched = self.schedule_dict[day]
                        start = int(sched[0])
                        end = int(sched[1])
                        if (self.timestamp[points].hour < start or
                           self.timestamp[points].hour > end):
                            oae6_result.append(71)
                        else:
                            oae6_result.append(70)
                    else:
                        oae6_result.append(70)
                else:
                    oae6_result.append(77)
            return oae6_result
 
        def calculate_energy_impact(self, oae_2, oae_3, oae_4):
            energy_impact = []
            month_abbr = {k: v for k, v in enumerate(calendar.month_abbr)}
            if not self.matemp_missing:
                for points in xrange(0, self.newdata):
                    if oae_2[points] == 32 or oae_2[points] == 33:
                        energy_impact.append(
                            1.08*self.cfm*(self.matemp[points] -
                                           self.oatemp[points]) /
                            (1000*self.eer))
                    elif (oae_3[points] == 41 or oae_4[points] == 51 or
                          oae_4[points] == 53 and
                          self. oatemp[points] > self.matemp[points]):
                        ei = 1.08*self.cfm/(1000*self.eer)
                        ei = ei*(self.matemp[points] - (self.oatemp[points] *
                                                        self.minimum_oa +
                                                        self.ratemp[points] *
                                                        (1 - self.minimum_oa)))
                        energy_impact.append(ei)
                    elif (oae_3[points] == 41 or oae_4[points] == 51 or
                          oae_4[points] == 53 and
                          self. oatemp[points] > self.matemp[points]):
                        ei = (1.08*(
                            self.oatemp[points]*self.minimum_oa +
                            self.ratemp[points]*(1 - self.minimum_oa)) -
                            self.cfm*(self.matemp[points])/(1000*self.eer))
                        energy_impact.append(ei)
                    else:
                        energy_impact.append(0)
                    if energy_impact[points] < 0:
                        energy_impact[points] = 0
            return energy_impact
 
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
