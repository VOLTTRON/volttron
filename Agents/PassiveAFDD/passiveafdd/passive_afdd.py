# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
# Copyright ï¿½ 2013, Battelle Memorial Institute
# All rights reserved.
# 1.     Battelle Memorial Institute (hereinafter Battelle) hereby grants permission to any person or entity lawfully obtaining a copy of this software and associated documentation files (hereinafter ï¿½the Softwareï¿½) to redistribute and use the Software in source and binary forms, with or without modification.  Such person or entity may use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and may permit others to do so, subject to the following conditions:
# ï¿½    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimers. 
# ï¿½    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution. 
# ï¿½    Other than as used herein, neither the name Battelle Memorial Institute or Battelle may be used in any form whatsoever without the express written consent of Battelle.   
# 2.     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# 3.      The Software was produced by Battelle under Contract No. DE-AC05-76RL01830 with the Department of Energy.  For five (5) years from September 30, 2013 the Government is granted for itself and others acting on its behalf a nonexclusive, paid-up, irrevocable worldwide license in this data to reproduce, prepare derivative works, and perform publicly and display publicly, by or on behalf of the Government.  There is provision for the possible extension of the term of this license.  Subsequent to that period or any extension granted, the Government is granted for itself and others acting on its behalf a nonexclusive, paid-up, irrevocable worldwide license in this data to reproduce, prepare derivative works, distribute copies to the public, perform publicly and display publicly, and to permit others to do so.  The specific term of the license can be identified by inquiry made to Battelle or DOE.  Neither the United States nor the United States Department of Energy, nor any of their employees, makes any warranty, express or implied, or assumes any legal liability or responsibility for the accuracy, completeness or usefulness of any data, apparatus, product or process disclosed, or represents that its use would not infringe privately owned rights.
# }}}}  
import datetime
import logging
import numpy
import math
import calendar
import sys
import inspect
import os
#import getopt
import clock
import logging
import sys
import csv
import itertools
import logging

logging.captureWarnings(True)
from zmq.utils import jsonapi
from dateutil import parser
from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import headers as headers_mod, topics

from input_output import read_oae_csv, result_writer, open_file
#logging.captureWarnings(True)
    
#if( __name__ == '__main__' ):
#    sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
#from src.lbl import convert_dateStr as fr_cds
#from src.lbl import read_csv as fr_rcsv
#from src.lbl import copy_file as fw_copy
def passiveafdd(config_path, **kwargs):
    """Passive fault detection application"""
    config_data = utils.load_config(config_path)
    rtu_path = dict((key, config_data[key])
                        for key in ['campus', 'building', 'unit'])
    
    class Agent(PublishMixin, BaseAgent):
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            
            self.agent_id = config_data.get('agentid')
           
            self.aggregate_data = int(config_data["aggregate_data"])
            self.matemp_missing = int(config_data["matemp_missing"])
            self.mat_low = float(config_data["mat_low"])
            self.mat_high =float(config_data["mat_high"])
            self.oat_low = float(config_data["oat_low"])
            self.oat_high =float(config_data["oat_high"])
            self.rat_low = float(config_data["rat_low"])
            self.rat_high =float(config_data["rat_high"])
            self.high_limit = float(config_data["high_limit"])
            self.oae2_damper_threshold = float(config_data["oae2_damper_threshold"])
            self.oae2_oaf_threshold = float(config_data["oae2_oaf_threshold"])
            self.economizer_type = int(config_data["economizer_type"])
            self.damper_minimum = float(config_data["damper_minimum"])
            self.minimum_oa = float(config_data["minimum_oa"])
            self.oae4_oaf_threshold  = float(config_data["oae4_oaf_threshold"])
            self.oae5_oaf_threshold  = float(config_data["oae5_oaf_threshold"])
            self.eer = float(config_data["EER"])
            tonnage = float(config_data["tonnage"])
            self.cfm = 300 * tonnage
            self.csv_input = int(config_data["csv_input"])
                
            self.input_file = config_data.get('input_file')
            self.oat_name = config_data.get('oat_point_name')
            self.rat_name = config_data.get('rat_point_name')
            self.mat_name = config_data.get('mat_point_name')
            #self.dat_name = config_data.get('dat_point_name')
            self.fan_status_name =  config_data.get('fan_status_point_name')
            self.coolcmd1_name = config_data.get('cool_cmd1_point_name')
            self.heat_cmd1_name = config_data.get('heat_command1_point_name')
            self.damper_name = config_data.get('damper_point_name')
            self.mat_missing = config_data.get('mixed_air_sensor_missing')
            sunday=config_data.get('Sunday')
            monday=config_data.get('Monday')
            tuesday=config_data.get('Tuesday')
            wednesday=config_data.get('Wednesday')
            thursday=config_data.get('Thursday')
            friday=config_data.get('Friday')
            saturday=config_data.get('Saturday')
            
            
            self.schedule_dict = dict({0:sunday,1:monday,2:tuesday,3:wednesday,4:thursday,5:friday,6:saturday})
#             for items in schedule:
#                     self.schedule[items]=schedule[items].split(',')
    
            self.oaf_raw = []
            self.timestamp_raw = []
            self.matemp_raw = []
            self.oatemp_raw = []
            self.ratemp_raw = []
            self.compressor_raw = []
            self.heating_raw = []
            self.damper_raw = []
            self.fan_status_raw=[]
            
            self.oaf = []
            self.timestamp = []
            self.matemp = []
            self.oatemp = []
            self.ratemp = []
            self.compressor = []
            self.heating = []
            self.damper = []
            self.fan_status=[]

            self.run_aggregate= None

        def setup(self):
            try:
                super(Agent, self).setup()
                print 'Running'
                if self.csv_input:
                    self.file_path = open_file()
                    if self.file_path == '':
                        print 'No csv file entered, rerun AFDD...'
                        return
                    if self.file_path == 'File Selected is not a csv':
                        print self.file_path
                        return
                 
                self.bldg_data = read_oae_csv(self.file_path)
                self.process_data()
            except:
                 print 'Error with data file check file format'

        def process_data(self):
            print 'Performing diagnostic...'
            if self.csv_input:
                timestamp = self.bldg_data['Timestamp']
                matemp = self.bldg_data['MixedAirTemp']
                oatemp = self.bldg_data['OutsideAirTemp']
                ratemp = self.bldg_data['ReturnAirTemp']
                compressor = self.bldg_data['CompressorStatus']
                heating = self.bldg_data['HeatingStatus']
                damper = self.bldg_data['Damper']
                fan_status = self.bldg_data['FanStatus']
            else:
                timestamp = self.timestamp_raw
                matemp = self.matemp_raw
                oatemp = self.oatemp_raw 
                ratemp = self.ratemp_raw
                compressor = self.compressor_raw 
                heating = self.heating_raw
                damper = self.damper_raw
                fan_status = self.fan_status_raw
                
            def convert_fr_string(data):
                for x in xrange(0,len(data)):
                    try:
                        data[x]=float(data[x])
                    except (TypeError, ValueError):
                        data[x]=-99
                return data
                        
            matemp = convert_fr_string(matemp)
            oatemp = convert_fr_string(oatemp)
            ratemp = convert_fr_string(ratemp)
            compressor = convert_fr_string(compressor)
            heating = convert_fr_string(heating)
            damper = convert_fr_string(damper)
            fan_status = convert_fr_string(fan_status)
           
            if self.aggregate_data:         
                temp_damper=[]
                temp_mat=[]
                temp_oat=[]
                temp_rat=[]
                for points in xrange(0, len(timestamp)-1):
                    temp_damper.append(damper[points])
                    temp_oat.append(oatemp[points])
                    temp_mat.append(matemp[points])
                    temp_rat.append(ratemp[points])
                    if timestamp[points].hour != timestamp[points+1].hour:
                        self.timestamp.append((timestamp[points] + datetime.timedelta(hours=1)).replace(minute=0))
                        temp_oat[:] = (value for value in temp_oat if value != 0)
                        temp_rat[:] = (value for value in temp_rat if value != 0)
                        temp_mat[:] = (value for value in temp_mat if value != 0)
                        self.damper.append(numpy.mean(temp_damper))                                                           
                        self.oatemp.append(numpy.mean(temp_oat))
                        self.matemp.append(numpy.mean(temp_mat))
                        self.ratemp.append(numpy.mean(temp_rat))
                        self.compressor.append(compressor[points])
                        self.fan_status.append(fan_status[points])
                        self.heating.append(heating[points])
                        temp_damper=[]
                        temp_mat=[]
                        temp_oat=[]
                        temp_rat=[]
                           
                    elif (compressor[points+1]!=compressor[points] or heating[points+1]!=heating[points]):
                        self.timestamp.append(timestamp[points])
                        temp_oat[:] = (value for value in temp_oat if value != 0)
                        temp_rat[:] = (value for value in temp_rat if value != 0)
                        temp_mat[:] = (value for value in temp_mat if value != 0)
                        self.damper.append(numpy.mean(temp_damper))
                        self.oatemp.append(numpy.mean(temp_oat))
                        self.matemp.append(numpy.mean(temp_mat))
                        self.ratemp.append(numpy.mean(temp_rat))
                        self.compressor.append(compressor[points])
                        self.fan_status.append(fan_status[points])
                        self.heating.append(heating[points])
                        temp_damper=[]
                        temp_mat=[]
                        temp_oat=[]
                        temp_rat=[]
                        
                    if (points==len(timestamp)-2 and temp_oat!=[]):
                        temp_damper.append(damper[points+1])
                        temp_oat.append(oatemp[points+1])
                        temp_mat.append(matemp[points+1])
                        temp_rat.append(ratemp[points+1])
                        self.timestamp.append(timestamp[points+1])
                        temp_oat[:] = (value for value in temp_oat if value != 0)
                        temp_rat[:] = (value for value in temp_rat if value != 0)
                        temp_mat[:] = (value for value in temp_mat if value != 0)
                        self.damper.append(numpy.mean(temp_damper))
                        self.oatemp.append(numpy.mean(temp_oat))
                        self.matemp.append(numpy.mean(temp_mat))
                        self.ratemp.append(numpy.mean(temp_rat))
                        self.compressor.append(compressor[points+1])
                        self.fan_status.append(fan_status[points+1])
                        self.heating.append(heating[points+1])
                        temp_damper=[]
                        temp_mat=[]
                        temp_oat=[]
                        temp_rat=[]
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
            self.fan_status_raw =[]
            self.newdata=len(self.timestamp)

                
            def check_nan(data):
                length=len(data)
                for x in xrange(0,length):
                    if math.isnan(data[x]):
                        data[x]= -99
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

            oae_1 = self.sensor_diagnostic()
            oae_2 = self.economizer_diagnostic1()
            oae_3 = self.economizer_diagnostic2()
            oae_4 = self.excess_oa_intake()
            oae_5 = self.insufficient_ventilation()
            oae_6 = self.schedule_diagnostic()      
            energy_impact = self.calculate_energy_impact(oae_2, oae_3, oae_4)
            contents = [self.timestamp,oae_1, oae_2, oae_3, oae_4, oae_5, oae_6, energy_impact, self.oaf]
            #return self.timestamp 
            result_writer(contents)
            
        def output_aggregate(self):
            file_path = inspect.getfile(inspect.currentframe())
            out_dir = os.path.dirname(os.path.realpath(file_path))
            now = datetime.date.today()
            file_path = os.path.join(out_dir,"Aggregate_Data({ts}).csv".format(ts=now))

            ofile = open(file_path, 'wb')
            x = [self.timestamp, self.oatemp, self.matemp, self.ratemp, self.damper, self.compressor, self.heating, self.fan_status]
            outs = csv.writer(ofile, dialect='excel')
            writer = csv.DictWriter(ofile, fieldnames = ["Timestamp", "OutsideAirTemp","MixedAirTemp","ReturnAirTemp", "Damper","CompressorStatus","Heating","FanStatus"], delimiter = ',')
            writer.writeheader()
            for row in itertools.izip_longest(*x):
                    outs.writerow(row)
            ofile.close()          
              
        def calculate_oaf(self):
            for points in xrange(0, self.newdata):
                if (self.matemp[points]!=-99 and self.oatemp[points] != -99 and self.ratemp[points] != -99 and
                    math.fabs(self.oatemp[points] - self.ratemp[points]) > 4.0 and int(self.fan_status[points])==1):
                    self.oaf.append((self.matemp[points] - self.ratemp[points])/(self.oatemp[points]-self.ratemp[points]))       
                else:
                    self.oaf.append(int(-99))
            return self.oaf
               
        def sensor_diagnostic(self):
            oae1_result=[]
            for points in xrange(0, self.newdata):
                if self.fan_status[points]!= -99:
                    if int(self.fan_status[points]):
                        if (self.matemp[points] != -99 and
                            self.ratemp[points] != -99 and self.oatemp[points] != -99):
                            if (int(self.matemp_missing) and (int(self.compressor[points]) or int(self.heating[points]))):  
                                oae1_result.append(22)
                            elif self.matemp[points] < self.mat_low or self.matemp[points] > self.mat_high:
                                oae1_result.append(23) #Temperature sensor error (Fault)    
                            elif self.ratemp[points] < self.rat_low or self.ratemp[points] > self.rat_high:
                                oae1_result.append(24) #Temperature sensor error (Fault)  
                            elif self.oatemp[points] < self.oat_low or self.oatemp[points] > self.oat_high:
                                oae1_result.append(25) #Temperature sensor error (Fault)        
                            elif ((self.matemp[points] > self.ratemp[points] and self.matemp[points] > self.oatemp[points]) or
                                (self.matemp[points] < self.ratemp[points] and self.matemp[points] < self.oatemp[points])):
                                oae1_result.append(21) #Temperature sensor error (Fault)
                            else:
                                oae1_result.append(20) #No sensor error (No Fault)
                        else:
                            oae1_result.append(27) #Missing Data (No Fault)
                    else:
                        oae1_result.append(29) #Unit is off (No Fault)
                else:
                   oae1_result.append(27) #Missing Data (No Fault)
            return oae1_result
        
        def economizer_diagnostic1(self):
            oae2_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if self.fan_status[points]:
                        if (self.ratemp[points] != -99 and self.oatemp[points] !=-99 and 
                            self.compressor[points] != -99 and self.damper[points]!=-99):
                            if (self.compressor[points] and ((self.oatemp[points] < self.ratemp[points] and self.economizer_type == 0.0) or 
                                (self.oatemp[points] < self.high_limit and self.economizer_type == 1.0))):
                                if (100.0 - self.damper[points]) < self.oae2_damper_threshold:
                                    if math.fabs(self.oatemp[points]-self.ratemp[points])> 4 and not self.matemp_missing:
                                        if (1.0 - self.oaf[points] < self.oae2_oaf_threshold and 
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae2_result.append(30) #No Fault
                                        elif (1.0 - self.oaf[points] > self.oae2_oaf_threshold and 
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25) :
                                            oae2_result.append(32) #OAF is too low when unit is economizing (Fault)
                                        else:
                                           oae2_result.append(38) #Damper is open for economizing but OAF resulted in unexpected value (No Fault)
                                    elif not ((self.heating[points] and self.compressor[points]) and
                                        math.fabs(self.oatemp[points]-self.ratemp[points]) > 4 and self.matemp_missing):
                                        if (1.0 - self.oaf[points] < self.oae2_oaf_threshold and 
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae2_result.append(30) #No Fault
                                        elif (1.0 - self.oaf[points] > self.oae2_oaf_threshold and 
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25) :
                                            oae2_result.append(32) #OAF is too low when unit is economizing (Fault)
                                        else:
                                           oae2_result.append(38) #Damper is open for economizing but OAF resulted in unexpected value (No Fault)
                                    else:
                                        oae2_result.append(36) #Damper is open for economizing but conditions are not favorable for OAF calculation (No Fault)
                                else:
                                    oae2_result.append(33) #damper is not open when conditions are favorable for economizing (Fault)
                            else:
                                oae2_result.append(31) #No call for cooling RTU should not economize or conditions not favorable for economizing (No Fault)
                        else:
                            oae2_result.append(37) #Missing data 
                    else:
                        oae2_result.append(39) #Fan is off (No Fault)
                else:
                    oae2_result.append(37) #Fan Status is missing
            return oae2_result
            
        def economizer_diagnostic2(self):
            oae3_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99: 
                    if self.fan_status[points]:
                        if (self.compressor[points] != -99 and self.ratemp[points] != -99 and
                            self.oatemp[points] !=-99 and self.damper[points]!=-99):
                            if (self.compressor[points]):
                                if((self.oatemp[points] > self.ratemp[points] and self.economizer_type == 0.0) or 
                                    (self.oatemp[points] > self.high_limit and self.economizer_type == 1.0)):
                                    if self.damper[points] <= self.damper_minimum:
                                        oae3_result.append(40) #No Fault
                                    else:
                                        oae3_result.append(41) #Damper should be at minimum(Fault)
                                else:
                                    oae3_result.append(43) #Conditions favorable for economizing (No Fault)
                            else:
                                if self.damper[points] <= self.damper_minimum:
                                    oae3_result.append(42) #Damper is at minimum for ventilation(No Fault)
                                else:
                                    oae3_result.append(41)#Damper should be at minimum(Fault)
                        else:
                            oae3_result.append(47) #Missing Data(No fault)
                    else:
                        oae3_result.append(49) #fan is off (No fault)
                else:
                    oae3_result.append(47) #Missing Data(No fault)
            return oae3_result
    
        def excess_oa_intake(self):                 
            oae4_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if self.fan_status[points]:
                        if self.compressor[points] !=-99 and self.oatemp[points] != -99 and self.ratemp[points] != -99 and self.damper[points] != -99: 
                            if ((self.compressor[points] and ((self.oatemp[points] > self.ratemp[points] and self.economizer_type == 0.0) or 
                                (self.oatemp[points] > self.high_limit and self.economizer_type == 1.0))) or not self.compressor[points]):
                                if self.damper[points] <= self.damper_minimum:
                                    if  not self.matemp_missing and math.fabs(self.oatemp[points]- self.ratemp[points]) > 4:
                                        if (self.oaf[points] - self.minimum_oa < self.oae4_oaf_threshold and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae4_result.append(50) #No fault
                                        elif (self.oaf[points] - self.minimum_oa > self.oae4_oaf_threshold and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae4_result.append(51) # Excess OA (Fault)
                                        else:
                                            oae4_result.append(58) #Damper is position is at minimum but unexpected value for OAF
                                    elif (not (int(self.heating[points]) and int(self.compressor[points])) and 
                                        math.fabs(self.oatemp[points]-self.ratemp[points]) > 4 and self.matemp_missing):
                                        if (self.oaf[points] - self.minimum_oa < self.oae4_oaf_threshold and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae4_result.append(50) #No fault
                                        elif (self.oaf[points] - self.minimum_oa > self.oae4_oaf_threshold and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae4_result.append(51) # Excess OA (Fault)
                                        else:
                                            oae4_result.append(58) #Damper position is at minimum but unexpected value for OAF
                                    else:
                                        oae4_result.append(52) #Damper is at minimum but conditions are not favorable for OAF calculation (No Fault)
                                else:
                                    oae4_result.append(53) #Damper is not at minimum (Fault)
                            else:
                                oae4_result.append(56) #Unit should be economizing (No Fault)
                        else:
                            oae4_result.append(57) #Missing Data
                    else:
                        oae4_result.append(59) #Fan is off (No Fault)
                else:
                    oae4_result.append(57) #Missing Data
            return oae4_result
    
        def insufficient_ventilation(self):                 
            oae5_result = []
            for points in xrange(0, self.newdata):
                if self.fan_status[points] != -99:
                    if int(self.fan_status[points]) == 1:
                        if self.compressor[points] !=-99 and self.oatemp[points] != -99 and self.ratemp[points] != -99 and self.damper[points] != -99:
                            if ((int(self.compressor[points]) and ((self.oatemp[points] > self.ratemp[points] and self.economizer_type == 0.0) or 
                                (self.oatemp[points] > self.high_limit and self.economizer_type == 1.0))) or not int(self.compressor[points])):
                                if self.damper[points] <= self.damper_minimum:
                                    if math.fabs(self.oatemp[points]-self.ratemp[points]) > 4.0 and not self.matemp_missing:
                                        if (self.minimum_oa - self.oaf[points] > self.oae5_oaf_threshold  and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae5_result.append(61) # Insufficient OA (Fault)
                                        elif (self.minimum_oa - self.oaf[points] < self.oae5_oaf_threshold  and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae5_result.append(60) # No Fault
                                        else:
                                            oae5_result.append(68) #Unexpected value for OAF (No Fault)
                                    elif (math.fabs(self.oatemp[points]-self.ratemp[points]) > 4.0 and self.matemp_missing and 
                                        not (int(self.compressor[points]) and int(self.heating[points]))):
                                        if (self.minimum_oa - self.oaf[points] > self.oae5_oaf_threshold  and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae5_result.append(61) # Insufficient OA (Fault)
                                        elif (self.minimum_oa - self.oaf[points] < self.oae5_oaf_threshold  and
                                            self.oaf[points] > 0 and self.oaf[points] < 1.25):
                                            oae5_result.append(60) # No Fault
                                        else:
                                            oae5_result.append(68)#Unexpected value for OAF (No Fault)
                                    else:
                                        oae5_result.append(62) #Damper is at minimum but conditions are not favorable for OAF calculation (No Fault)
                                else:
                                    oae5_result.append(63) #Damper is not at minimum (Fault)
                            else:
                                oae5_result.append(66) #Unit should be economizing (No Fault)
                        else:
                            oae5_result.append(67) #Missing data (No Fault)
                    else:
                        oae5_result.append(69) #Unit is off (No Fault)
                else:
                    oae5_result.append(67) #Missing data (No Fault)
            return oae5_result
    
        def schedule_diagnostic(self):
            oae6_result = []
            for points in xrange(0, self.newdata):
                if (self.fan_status[points] !=-99 and self.compressor[points]!=-99):
                    if (int(self.fan_status[points]) or int(self.compressor[points])):
                        day = self.timestamp[points].weekday()
                        sched = self.schedule_dict[day]
                        start = int(sched[0])
                        end = int(sched[1])
                        if (self.timestamp[points].hour < start or self.timestamp[points].hour > end):
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
            month_abbr = {k: v for k,v in enumerate(calendar.month_abbr)}
            if not self.matemp_missing:
                for points in xrange(0, self.newdata):
                    if oae_2[points] == 32 or oae_2[points] == 33:
                        energy_impact.append(1.08 * self.cfm *(self.matemp[points] - self.oatemp[points])/(1000*self.eer))
                    elif (oae_3[points] == 41 or oae_4[points] == 51 or oae_4[points] == 53 and self. oatemp[points] > self.matemp[points]):
                        energy_impact.append(1.08 * self.cfm *(self.matemp[points] - (self.oatemp[points]*self.minimum_oa + self.ratemp[points]*(1-self.minimum_oa)))/(1000*self.eer))
                    elif (oae_3[points] == 41 or oae_4[points] == 51 or oae_4[points] == 53 and self. oatemp[points] > self.matemp[points]):
                        energy_impact.append(1.08 *(self.oatemp[points]*self.minimum_oa + self.ratemp[points]*(1-self.minimum_oa)) -  self.cfm *(self.matemp[points])/(1000*self.eer))
                    else:
                        energy_impact.append(0)
                    if energy_impact[points] < 0:
                        energy_impact[points] = 0
            return energy_impact
        
        @matching.match_exact(topics.RTU_VALUE(point='all', **rtu_path))
        def datahandler(self, topic, header, message, match):
            """watching for new data"""
            data = jsonapi.loads(message[0])
            print 'getting data'
            publisher_id = header.get('AgentID',0)
            
            if (self.run_aggregate == False or self.run_aggregate is None) and publisher_id != 'publisher':
                print 'real-time data'
                self.run_aggregate = True
                event_time = datetime.datetime.now().replace(hour=0, minute=0, second=0) + datetime.timedelta(days=1)
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
                self.fan_status_raw =[]
            elif publisher_id == 'publisher':
                print 'emulated device'
                if self.run_aggregate is None:
                    self.prev_time = parser.parse(data['Timestamp'])
                self.run_aggregate = True
                time = parser.parse(data['Timestamp'], fuzzy=True)
                time_delta = time - self.prev_time
                time_check = time + time_delta
                
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
                    self.fan_status_raw =[]
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
    
                                       
#For running in the terminal as stand alone application
# import os
# from input_output import gen_oae_output, read_oae_config, read_oae_csv
# 
# def usage():
#     print ''
#     print ' Outdoor Air Diagnostician'
#     print ' Usage:'
#     print '    python oae_fdd.py -c <configuration file> -i <input file (data file)>'
#     print ''
#     print ' Options:'
#     print '    -h, --help         OAE help'
#     print '    -i, --ifile        Data input file'
#     print '    -c, --config_file  Configuration file'
# 
# if __name__ == "__main__":
#     try:
#         opts, args = getopt.getopt(sys.argv[1:],"hi:c:",["help","ifile=","config_file"])
#     except getopt.GetoptError:
#         usage()
#         sys.exit(2) 
#     input_file = ''
#     output_dir = '' 
#  
#     for opt, arg in opts:
#         if opt in ('-h',"--help"):
#             usage()
#             sys.exit()
#         if opt in ("-c", "--config_file"):
#             input_file = arg
#         if opt in ("-i", "--ifile"):
#             bldg_file = arg
#     if input_file == ''or bldg_file =='':
#         usage()
#         sys.exit()
#     #Run OAE
#     if not os.path.exists(input_file):
#         print "No such file ", input_file
#         sys.exit()
#     try:
#         # read config file
#         ui_flag = False
#         oae_config_data = read_oae_config(input_file, ui_flag)
#         out_dir = os.path.abspath(os.path.join(os.path.dirname(input_file), '../OAE_Output'))
#         #out_dir = '../output_samples'
#         #bldg_file = '../../../sample_files/oae_data_csv/hourly_aggregated.csv'
#         #read csv file
#         oae_bldg_data = read_oae_csv(bldg_file)
#         #do analysis
#         oae = Oae(oae_bldg_data, oae_config_data, ui_flag)
#         timestamp = oae.map_input_data()
#         oaf = oae.calculate_oaf()
#         oae_1 = oae.sensor_diagnostic()
#         oae_2 = oae.economizer_diagnostic1()
#         oae_3 = oae.economizer_diagnostic2()
#         oae_4 = oae.excess_oa_intake()
#         oae_5 = oae.insufficient_ventilation()
#         oae_6 = oae.schedule_diagnostic()
#         energy_impact = oae.calculate_energy_impact(oae_2, oae_3, oae_4)
#         contents = [timestamp,oae_1, oae_2, oae_3, oae_4, oae_5, oae_6, energy_impact, oaf]
#         gen_oae_output(timestamp, energy_impact, contents, out_dir)
#     except Exception as err:
#         print err
#         sys.exit(2)           


