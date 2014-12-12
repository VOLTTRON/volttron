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
   
import numpy
import math
import calendar
import datetime
import sys
import os
import logging
import itertools
import inspect
import csv
   
logging.captureWarnings(True)
from zmq.utils import jsonapi
import dateutil.parser
from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import headers as headers_mod, topics
   
from input_output import result_writer, open_file, read_oae_pandas
   
def passiveafdd(config_path, **kwargs):
    '''Passive fault detection application for AHU/RTU economizer systems'''
    config_data = utils.load_config(config_path)
    rtu_path = dict((key, config_data[key])
                        for key in ['campus', 'building', 'unit'])
    utils.setup_logging()
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
    

    class Agent(PublishMixin, BaseAgent):
        def __init__(self, **kwargs):
            '''Input and initialize user configurable parameters.'''
            super(Agent, self).__init__(**kwargs)
            self.agent_id = config_data.get('agentid')
            self.aggregate_data = int(config_data["aggregate_data"])
            self.matemp_missing = int(config_data["matemp_missing"])
            self.mat_low = float(config_data["mat_low"])
            self.mat_high = float(config_data["mat_high"])
            self.oat_low = float(config_data["oat_low"])
            self.oat_high = float(config_data["oat_high"])
            self.rat_low = float(config_data["rat_low"])
            self.rat_high = float(config_data["rat_high"])
            self.high_limit = float(config_data["high_limit"])
            self.oae2_damper_threshold = float(config_data["oae2_damper_threshold"])
            self.oae2_oaf_threshold = float(config_data["oae2_oaf_threshold"])
            self.economizer_type = int(config_data["economizer_type"])
            self.damper_minimum = float(config_data["damper_minimum"])
            self.minimum_oa = float(config_data["minimum_oa"])
            self.oae4_oaf_threshold = float(config_data["oae4_oaf_threshold"])
            self.oae5_oaf_threshold = float(config_data["oae5_oaf_threshold"])
            self.eer = float(config_data["EER"])
            tonnage = float(config_data["tonnage"])
            self.cfm = 300*tonnage
            self.csv_input = int(config_data["csv_input"])
            self.timestamp_name = config_data.get('timestamp_name')
            self.input_file = config_data.get('input_file','CONFIG_ERROR')
            self.oat_name = config_data.get('oat_point_name')
            self.rat_name = config_data.get('rat_point_name')
            self.mat_name = config_data.get('mat_point_name')
            self.sampling_rate = config_data.get('sampling_rate')
            self.fan_status_name = config_data.get('fan_status_point_name')
            self.cool_cmd_name = config_data.get('cool_cmd_name')
            self.heat_cmd_name = config_data.get('heat_cmd_name')
            self.damper_name = config_data.get('damper_point_name')
            self.mat_missing = config_data.get('mixed_air_sensor_missing')
            sunday = config_data.get('Sunday')
            monday = config_data.get('Monday')
            tuesday = config_data.get('Tuesday')
            wednesday = config_data.get('Wednesday')
            thursday = config_data.get('Thursday')
            friday = config_data.get('Friday')
            saturday = config_data.get('Saturday')
   
            self.schedule_dict = dict({0:sunday, 1:monday, 2:tuesday, 3:wednesday,
                                       4:thursday, 5:friday,
                                       6:saturday})
            self.oaf_raw = []
            self.timestamp_raw = []
            self.matemp_raw = []
            self.oatemp_raw = []
            self.ratemp_raw = []
            self.compressor_raw = []
            self.heating_raw = []
            self.damper_raw = []
            self.fan_status_raw = []
            self.oaf = []
            self.timestamp = []
            self.matemp = []
            self.oatemp = []
            self.ratemp = []
            self.compressor = []
            self.heating = []
            self.damper = []
            self.fan_status = []
            self.run_aggregate = None
            self.names = [config_data.get('oat_point_name'),
                          config_data.get('mat_point_name'),
                          config_data.get('dat_point_name'),
                          config_data.get('rat_point_name'),
                          config_data.get('damper_point_name'),
                          config_data.get('cool_cmd_name'),
                          config_data.get('fan_status_point_name'),
                          config_data.get('heat_cmd_name')]
            self.file = config_data.get('input_file')
   
        def setup(self):
            '''Enter location for the data file if using text csv.
            
            Entry can be through file entry window using TKinter or 
            through configuration file as input_file.
            ''' 
            try:
                super(Agent, self).setup()
                _log.info('Running')
                if self.csv_input:
                    self.file_path = open_file()
                    if self.file_path == '':
                        _log.info('No csv file not found ...')
                        return
                    if (self.file_path == 'File Selected is not a csv' or
                       not self.file_path.endswith('.csv')):
                        _log.info('File must be in CSV format.')
                        return
                    if self.input_file =="CONFIG_ERROR":
                        _log.info('Check configuration file and add input_file parameter '
                                  'as file path to data file')
                        return
                    if self.file_path is None:
                        self.file_path = self.file
                    self.bldg_data = read_oae_pandas(self.file_path, self.names)
                self.process_data()
            except:
                _log.error('Error on data input, could not data file...')
   
        def process_data(self):
            '''Aggregate the data based on compressor status, heating status,
            and supply-fan status where one hour is the largest aggregated 
            interval.
            '''
            _log.info('Processing data')
            timestamp = []
            if self.csv_input:
                timestamp_ = self.bldg_data[self.timestamp_name].tolist()
                matemp = self.bldg_data[self.mat_name].tolist()
                oatemp = self.bldg_data[self.oat_name].tolist()
                ratemp = self.bldg_data[self.rat_name].tolist()
                compressor = self.bldg_data[self.cool_cmd_name].tolist()
                heating = self.bldg_data[self.heat_cmd_name].tolist()
                damper = self.bldg_data[self.damper_name].tolist()
                fan_status = self.bldg_data[self.fan_status_name].tolist()
            else:
                timestamp_ = self.timestamp_raw
                matemp = self.matemp_raw
                oatemp = self.oatemp_raw 
                ratemp = self.ratemp_raw
                compressor = self.compressor_raw 
                heating = self.heating_raw
                damper = self.damper_raw
                fan_status = self.fan_status_raw
            for item in timestamp_:
                timestamp.append(dateutil.parser.
                                 parse(item, fuzzy=True))
            if self.aggregate_data:
                temp_damper = []
                temp_mat = []
                temp_oat = []
                temp_rat = []
                for points in xrange(0, len(timestamp)-1):
                    temp_damper.append(damper[points])
                    temp_oat.append(oatemp[points])
                    temp_mat.append(matemp[points])
                    temp_rat.append(ratemp[points])
                    if timestamp[points].hour != timestamp[points+1].hour:
                        self.timestamp.append((timestamp[points] +
                                              datetime.timedelta(hours=1)).
                                              replace(minute=0))
                        temp_oat[:] = (value for value in temp_oat
                                       if value != 0)
                        temp_rat[:] = (value for value in temp_rat
                                       if value != 0)
                        temp_mat[:] = (value for value in temp_mat
                                       if value != 0)
                        self.damper.append(numpy.mean(temp_damper))
                        self.oatemp.append(numpy.mean(temp_oat))
                        self.matemp.append(numpy.mean(temp_mat))
                        self.ratemp.append(numpy.mean(temp_rat))
                        self.compressor.append(compressor[points])
                        self.fan_status.append(fan_status[points])
                        self.heating.append(heating[points])
                        temp_damper = []
                        temp_mat = []
                        temp_oat = []
                        temp_rat = []
   
                    elif (compressor[points+1] != compressor[points] or
                          heating[points+1] != heating[points] or
                          ((timestamp[points+1] - timestamp[points]
                           > datetime.timedelta(minutes=self.sampling_rate)))):
                        self.timestamp.append(timestamp[points])
                        temp_oat[:] = (value for value in temp_oat
                                       if value != 0)
                        temp_rat[:] = (value for value in temp_rat
                                       if value != 0)
                        temp_mat[:] = (value for value in temp_mat
                                       if value != 0)
                        self.damper.append(numpy.mean(temp_damper))
                        self.oatemp.append(numpy.mean(temp_oat))
                        self.matemp.append(numpy.mean(temp_mat))
                        self.ratemp.append(numpy.mean(temp_rat))
                        self.compressor.append(compressor[points])
                        self.fan_status.append(fan_status[points])
                        self.heating.append(heating[points])
                        temp_damper = []
                        temp_mat = []
                        temp_oat = []
                        temp_rat = []
                    if (points == len(timestamp) - 2 and not temp_oat):
                        temp_damper.append(damper[points+1])
                        temp_oat.append(oatemp[points+1])
                        temp_mat.append(matemp[points+1])
                        temp_rat.append(ratemp[points+1])
                        self.timestamp.append(timestamp[points+1])
                        temp_oat[:] = (value for value in temp_oat
                                       if value != 0)
                        temp_rat[:] = (value for value in temp_rat
                                       if value != 0)
                        temp_mat[:] = (value for value in temp_mat
                                       if value != 0)
                        self.damper.append(numpy.mean(temp_damper))
                        self.oatemp.append(numpy.mean(temp_oat))
                        self.matemp.append(numpy.mean(temp_mat))
                        self.ratemp.append(numpy.mean(temp_rat))
                        self.compressor.append(compressor[points+1])
                        self.fan_status.append(fan_status[points+1])
                        self.heating.append(heating[points+1])
                        temp_damper = []
                        temp_mat = []
                        temp_oat = []
                        temp_rat = []
            else:
                self.matemp = matemp
                self.oatemp = oatemp 
                self.ratemp = ratemp 
                self.compressor = compressor
                self.heating = heating 
                self.damper = damper
                self.fan_status = fan_status
            self.oaf_raw = []
            self.timestamp_raw = []
            self.matemp_raw = []
            self.oatemp_raw = []
            self.ratemp_raw = []
            self.compressor_raw = []
            self.heating_raw = []
            self.damper_raw = []
            self.fan_status_raw = []
            self.newdata = len(self.timestamp)
   
            def check_nan(data):
                '''check for any nan values in data.'''
                length = len(data)
                for x in xrange(0, length):
                    if math.isnan(data[x]):
                        data[x] = -99
                return data
            self.matemp = check_nan(self.matemp)
            self.oatemp = check_nan(self.oatemp)
            self.ratemp = check_nan(self.ratemp)
            self.compressor = check_nan(self.compressor)
            self.heating = check_nan(self.heating)
            self.damper = check_nan(self.damper)
            self.fan_status = check_nan(self.fan_status)
            self.oaf = self.calculate_oaf()
            #self.output_aggregate()
            _log.info('Performing Diagnostic')
            oae_1 = self.sensor_diagnostic()
            oae_2 = self.economizer_diagnostic1()
            oae_3 = self.economizer_diagnostic2()
            oae_4 = self.excess_oa_intake()
            oae_5 = self.insufficient_ventilation()
            oae_6 = self.schedule_diagnostic()
            energy_impact = self.calculate_energy_impact(oae_2, oae_3, oae_4)
            contents = [self.timestamp, oae_1, oae_2, oae_3, oae_4, oae_5,
                        oae_6, energy_impact, self.oaf]
            result_writer(contents)
   
        def output_aggregate(self):
            '''output_aggregate writes the results of the data
            aggregation to file for inspection.
            '''
            file_path = inspect.getfile(inspect.currentframe())
            out_dir = os.path.dirname(os.path.realpath(file_path))
            now = datetime.date.today()
            file_path = os.path.join(out_dir, "Aggregate_Data({ts}).csv".
                                     format(ts=now))
   
            ofile = open(file_path, 'wb')
            x = [self.timestamp, self.oatemp, self.matemp, self.ratemp,
                 self.damper, self.compressor, self.heating, self.fan_status]
            outs = csv.writer(ofile, dialect='excel')
            writer = csv.DictWriter(ofile, fieldnames=["Timestamp",
                                                       "OutsideAirTemp",
                                                       "MixedAirTemp",
                                                       "ReturnAirTemp",
                                                       "Damper",
                                                       "CompressorStatus",
                                                       "Heating",
                                                       "FanStatus"],
                                    delimiter=',')
            writer.writeheader()
            for row in itertools.izip_longest(*x):
                    outs.writerow(row)
            ofile.close()
   
        def calculate_oaf(self):
            '''Create OAF vector for data set.'''
            for points in xrange(0, self.newdata):
                if (self.matemp[points] != -99 and self.oatemp[points] != -99
                    and self.ratemp[points] != -99 and
                    math.fabs(self.oatemp[points] - self.ratemp[points])
                        > 4.0 and int(self.fan_status[points]) == 1):
                    self.oaf.append((self.matemp[points] - self.ratemp[points])
                                    / (self.oatemp[points] -
                                       self.ratemp[points]))
                else:
                    self.oaf.append(int(-99))
            return self.oaf
   
        def sensor_diagnostic(self):
            oae1_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if int(self.fan_status[points]):
                        if (self.matemp[points] != -99 and
                           self.ratemp[points] != -99 and
                           self.oatemp[points] != -99):
                            if ((int(self.matemp_missing) and
                               int(self.compressor[points])
                               or int(self.heating[points]))):
                                oae1_result.append(22)
                            elif (self.matemp[points] < self.mat_low or
                                  self.matemp[points] > self.mat_high):
                                # Temperature sensor problem detected (fault).
                                oae1_result.append(23)
                            elif (self.ratemp[points] < self.rat_low or
                                  self.ratemp[points] > self.rat_high):
                                # Temperature sensor problem detected (fault).
                                oae1_result.append(24)
                            elif (self.oatemp[points] < self.oat_low or
                                  self.oatemp[points] > self.oat_high):
                                # Temperature sensor problem detected (fault).
                                oae1_result.append(25)
                            elif ((self.matemp[points] > self.ratemp[points]
                                   and
                                  self.matemp[points] > self.oatemp[points]) or
                                  (self.matemp[points] < self.ratemp[points]
                                   and
                                  self.matemp[points] < self.oatemp[points])):
                                # Temperature sensor problem detected (fault).
                                oae1_result.append(21)
                            else:
                                # No faults detected.
                                oae1_result.append(20)   
                        else:
                            # Missing required data for diagnostic (No fault).
                            oae1_result.append(27)
                    else:
                        # Unit is off (No Fault).
                        oae1_result.append(29)
                else:
                    # Missing required data for diagnostic (No fault).
                    oae1_result.append(27)
            return oae1_result
   
        def economizer_diagnostic1(self):
            oae2_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if self.fan_status[points]:
                        if (self.ratemp[points] != -99 and
                           self.oatemp[points] != -99 and
                           self.compressor[points] != -99 and
                           self.damper[points] != -99):
                            if (self.compressor[points] and
                                ((self.oatemp[points] < self.ratemp[points]
                                 and self.economizer_type == 0.0) or
                                (self.oatemp[points] < self.high_limit
                                 and self.economizer_type == 1.0))):
                                if ((100.0 - self.damper[points]) <
                                   self.oae2_damper_threshold):
                                    if math.fabs(self.oatemp[points] - self.ratemp[points]) > 5.0 and not self.matemp_missing:
                                        if (1.0 - self.oaf[points] < self.oae2_oaf_threshold
                                            and
                                           self.oaf[points] > 0 and
                                           self.oaf[points] < 1.25):
                                            # No fault detected.
                                            oae2_result.append(30)
                                        elif (1.0 - self.oaf[points] > self.oae2_oaf_threshold and
                                              self.oaf[points] > 0 and
                                              self.oaf[points] < 1.25):
                                            # OAF is too low (Fault).
                                            oae2_result.append(32)
                                        else:
                                            # OAF resulted in unexpected value (No fault).
                                            oae2_result.append(38)
                                    elif not ((self.heating[points] and
                                              self.compressor[points]) and
                                        math.fabs(self.oatemp[points] - self.ratemp[points]) > 5.0
                                              and self.matemp_missing):
                                        if (1.0 - self.oaf[points] < self.oae2_oaf_threshold and
                                           self.oaf[points] > 0 and
                                           self.oaf[points] < 1.25):
                                            oae2_result.append(30)
                                        elif (1.0 - self.oaf[points] > self.oae2_oaf_threshold and
                                              self.oaf[points] > 0
                                              and self.oaf[points] < 1.25):
                                             # OAF is too low when unit is economizing (Fault).
                                            oae2_result.append(32)
                                        else:
                                            oae2_result.append(38)
                                    else:
                                        oae2_result.append(36)
                                else:
                                      # Damper is not open when conditions are favorable for economizing (Fault).
                                    oae2_result.append(33)
                            else:
                                oae2_result.append(31)
                        else:
                            #Missing data (No fault).
                            oae2_result.append(37)
                    else:
                        # Supply fan is off (No fault).
                        oae2_result.append(39)
                else:
                    oae2_result.append(37)
            return oae2_result
   
        def economizer_diagnostic2(self):
            oae3_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if self.fan_status[points]:
                        if (self.compressor[points] != -99 and
                           self.ratemp[points] != -99 and
                           self.oatemp[points] != -99 and
                           self.damper[points] != -99):
                            if (self.compressor[points]):
                                if((self.oatemp[points] > self.ratemp[points]
                                    and self.economizer_type == 0.0)
                                   or
                                    (self.oatemp[points] > self.high_limit
                                     and self.economizer_type == 1.0)):
                                    if self.damper[points] <= self.damper_minimum:
                                        # No fault detected.
                                        oae3_result.append(40)
                                    else:
                                        # Damper should be at minimum (Fault).
                                        oae3_result.append(41)
                                else:
                                    # Conditions favorable for economizing (No fault).
                                    oae3_result.append(43)
                            else:
                                if self.damper[points] <= self.damper_minimum:
                                    # Damper is at minimum for ventilation(No fault).
                                    oae3_result.append(42)
                                else:
                                    # Damper should be at minimum(Fault).
                                    oae3_result.append(41)
                        else:
                             # Missing Data (No fault).
                            oae3_result.append(47)
                    else:
                        # Supply fan is off (No fault).
                        oae3_result.append(49)   
                else:
                    # Missing data (No fault).
                    oae3_result.append(47)  
            return oae3_result
   
        def excess_oa_intake(self):
            oae4_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if self.fan_status[points]:
                        if (self.compressor[points] != -99 and
                           self.oatemp[points] != -99 and
                           self.ratemp[points] != -99 and
                           self.damper[points] != -99):
                            if ((self.compressor[points] and
                               ((self.oatemp[points] > self.ratemp[points] and
                                self.economizer_type == 0.0)
                                   or
                                (self.oatemp[points] > self.high_limit and
                                 self.economizer_type == 1.0)))
                                or
                               not self.compressor[points]):
                                if self.damper[points] <= self.damper_minimum:
                                    if (not self.matemp_missing and
                                       math.fabs(self.oatemp[points] -
                                                 self.ratemp[points]) > 5.0):
                                        if ((self.oaf[points] -
                                           self.minimum_oa) < self.oae4_oaf_threshold and
                                           self.oaf[points] > 0 and
                                           self.oaf[points] < 1.25):
                                            # No Fault detected.
                                            oae4_result.append(50)
                                        elif ((self.oaf[points] -
                                              self.minimum_oa)
                                                > self.oae4_oaf_threshold and
                                              self.oaf[points] > 0 and
                                              self.oaf[points] < 1.25):
                                             # Excess OA intake (Fault).
                                            oae4_result.append(51) 
                                        else:
                                            # OAF calculation resulted in unexpected value (No fault).
                                            oae4_result.append(58)
                                    elif (not int(self.heating[points]) and
                                          not int(self.compressor[points]) and
                                          math.fabs(self.oatemp[points] -
                                                    self.ratemp[points]) > 5.0
                                          and self.matemp_missing):
                                        if (self.oaf[points] - self.minimum_oa < self.oae4_oaf_threshold and
                                           self.oaf[points] > 0 and
                                           self.oaf[points] < 1.25):
                                            # No fault detected.
                                            oae4_result.append(50)
                                        elif ((self.oaf[points] -
                                               self.minimum_oa) >
                                                self.oae4_oaf_threshold and
                                              self.oaf[points] > 0 and
                                              self.oaf[points] < 1.25):
                                            # The unit is bringing in excess OA (Fault).
                                            oae4_result.append(51)
                                        else:
                                             # OAF calculation resulted in unexpected value (No Fault).
                                            oae4_result.append(58)
                                    else:
                                        # Conditions are not favorable for OAF calculation (No Fault).
                                        oae4_result.append(52)
                                else:
                                    # Damper is not at minimum (Fault).
                                    oae4_result.append(53)  
                            else:
                                # Unit should be economizing (No fault).
                                oae4_result.append(56)
                        else:
                            # Missing data (No fault).
                            oae4_result.append(57)
                    else:
                        # Supply fan is off (No Fault).
                        oae4_result.append(59)
                else:
                    # Missing data (No fault).
                    oae4_result.append(57)
            return oae4_result
   
        def insufficient_ventilation(self):
            oae5_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if int(self.fan_status[points]) == 1:
                        if (self.compressor[points] != -99 and
                           self.oatemp[points] != -99 and
                           self.ratemp[points] != -99 and
                           self.damper[points] != -99):
                            if ((int(self.compressor[points] and
                                (self.oatemp[points] > self.ratemp[points])
                                and self.economizer_type == 0.0)) or
                                (self.oatemp[points] > self.high_limit and
                               self.economizer_type == 1.0) or not
                               int(self.compressor[points])):
                                if self.damper[points] <= self.damper_minimum:
                                    if (math.fabs(self.oatemp[points]-self.ratemp[points]) > 5.0
                                       and not self.matemp_missing):
                                        if ((self.minimum_oa - self.oaf[points]) > self.oae5_oaf_threshold and
                                           self.oaf[points] > 0 and
                                           self.oaf[points] < 1.25):
                                            # Unit is bringing in insufficient OA (Fault).
                                            oae5_result.append(61)
                                        elif ((self.minimum_oa - self.oaf[points]) < self.oae5_oaf_threshold and
                                              self.oaf[points] > 0 and
                                              self.oaf[points] < 1.25):
                                            # No problem detected.
                                            oae5_result.append(60)
                                        else:
                                            oae5_result.append(68)
                                    elif (math.fabs(self.oatemp[points]-self.ratemp[points]) > 5.0 and
                                          self.matemp_missing and not int(self.compressor[points]) and
                                          int(self.heating[points])):
                                        if ((self.minimum_oa - self.oaf[points]) > self.oae5_oaf_threshold  and
                                           self.oaf[points] > 0 and
                                           self.oaf[points] < 1.25):
                                            oae5_result.append(61)  # Insufficient OA (Fault)
                                        elif ((self.minimum_oa - self.oaf[points]) < self.oae5_oaf_threshold and
                                              self.oaf[points] > 0 and
                                              self.oaf[points] < 1.25):
                                            oae5_result.append(60)  # No Fault
                                        else:
                                            # OAF calculation resulted in unexpected value (No Fault).
                                            oae5_result.append(68)
                                    else:
                                         # Conditions are not favorable for OAF calculation (No Fault).
                                        oae5_result.append(62)
                                else:
                                    # Damper is not at minimum (Fault).
                                    oae5_result.append(63)
                            else:
                                # Unit should be economizing (No Fault)
                                oae5_result.append(66)
                        else:
                            # Missing required data (No fault).
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
                   self.compressor[points] != -99):
                    if (int(self.fan_status[points]) or
                       int(self.compressor[points])):
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
   
        def calculate_energy_impact(self,oae_2, oae_3, oae_4):
            energy_impact = []
            month_abbr = {k: v for k, v in enumerate(calendar.month_abbr)}
            if not self.matemp_missing:
                for points in xrange(0, self.newdata):
                    if oae_2[points] == 32 or oae_2[points] == 33:
                        energy_impact.append(
                            1.08*self.cfm*(self.matemp[points] -
                                           self.oatemp[points])/(1000*self.eer))
                    elif (oae_3[points] == 41 or oae_4[points] == 51 or
                          oae_4[points] == 53 and
                          self. oatemp[points] > self.matemp[points]):
                        ei = 1.08*self.cfm/(1000*self.eer)
                        ei = ei*(self.matemp[points] - (self.oatemp[points]*
                                                        self.minimum_oa +
                                                        self.ratemp[points]*
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
        
        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def datahandler(self, topic, header, message, match):
            '''Subscribes to data and assembles raw data arrays.
            
            data_handler subscribes to a device or simulated device on the 
            message bus and assembles the array (lists) of data to be aggregated
            for analysis.
            '''
            data = jsonapi.loads(message[0])
            _log.info('Getting Data from message bus')
            publisher_id = header.get('AgentID', 0)
            if ((self.run_aggregate is False or
               self.run_aggregate is None) and
               publisher_id != 'publisher'):
                _log.info('Real-time device data.')
                self.run_aggregate = True
                event_time = (datetime.datetime.now().
                              replace(hour=0, minute=0, second=0) +
                              datetime.timedelta(days=1))
                event = sched.Event(self.process_data)
                self.schedule(event_time, event)
                self.oaf_raw = []
                self.timestamp_raw = []
                self.matemp_raw = []
                self.oatemp_raw = []
                self.ratemp_raw = []
                self.compressor_raw = []
                self.heating_raw = []
                self.damper_raw = []
                self.fan_status_raw = []
            elif publisher_id == 'publisher':
                _log.info('Simulated device data.')
                if self.run_aggregate is None:
                    self.prev_time = dateutil.parser.parse(
                                            data[self.timestamp_name])
                self.run_aggregate = True
                time = dateutil.parser.parse(data[self.timestamp_name ],
                                             fuzzy=True)
                time_delta = time - self.prev_time
                time_check = time + time_delt
                self.timestamp_raw.append(time)
                self.fan_status_raw.append(data[self.fan_status_name])
                self.compressor_raw.append(data[self.coolcmd1_name])
                self.heating_raw.append(data[self.heat_cmd1_name])
                self.damper_raw.append(data[self.damper_name])
                self.oatemp_raw.append(data[self.oat_name])
                self.ratemp_raw.append(data[self.rat_name])
                self.matemp_raw.append(data[self.mat_name])
                if time.day < time_check.day:
                    self.timestamp_raw.append(time_check)
                    self.process_data()
                    self.oaf_raw = []
                    self.timestamp_raw = []
                    self.oatemp_raw = []
                    self.ratemp_raw = []
                    self.compressor_raw = []
                    self.heating_raw = []
                    self.damper_raw = []
                    self.fan_status_raw = []
                self.prev_time = time
            if publisher_id != 'publisher':
                self.timestamp_raw.append(datetime.datetime.now())
                self.fan_status_raw.append(data[self.fan_status_name])
                self.compressor_raw.append(data[self.coolcmd1_name])
                self.heating_raw.append(data[self.heat_cmd1_name])
                self.damper_raw.append(data[self.damper_name])
                self.oatemp_raw.append(data[self.oat_name])
                self.ratemp_raw.append(data[self.rat_name])
                self.matemp_raw.append(data[self.mat_name])
   
    Agent.__name__ = 'passiveafdd'
    return Agent(**kwargs)
   
   
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(passiveafdd,
                       description='VOLTTRON passive AFDD',
                       argv=argv)
if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
