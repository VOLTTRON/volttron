# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
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

#}}}
import logging
import sys
import math
from zmq.utils import jsonapi
# _log = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
from volttron.platform.agent import  utils
from volttron.platform.messaging import headers as headers_mod
import time
from volttron.platform.messaging import topics


class AFDD:
    """
        Doc for AFDD
    """
    def __init__(self, agent, config_path):
        self._agent = agent
        self.init_algo_state()
        self.set_points_name(config_path)
    
    def init_algo_state(self):
        self._afdd0_ret = -1
        self._afdd1_ret = -1
        self._afdd2_ret = -1
        self._afdd3_ret = -1
        self._afdd4_ret = -1
        self._afdd5_ret = -1
        self._afdd6_ret = -1
        
    def set_points_name(self, config_path):
        config = utils.load_config(config_path)
        self.agent_id = config.get('agentid')
        #self.headers = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, 'requesterID': self.agent_id}
        self.headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': self.agent_id,
                    
            }
        self.rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
        self.smap_path = config.get('smap_path')
        
        ##From Configuration file
        #Controller Points
        self.volttron_flag = config.get('volttron_flag')
        self.oat_name = config.get('oat_point_name')
        self.rat_name = config.get('rat_point_name')
        self.mat_name = config.get('mat_point_name')
        self.dat_name = config.get('dat_point_name')
        self.fan_status_name =  config.get('fan_status_point_name')
        self.coolcall1_name = config.get('cool_call1_point_name')
        self.coolcall2_name = config.get('cool_call2_point_name')
        self.coolcmd1_name = config.get('cool_cmd1_point_name')
        self.coolcmd2_name = config.get('cool_cmd2_point_name')
        self.heat_cmd1_name = config.get('heat_command1_point_name')
        self.heat_cmd2_name = config.get('heat_command2_point_name')
        self.damper_name = config.get('damper_point_name')
        self.damper_command_name = config.get('damper_command_name')
        self.oat_bias_name = config.get('oat_bias')
        self.fan_speed = config.get('fan_command_name')
        self.mat_missing = config.get('mixed_air_sensor_missing')
    
        #Global parameters and thresholds
        self.oat_min = config.get('min_oa_temperature')
        self.oat_max = config.get('max_oa_temperature')
        self.rat_min = config.get('min_ra_temperature')
        self.rat_max = config.get('max_ra_temperature')
        self.mat_min = config.get('min_ma_temperature')
        self.mat_max = config.get('max_ma_temperature')
        self.seconds_to_steady_state = config.get('seconds_to_steady_state')
        self.minutes_to_average = config.get('minutes_to_average')
        self.cfm = config.get('cfm')
        self.EER = config.get('EER')
        self.economizertype = config.get('economizertype')
        self.high_limit = config.get('high_limit')
        
        self.afdd0_threshold = config.get('afdd0_mat_dat_consistency _threshold')
        
        #AFDD1 threshold
        self.afdd1_econ_threshold = config.get('afdd1_econ_temp_differential')
        self.afdd1_damper_threshold = config.get('afdd1_damper_modulation_threshold')
        
        #AFDD2 thresholds
        self.afdd2_temperature_sensor_threshold = config.get('afdd2_tempsensorfault_threshold')
        self.afdd2_oat_mat_threshold = config.get('afdd2_oat_mat_consistency_threshold')
        self.afdd2_rat_mat_threshold = config.get('afdd2_rat_mat_consistency_threshold')
        
        #AFDD3 thresholds
        self.afdd3_oaf_threshold = config.get('afdd3_oaf_threshold')
        self.afdd3_econ_differential = config.get('afdd3_econ_temp_differential')
        self.afdd3_temp_differential  = config.get('afdd3_oat_rat_temperature_difference_threshold')
        self.afdd3_open_damper_threshold = config.get('afdd3_open_damper_threshold')
        
        #AFDD4 thresholds
        self.afdd4_econ_differential = config.get('afdd4_econ_temp_differential')
        self.afdd4_min_damper = config.get('afdd4_minimum_damper_command')
        
        #AFDD5 thresholds
        self.afdd5_econ_differential = config.get('afdd5_econ_temp_differential')
        self.afdd5_temp_differential = config.get('afdd5_oat_rat_temperature_difference_threshold')
        self.afdd5_min_damper = config.get('afdd5_minimum_damper_command')
        self.afdd5_oaf_threshold = config.get('afdd5_oaf_threshold')
        self.minimum_oa = config.get('afdd5_minimum_oa')
        
        #AFDD6 thresholds
        self.afdd6_min_damper = config.get('afdd6_minimum_damper_command')
        self.afdd6_min_oa = config.get('afdd6_min_oa')
        self.afdd6_econ_differential = config.get('afdd6_econ_temp_differential')
        self.afdd6_temp_differential = config.get('afdd6_oat_rat_temperature_difference_threshold')
        self.afdd6_oaf_threshold = config.get('afdd6_oaf_threshold')
        log_filename = config.get('file_name')
        
        debug_flag = True
        if not debug_flag:
            self._log = logging.getLogger(__name__)
            logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                                format='%(asctime)s   %(levelname)-8s %(message)s',
                                datefmt='%m-%d-%y %H:%M:%S')
        else:
            self._log = logging.getLogger(__name__)
            logging.basicConfig(level=logging.debug, stream=sys.stderr,
                            format='%(asctime)s   %(levelname)-8s %(message)s',
                            datefmt= '%m-%d-%y %H:%M:%S',
                            filename=log_filename,
                            filemode='a+')
            fmt_str = '%(asctime)s   %(levelname)-8s    %(message)s'
            formatter = logging.Formatter(fmt_str,datefmt = '%m-%d-%y %H:%M:%S')
#             console = logging.StreamHandler()
#             console.setLevel(logging.DEBUG)
#             console.setFormatter(formatter)
#             logging.getLogger("").addHandler(console)
    
    def clean_up(self):
        self._log.debug("Cleaning up...")
        self._agent.command_equip(self.volttron_flag, 0.0)
        self._agent.is_running = False
        
    def publish_to_smap(self, smap_identifier, afdd_msg, smap_energyid, energy_impact):
        self._log.debug('Push to SMap - ' + smap_identifier + ': ' + str(afdd_msg) + '  Energy Impact: ' + str(energy_impact))
        mytime = int(time.time())
        if smap_energyid is not None:
            content = {
                smap_identifier: {
                     "Readings": [[mytime, afdd_msg]],
                     "Units": "TU",
                     "data_type": "double"
                 },
                  smap_energyid: {
                     "Readings": [[mytime, energy_impact]],
                     "Units": "kWh",
                     "data_type": "double"}
             }
        else:
            content = {
                smap_identifier: {
                     "Readings": [[mytime, afdd_msg]],
                     "Units": "TU",
                     "data_type": "double"
                 }
            }
        self._agent.publish(self.smap_path, self.headers, jsonapi.dumps(content))

    def run(self):
        
        #Testing function for unit tests
        #status = self._agent.command_equip(self.volttron_flag, 2.0)
#         status = self._agent.command_equip(self.volttron_flag, 0.0)
#         headers = {
#              headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
#            'requesterID': self.agent_id}
        #self._agent.publish(topics.ACTUATOR_LOCK_RELEASE(**self.rtu_path), headers)
        #status = self.command_volttron_flag(0.0)
        #print status
        print 'Test1 complete'   
        status = self._agent.command_equip('HeatingTemperatureStPt', 55.0)
        print status
#         status = self._agent.command_equip('CoolingTemperatureStPt', 65.0)

    def run_all(self):
        try:
            status = False
            self._afdd_ret = 70.0 #Normal
            self.headers[headers_mod.FROM] = self.agent_id
            self.headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
            data = self._agent.get_new_data()
            fan_status = int(data[self.fan_status_name])

            if not fan_status:
                self.command_volttron_flag(1.0)
                self._agent.sleep(120)
                data = self._agent.get_new_data()
                
            fan_status = int(data[self.fan_status_name])
            oa_temp = float(data[self.oat_name])
            ra_temp = float(data[self.rat_name])  
            if not self.mat_missing:
                mat_name = self.mat_name
            elif self.mat_missing:
                mat_name = self.dat_name
            ma_temp = float(data[mat_name])    
          
            
            if (oa_temp <= self.oat_min or oa_temp >= self.oat_max):
                self._log.debug("Conditions not favorable for fault detection")
                self._afdd_ret = 71.0
            if(ra_temp <= self.rat_min or ra_temp >= self.rat_max):
                self._log.debug("Conditions not favorable for fault detection")
                self._afdd_ret = 72.0
            if ((ma_temp <= self.mat_min or ma_temp >= self.mat_max) and not self.mat_missing):
                self._log.debug("Conditions not favorable for fault detection")
                self._afdd_ret = 73.0
            if not fan_status:
                self._log.debug("Conditions not favorable for fault detection")
                self._afdd_ret = 74.0
                 
            self.publish_to_smap("AFDD Error", self._afdd_ret, None, None)
            if self._afdd_ret > 70.0:
                return self._afdd_ret
             
            #AFDD0
            status = self.command_volttron_flag(1.0)
            if not status:
                self.publish_to_smap("AFDD Error", 75.0, None, None)
                return
            self._agent.sleep(self.seconds_to_steady_state)
            
            self._afdd0_ret = self.afdd0()
            self.publish_to_smap("AFDD0 Error", self._afdd0_ret, None, None)
                  
            data = self._agent.get_new_data()
            oa_temp = float(data[self.oat_name])
            ra_temp = float(data[self.rat_name])
            #AFDD1 
            if math.fabs(oa_temp - ra_temp) > self.afdd1_econ_threshold: 
                self._afdd1_ret = self.afdd1()
            else:
                self._afdd1_ret = 11.0
 
            self.publish_to_smap("AFDD1 Error", self._afdd1_ret, None, None)
     
            if self._afdd1_ret == 12.0:  #will need to update when decimal messages added
                self._afdd2_ret = 21.0
                self.publish_to_smap("AFDD2 Error", self._afdd2_ret, None, None)
                return self._afdd2_ret
            else: #run AFDD2
                self._afdd2_ret = self.afdd2()
            self.publish_to_smap("AFDD2 Error", self._afdd2_ret, None, None)
             
            if self._afdd2_ret >= 24.0:  
                self._afdd3_ret = 36.0
                self.publish_to_smap("AFDD3 Error", self._afdd3_ret, "AFDD3 Energy Impact", -99.0)
                return self._afdd3_ret
            
            flag_status = self._agent.command_equip(self.volttron_flag, 2.0, 60)
            if True not in flag_status:
                status = self.command_volttron_flag(2.0)
                if not status:
                    self.publish_to_smap("AFDD Error", 75.0, None, None)
                    return
                
            oabias_status = self._agent.command_equip(self.oat_bias_name, 0.0, 60)
            if True not in oabias_status:
                status = self.command_outdoor_air_temperature_bias(0.0)
                if not status:
                    self.publish_to_smap("AFDD Error", 75.0, None, None)
                    return
            
            
            data = self._agent.get_new_data()
            cool_call1 = float(data[self.coolcall1_name])
            if cool_call1 > 0: 
                heat_cmd1 = float(data[self.heat_cmd1_name])
                heat_cmd2=float(data[self.heat_cmd2_name])
                oa_temp = float(data[self.oat_name])
                ra_temp = float(data[self.rat_name])
                if (math.fabs(oa_temp-ra_temp) > self.afdd3_temp_differential and 
                   (heat_cmd1 < 1 and heat_cmd2 < 1)):
                    self._afdd3_ret,afdd3_energy_impact = self.afdd3()
                else:
                    self._afdd3_ret = 34.0
                    afdd3_energy_impact = -99.0
            else:
                self._afdd3_ret = 31.0
                afdd3_energy_impact = -99.0
                
            self.publish_to_smap("AFDD3 Error", self._afdd3_ret, 
                                 "AFDD3 Energy Impact", afdd3_energy_impact)
        
            #AFDD4
            oabias_status = self._agent.command_equip(self.oat_bias_name, 0.0, 60)
            if True not in oabias_status:
                status = self.command_outdoor_air_temperature_bias(0.0)
                if not status:
                    self.publish_to_smap("AFDD Error", 75.0, None, None)
                    return
            
            data = self._agent.get_new_data()
            heat_cmd1 = float(data[self.heat_cmd1_name])
            heat_cmd2 = float(data[self.heat_cmd2_name])
            if (heat_cmd1 < 1 and heat_cmd2 < 1):
                self._afdd4_ret, afdd4_energy_impact = self.afdd4()
            else:
                self._afdd4_ret = 42.0
                afdd4_energy_impact = -99.0
                 
            #AFDD5
            self.publish_to_smap("AFDD4 Error", self._afdd4_ret, 
                                 "AFDD4 Energy Impact", afdd4_energy_impact)
            
            oabias_status = self._agent.command_equip(self.oat_bias_name, 0, 60)
            if True not in oabias_status:
                status = self.command_outdoor_air_temperature_bias(0.0)
                if not status:
                    self.publish_to_smap("AFDD Error", 75.0, None, None)
                    return
                
            data = self._agent.get_new_data()
            oa_temp = float(data[ self.oat_name])
            ra_temp = float(data[self.rat_name])
            if math.fabs(oa_temp-ra_temp) > self.afdd5_temp_differential:
                self._afdd5_ret, afdd5_energy_impact = self.afdd5()
            else:
                self._afdd5_ret = 52.0
                afdd5_energy_impact = -99.0
            self.publish_to_smap("AFDD5 Error", self._afdd5_ret, 
                                 "AFDD5 Energy Impact", afdd5_energy_impact)
            
            #AFDD6
            oabias_status = self._agent.command_equip(self.oat_bias_name, 0, 60)
            if True not in oabias_status:
                status = self.command_outdoor_air_temperature_bias(0.0)
                if not status:
                    self.publish_to_smap("AFDD Error", 75.0, None, None)
                    return
            
            data = self._agent.get_new_data()
            oa_temp = float(data[ self.oat_name])
            ra_temp = float(data[self.rat_name])
            if math.fabs(oa_temp-ra_temp) > self.afdd6_temp_differential:
                self._afdd6_ret = self.afdd6()
            else:
                self._afdd6_ret = 62.0
            self.publish_to_smap("AFDD6 Error", self._afdd6_ret, None, None)
            
            oabias_status = self._agent.command_equip(self.oat_bias_name, 0, 60)
            if True not in oabias_status:
                status = self.command_outdoor_air_temperature_bias(0.0)
                if not status:
                    self.publish_to_smap("AFDD Error", 75.0, None, None)
                    return
            
            #Loop AFDD3
            while self._afdd3_ret < 0 or self._afdd3_ret == 31.0:
                data = self._agent.get_new_data()
                cool_call1 = float(data[self.coolcall1_name])
                if cool_call1 > 0: 
                    heat_cmd1 = float(data[self.heat_cmd1_name])
                    heat_cmd2=float(data[self.heat_cmd2_name])
                    oa_temp = float(data[ self.oat_name])
                    ra_temp = float(data[self.rat_name])
                    if (math.fabs(oa_temp-ra_temp) > self.afdd3_econ_differential and 
                    (heat_cmd1 < 1 and heat_cmd2 < 1)):
                        self._afdd3_ret,afdd3_energy_impact = self.afdd3()
                    else:
                        self._afdd3_ret = 34.0
                        afdd3_energy_impact = -99.0
                else:
                    self._afdd3_ret = 31.0
                    afdd3_energy_impact = -99.0
            self.publish_to_smap("AFDD3 Error", self._afdd3_ret, 
                                 "AFDD3 Energy Impact", afdd3_energy_impact)    
        finally:
            self.clean_up()
    
    def sensor_error_check(self, mat_name):
        status = False
        volttron_data = self._agent.get_new_data()
        ra_temp = float(volttron_data[self.rat_name])
        outdoor_temp = float(volttron_data[ self.oat_name])
        mixed_temp = float(volttron_data[mat_name])
        if (mixed_temp < outdoor_temp and mixed_temp < ra_temp):
            status = True
            return status
        if (mixed_temp > outdoor_temp and mixed_temp > ra_temp):
            status = True
            return status
        return status
    
    def command_damper(self,command):
        """ Command outdoor air damper to a new position """
        status = self._agent.command_equip(self.damper_command_name,command, 60)
        while True not in status:
            self._agent.sleep(30)
            status = self._agent.command_equip(self.damper_command_name,command, 60)
            if True in status:
                status = self._agent.command_equip(self.volttron_flag, 1.0)
        if True in status:
            self._agent.sleep(60)
            volttron_data = self._agent.get_new_data()
            damper = int(volttron_data[self.damper_name])
            if math.fabs(damper - command) < 5:
                status = True
            else:
                status = False
        return status
    
    def oad_modulation_check(self,num_minutes, point_name1, point_name2):
        diff = 0.
        temp_value1 = 0.
        temp_value2 = 0.
        
        for n in xrange(num_minutes):
            volttron_data = self._agent.get_new_data()
            temp_value1 = float(volttron_data[point_name1]) # Point name follows RTUNetwork wiki)
            temp_value2 = float(volttron_data[point_name2]) # Point name follows RTUNetwork wiki)
            diff +=math.fabs(temp_value1 - temp_value2)
            cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            heat_cmd1 = int(volttron_data[self.heat_cmd1_name]) 
            if cool_cmd1 or heat_cmd1:
                return 'Lock Failure'
        diff = diff/num_minutes
        return diff
    
    
    def get_rtu_status(self):
        """ 
        Check heating and cooling status.  If the unit either heating or cooling, turn it off 
        """
        status = False
        volttron_data = self._agent.get_new_data()
        cool_cmd1 = int(volttron_data[self.coolcmd1_name]) 
        cool_cmd2 = int(volttron_data[self.coolcmd2_name]) 
        heat_cmd1 = int(volttron_data[self.heat_cmd1_name]) 
        heat_cmd2 = int(volttron_data[self.heat_cmd2_name]) 
        if (cool_cmd1  or cool_cmd1 or heat_cmd1 or heat_cmd2): 
            status = True

        return status

    def absolute_diff_ma_da(self, num_minutes, flag):
        # get the VOLTTRON data
        diff_da_ma = 0.
        if self.mat_missing and flag == 1.0:
            mat_name = self.oat_name
        elif self.mat_missing and flag == 2.0:
            mat_name = self.rat_name
        else:
            mat_name = self.mat_name  
            
        for n in xrange(num_minutes):
            volttron_data = self._agent.get_new_data()
            mixed_temp = float(volttron_data[mat_name])
            discharge_temp = float(volttron_data[self.dat_name])
            diff_da_ma += math.fabs(discharge_temp - mixed_temp)
            cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            heat_cmd1 = int(volttron_data[self.heat_cmd1_name]) 
            if cool_cmd1 or heat_cmd1:
                return 'Lock Failure'
        diff_da_ma = diff_da_ma/num_minutes
        return diff_da_ma

    def command_outdoor_air_temperature_bias(self,value):
        """ Command OutsideAirBias"""
        status = self._agent.command_equip(self.oat_bias_name, value, 60)
        while True not in status:
            self._agent.sleep(30)
            status = self._agent.command_equip(self.oat_bias_name, value, 60)
            if True in status:
                status = self._agent.command_equip(self.volttron_flag, 2.0)
                
        if True in status:
            self._agent.sleep(60)
            volttron_data = self._agent.get_new_data()
            oat_bias = float(volttron_data[self.oat_bias_name])
            
            if math.fabs(oat_bias - value) < 1.0:
                status = True
            else:
                status = False
        return status
    
    def command_volttron_flag(self,value):
        """ Command VOLTTRON Flag"""
        status = self._agent.command_equip(self.volttron_flag, value)
        while True not in status:
            print 'in loop'
            self._agent.sleep(30)
            status = self._agent.command_equip(self.volttron_flag, value, 60)
            print status
        if True in status: 
            self._agent.sleep(60)
            volttron_data = self._agent.get_new_data()
            volttron_flag = int(volttron_data[self.volttron_flag])
            
            if math.fabs(volttron_flag - value) == 0:
                status = True
            else:
                status = False
        return status
    
    def afdd0(self):
        #make sure compressor is shutdown
        for n in xrange(self.minutes_to_average): 
            status = self.get_rtu_status() 
            if not status: 
                break
        if (n == self.minutes_to_average - 1 and status):
            ## compressor is still running...
            ## exit the function
            self._log.debug("Compressor is running, can not complete diagnostic")
            return 3.0
            #Continue with processing.   
            # Need to open damper (OAD) all the way
            #Command outdoor air damper to fully open position
 
        if self.command_damper(100.0): # fully open position
            # Verify steady-state conditions
            # wait for steady-state conditions to be established
            self._agent.sleep(self.seconds_to_steady_state)
        else:
            self._log.debug("Unsuccessful at commanding damper to fully open position, can not complete diagnostic")
            return 4.0
       
        abs_diff1 = self.absolute_diff_ma_da(self.minutes_to_average,1.0) 
        
        if abs_diff1 == 'Lock Failure':
            self._log.debug("Compressor or heat is running, can not complete diagnostic")
            return 3.0
        
        if self.command_damper(0.0): # fully open position
        # Verify steady-state condition
        # wait for steady-state conditions to be established
            self._agent.sleep(self.seconds_to_steady_state)
        else:
            self._log.debug("Unsuccessful at commanding damper to fully closed position, can not complete diagnostic")
            return 4.0
            
        abs_diff2 = self.absolute_diff_ma_da(self.minutes_to_average,2.0)
        
        if abs_diff2 == 'Lock Failure':
            self._log.debug("Compressor or heat is running, can not complete diagnostic")
            return 3.0
        
        abs_diff = (abs_diff1 + abs_diff2)/2
        
        if(abs_diff < self.afdd0_threshold):
            self._log.debug("No Fault Detected during diagnostic 0")
            return 0.0
        if self.mat_missing:
            self._log.debug('Temperature sensor inconsistency')
            return 5.0
        self._log.debug("Mixed-air temperature and discharge-air temperature are not consistent when mechanical cooling and heating are off")
        return 2.0

    def afdd1(self):
     
        volttron_data = self._agent.get_new_data()
        damper = int(volttron_data[self.damper_name])
        cool_cmd1 = int(volttron_data[self.coolcmd1_name])
        heat_cmd1 = int(volttron_data[self.heat_cmd1_name]) 
        
        if cool_cmd1 or heat_cmd1:
            self._log.debug("Compressor or heating is running, can not complete diagnostic")
            return 13.0
        #Command outdoor air damper to fully closed position
        if damper != 0: 
            if not self.command_damper(0.0):
                self._log.debug("Unsuccessful at commanding damper to fully closed position, can not complete diagnostic")
                return 14.0 
            
            self._agent.sleep(self.seconds_to_steady_state)
            
        if not self.mat_missing:
            mat_name = self.mat_name
        else:
            mat_name = self.dat_name
                
        diff_rat_mat = self.oad_modulation_check(self.minutes_to_average,
                                                     self.rat_name , mat_name)
        if diff_rat_mat == 'Lock Failure':
            self._log.debug("Compressor is running, can not complete diagnostic")
            return 13.0
        if not self.command_damper(100.0): # fully open position
            # wait for steady-state conditions to be established
            # Verify steady-state condition
            self._log.debug("Unsuccessful at commanding damper to open position, can not complete diagnostic")
            return 14.0
        self._agent.sleep(self.seconds_to_steady_state)
        diff_oat_mat = self.oad_modulation_check(self.minutes_to_average, 
                                                     self.oat_name, mat_name)
        if diff_oat_mat == 'Lock Failure':
            self._log.debug("Compressor is running, can not complete diagnostic")
            return 13.0
        
        diff_average = (diff_oat_mat + diff_rat_mat)/2
            
        if (diff_average > self.afdd1_damper_threshold):
            self._log.debug("No Modulation of outdoor-air damper")
            return 12.0
        self._log.debug("Outdoor-air damper is modulating, no fault detected")
        return 10.0

    def afdd2(self):
        #check for temperature sensor error
        if self.mat_missing:
            mat_name = self.dat_name
        else:
            mat_name = self.mat_name
            
        volttron_data = self._agent.get_new_data()
        damper = int(volttron_data[self.damper_name])
        cool_cmd1 = int(volttron_data[self.coolcmd1_name])
        heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
        if cool_cmd1 or heat_cmd1:
            return 23.0
        
        status = self.sensor_error_check(mat_name)
        
        if (status):
            if damper != 100: 
                if not self.command_damper(100.0):
                    self._log.debug("Unsuccessful at commanding damper to open position, can not complete diagnostic")
                    return 22.0 
                self._agent.sleep(self.seconds_to_steady_state)
                
            volttron_data = self._agent.get_new_data()
            cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
            
            if cool_cmd1 or heat_cmd1:
                return 23.0
            
            oa_temp = float(volttron_data[self.oat_name])
            ma_temp = float(volttron_data[mat_name])
            sensorcondition_1 = math.fabs(ma_temp - oa_temp)
            #Check for return-air temperature fault
           
            if sensorcondition_1 < self.afdd2_oat_mat_threshold:
                self._log.debug("Return-air temperature sensor problem")
                return 25.0
            #close damper and wait for steady state conditions
            #if damper did not close cannot complete diagnostic
            if not self.command_damper(0.0):
                self._log.debug("Lock not Received from controller to open damper")
                return 22.0

            self._agent.sleep(self.seconds_to_steady_state)
            
            volttron_data = self._agent.get_new_data()
            cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
            
            if cool_cmd1 or heat_cmd1:
                return 23.0
            
            ra_temp = float(volttron_data[self.rat_name])
            ma_temp = float(volttron_data[mat_name]) 
            
            sensorcondition_2 = math.fabs(ma_temp-ra_temp)# probably should do average over a number of minutes
            #check for outside-air temperature sensor fault
            
            if sensorcondition_2 < self.afdd2_rat_mat_threshold:
                self._log.debug("Outside-air temperature sensor problem")
                return 24.0
    
            #If it comes here => both tests fail
            if self.mat_missing:
                self._log.debug("discharge-air temperature sensor problem")
                return 27.0
           
            self._log.debug("Mixed-air temperature sensor problem")
            return 26.0
        
        self._log.debug("No Temperature Sensor faults detected")
        return 20.0
    
    #Diagnostic to determine if RTU is Economizing when it should
    def afdd3(self):
        potential_cooling_savings = -99.0
        if self.mat_missing:
            mat_name = self.dat_name
        else:
            mat_name = self.mat_name
  
        volttron_data = self._agent.get_new_data()
        cool_call1 = int(volttron_data[self.coolcall1_name])
        ma_temp = float(volttron_data[mat_name])
        ra_temp = float(volttron_data[self.rat_name])
        oa_temp = float(volttron_data[self.oat_name])
        damper = float(volttron_data[self.damper_name])
        heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
        fan_speed = float(volttron_data[self.fan_speed])
        cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            
        # Main Algorithm
        if not heat_cmd1:
            if cool_call1:
                if (((oa_temp + self.afdd3_econ_differential) < ra_temp and oa_temp > self.high_limit and self.economizertype==0) or 
                    (oa_temp + self.afdd3_econ_differential) < self.high_limit): #Are economizer conditions favorable
                    if math.fabs(100.0 - damper) < self.afdd3_open_damper_threshold: # is the damper fully open
                        if (self.mat_missing and not cool_cmd1) or not self.mat_missing:
                            oaf = 0.0
                            avg_fanspeed = 0.0
                            for n in xrange(self.minutes_to_average):
                                ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki
                                ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                                oa_temp = float(volttron_data[ self.oat_name])
                                oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                                avg_fanspeed += fan_speed
                                volttron_data = self._agent.get_new_data()
                                cool_call1 = int(volttron_data[self.coolcall1_name])
                                fan_speed = float(volttron_data[self.fan_speed])
                                cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                                if not cool_call1 or (self.mat_missing and cool_cmd1):
                                    break
                                
                            if oaf < 0 or oaf > 1.25:
                                self._log.debug("Unexpected value calculated for OAF")
                                return 36.0, potential_cooling_savings
                            
                            oaf = oaf/(n + 1)
                            avg_fanspeed = avg_fanspeed/(n + 1)
                            self._log.debug('OAF: ' + str(oaf))
                            if 1.0 - oaf > self.afdd3_oaf_threshold:
                                if not self.mat_missing:
                                    potential_cooling_savings = 1.08 * self.cfm *(avg_fanspeed/100) * (ma_temp - oa_temp) #sensible cooling load estimation in BTU/hr
                                    potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                                    print 'fault kWh impact: ', potential_cooling_savings
                                self._log.debug("Insufficient outdoor air when economizing")
                                return 32.0, potential_cooling_savings
                            else:
                                self._log.debug("Economizer functioning properly")
                                return 30.0, 0.0
                        else:
                            return 30.0, 0.0
                    else:
                        if not self.mat_missing:
                            potential_cooling_savings = 1.08 * self.cfm * (fan_speed/100) * (ma_temp - oa_temp) #sensible cooling load estimation
                            potential_cooling_savings = potential_cooling_savings/(1000*self.EER) #kWh/h estimation
                            print 'fault kWh impact: ', potential_cooling_savings
                        self._log.debug("Outdoor-air damper is not fully open when outdoor conditions are favorable for economizing")
                        return 33.0, potential_cooling_savings
                else:#If conditions are not favorable for economizing
                    oa_bias = min(self.high_limit - (oa_temp + self.afdd3_econ_differential * 5), ra_temp - (oa_temp + self.afdd3_econ_differential * 5)) #Set OAT to favorable for economizing
                    status = self.command_outdoor_air_temperature_bias(oa_bias)
                    if not (status):
                        self._log.debug("Outside-air temperature bias was not set, controller lock error")    
                        return 35.0, potential_cooling_savings
                    
                    self._agent.sleep(self.seconds_to_steady_state)
                     
                    volttron_data = self._agent.get_new_data()
                    heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
                    
                    if heat_cmd1:
                        log.debug('Unit is no longer cooling, retry diagnostic')    
                        return 34.0, -99.0
                        
                    cool_call1 = int(volttron_data[self.coolcall1_name])
                    damper = float(volttron_data[self.damper_name])
                    fan_speed = float(volttron_data[self.fan_speed])
                    cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                    if cool_call1:
                        if math.fabs(100.0 - damper) < self.afdd3_open_damper_threshold: # is the damper fully open
                            if (self.mat_missing and not cool_cmd1) or not self.mat_missing:
                                oaf = 0.0
                                avg_fanspeed = 0.0
                                for n in xrange(self.minutes_to_average):
                                    ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki)
                                    ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                                    oa_temp = float(volttron_data[ self.oat_name]) - oa_bias
                                    oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                                    avg_fanspeed += fan_speed
                                    volttron_data = self._agent.get_new_data()
                                    cool_call1 = int(volttron_data[self.coolcall1_name])
                                    fan_speed = float(volttron_data[self.fan_speed])
                                    cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                                    if not cool_call1 or (self.mat_missing and cool_cmd1):
                                        break
                                    
                                if oaf < 0 or oaf > 1.25:
                                    self._log.debug("Unexpected value calculated for OAF")
                                    return 36.0, potential_cooling_savings
                                
                                oaf = oaf/(n + 1)
                                avg_fanspeed = fan_speed/(n + 1)
                                self._log.debug('OAF: ' + str(oaf))
                                if 1.0 - oaf > self.afdd3_oaf_threshold:
                                    if not self.mat_missing:
                                        ma_temp = float(volttron_data[mat_name])
                                        oa_temp = float(volttron_data[ self.oat_name]) - oa_bias
                                        potential_cooling_savings = 1.08 * self.cfm * (avg_fanspeed/100) * (ma_temp - oa_temp) #sensible cooling load estimation
                                        potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                                        print 'fault kWh impact: ', potential_cooling_savings
                                    self._log.debug("Insufficient outdoor air when economizing")
                                    return 32.0, potential_cooling_savings
                                else:
                                    self._log.debug("Economizer functioning properly")
                                    return 30.0, 0.0
                            else:
                                return 30.0, 0.0
                        else:
                            if not self.mat_missing:
                                ma_temp = float(volttron_data[mat_name])
                                oa_temp = float(volttron_data[ self.oat_name]) - oa_bias
                                potential_cooling_savings = 1.08 * self.cfm * (fan_speed/100) * (ma_temp-oa_temp) #sensible cooling load estimation
                                potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                                print 'fault kWh impact: ', potential_cooling_savings
                            self._log.debug("Outdoor-air damper is not fully open when outdoor conditions are favorable for economizing")
                            return 33.0, potential_cooling_savings
                    else:
                        self._log.debug('Unit is no longer cooling, retry diagnostic')
                        return 31.0, potential_cooling_savings
            else:
                self._log.debug('Unit is no longer cooling, retry diagnostic')
                return 31.0, potential_cooling_savings   
        self._log.debug('Unit is no longer cooling, retry diagnostic')    
        return 34.0, -99.0
                    
    #Diagnostic to determine if RTU is economizing when it should not
    def afdd4(self):
        potential_cooling_savings = -99.0
        volttron_data = self._agent.get_new_data()
        oa_temp = float(volttron_data[ self.oat_name])
        ra_temp = float(volttron_data[self.rat_name])
        cool_call1 = int(volttron_data[self.coolcall1_name])
        heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
        fan_speed = float(volttron_data[self.fan_speed])
        
        # Main Algorithm
        if not heat_cmd1:
            if cool_call1: # Is there a call for cooling for RTU
                if (((oa_temp - self.afdd4_econ_differential) < ra_temp and self.economizertype == 0) or 
                    (oa_temp - self.afdd4_econ_differential) < self.high_limit): #Check if conditions are favorable for economizing
                    oa_bias = max(ra_temp - (oa_temp - self.afdd4_econ_differential * 5.0), self.high_limit - oa_temp + self.afdd4_econ_differential * 5.0)
                    status = self.command_outdoor_air_temperature_bias(oa_bias)
                    if not status:
                        self._log.debug("Outside-air temperature bias was not set, controller lock error")
                        return 43.0, potential_cooling_savings
                    
                    self._agent.sleep(self.seconds_to_steady_state)
                    volttron_data = self._agent.get_new_data()
                    heat_cmd1 = int(volttron_data[self.heat_cmd1_name])
                    if heat_cmd1:
                        self._log.debug('Unit began heating, try diagnostic again later')
                        return 42.0, -99.0
                    cool_call1 = int(volttron_data[self.coolcall1_name])
                    damper = float(volttron_data[self.damper_name]) # damper should be at minimum
                    fan_speed = float(volttron_data[self.fan_speed])
                    
                    if cool_call1 and damper <= self.afdd4_min_damper:
                        self._log.debug("Economizer controls functioning properly")
                        return 40.0, 0.0
                    elif cool_call1 and damper > self.afdd4_min_damper:
                        if not self.mat_missing:
                            oa_temp = float(volttron_data[ self.oat_name])- oa_bias
                            ma_temp = float(volttron_data[self.mat_name])
                            ra_temp = float(volttron_data[self.rat_name])
                            potential_cooling_savings = 1.08 * self.cfm * (fan_speed/100) * ((0.05 * oa_temp + 0.95 * ra_temp) - ma_temp) #sensible cooling load estimation in BTU/hr
                            potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                            print 'fault kWh impact: ', potential_cooling_savings
                        self._log.debug("Damper should be at minimum but is commanded open, potentially wasting energy")
                        return 41.0, potential_cooling_savings
                    elif not cool_call1 and damper <= self.afdd4_min_damper:
                        self._log.debug('Unit is not cooling and damper is at minimum for ventilation')
                        return 40.0, 0.0
                else: #Conditions are not favorable for economizing
                    damper = float(volttron_data[self.damper_name]) #damper should be at minimum
                    if damper <= self.afdd4_min_damper:#damper should be at minimum
                        self._log.debug("Economizer controls functioning properly")
                        return 40.0, 0.0
                    else:
                        if not self.mat_missing:
                            oa_temp = float(volttron_data[ self.oat_name]) 
                            ma_temp = float(volttron_data[self.mat_name])
                            ra_temp = float(volttron_data[self.rat_name])
                            potential_cooling_savings = 1.08*self.cfm * (fan_speed/100) * ((0.05  *oa_temp+ 0.95 * ra_temp)- ma_temp) #sensible cooling load estimation in BTU/hr
                            potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                            print 'fault kWh impact: ', potential_cooling_savings
                        self._log.debug("Damper should be at minimum but is commanded open, potentially wasting energy")
                        return 41.0, potential_cooling_savings
            else: #There is not a call for cooling for the RTU
                damper = float(volttron_data[self.damper_name]) 
                if damper <= self.afdd4_min_damper: #damper should be at minimum
                    self._log.debug('Unit is not cooling and damper is at minimum for ventilation')
                    return 40.0, 0.0
                else:
                    if not self.mat_missing:
                        oa_temp = float(volttron_data[ self.oat_name])
                        ma_temp = float(volttron_data[self.mat_name])
                        ra_temp = float(volttron_data[self.rat_name])
                        potential_cooling_savings = 1.08 * self.cfm * (fan_speed/100) * ((0.05*oa_temp + 0.95*ra_temp)-ma_temp) #sensible cooling load estimation in BTU/hr
                        potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                        print 'fault kWh impact: ', potential_cooling_savings
                    self._log.debug("Damper should be at minimum but is commanded open, potentially wasting energy")
                    return 41.0, potential_cooling_savings
        self._log.debug('Unit began heating, try diagnostic again later')
        return 42.0, -99.0
            
    #Excess outside-air diagnostic
    def afdd5(self):
        potential_cooling_savings = -99.0
        if self.mat_missing:
            mat_name = self.dat_name
        else:
            mat_name = self.mat_name
            
        volttron_data = self._agent.get_new_data()
        damper = float(volttron_data[self.damper_name])
        ma_temp = float(volttron_data[mat_name])
        oa_temp = float(volttron_data[ self.oat_name])
        ra_temp  = float(volttron_data[self.rat_name])
        cool_call1 = int(volttron_data[self.coolcall1_name])
        cool_call2 = int(volttron_data[self.coolcall2_name])
        fan_speed = float(volttron_data[self.fan_speed])
        cool_cmd1 = int(volttron_data[self.coolcmd1_name])

        if  not cool_call1 :  #if there is no call or cooling air intake should be at ventilation minimum
            if (damper <= self.afdd5_min_damper):
                oaf = 0.0  # check OAF 
                avg_fanspeed = 0.0
                for n in xrange(self.minutes_to_average):
                    ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki)
                    ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                    oa_temp = float(volttron_data[ self.oat_name])
                    oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                    avg_fanspeed += fan_speed
                    volttron_data = self._agent.get_new_data()
                    cool_call1 = int(volttron_data[self.coolcall1_name])
                    fan_speed = float(volttron_data[self.fan_speed])
                    if cool_call1:
                        break
                    
                if oaf < 0 or oaf > 1.25:
                    self._log.debug("Unexpected value calculated for OAF")
                    return 56.0, potential_cooling_savings
                
                oaf = oaf/(n + 1)
                avg_fanspeed = avg_fanspeed/(n + 1)
                self._log.debug('OAF: ' + str(oaf))
                if(oaf - self.minimum_oa > self.afdd5_oaf_threshold): # Check to see if excess air is being brought into RTU
                    if not self.mat_missing:
                        ma_temp = float(volttron_data[mat_name])
                        oa_temp = float(volttron_data[ self.oat_name])
                        ra_temp  = float(volttron_data[self.rat_name])
                        potential_cooling_savings = 1.08 * self.cfm * (avg_fanspeed/100) * ((0.05 * oa_temp + 0.95 * ra_temp) - ma_temp)
                        potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                        print 'fault kWh impact: ', potential_cooling_savings
                    self._log.debug("Excessive outdoor-air intake")
                    return 51.0, potential_cooling_savings
                else:
                    self._log.debug("No fault detected during fault diagnostic")
                    return 50.0, 0.0 
            else:
                self._log.debug("Damper should be at minimum, possible control fault")
                return 53.0, potential_cooling_savings
        else: #Cooling is on 
            if (((oa_temp - self.afdd5_econ_differential) > ra_temp and
                (oa_temp - self.afdd5_econ_differential) > self.high_limit and self.economizertype == 0) or
                ((oa_temp - self.afdd5_econ_differential) > self.high_limit and self.economizertype == 1)): #Check economizer conditions
                if (damper > self.afdd5_min_damper): #Damper should be at minimum
                    self._log.debug("Damper should be at minimum, possible control fault")
                    return 53.0, potential_cooling_savings
                #OAF= [(ma_temp -ra_temp )/(oa_temp -ra_temp )]
                if (self.mat_missing and not cool_cmd1) or not self.mat_missing:
                    oaf = 0.0
                    avg_fanspeed = 0.0
                    for n in xrange(self.minutes_to_average):
                        ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki
                        ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki
                        oa_temp = float(volttron_data[ self.oat_name])
                        oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                        avg_fanspeed += fan_speed
                        volttron_data = self._agent.get_new_data()
                        cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                        cool_call1 = int(volttron_data[self.coolcall1_name])
                        fan_speed = float(volttron_data[self.fan_speed])
                        if not cool_call1 or (self.mat_missing and cool_cmd1):
                            break
                        
                    if oaf < 0 or oaf > 1.25:
                        self._log.debug("Unexpected value calculated for OAF")
                        return 56.0, potential_cooling_savings
                    
                    oaf = oaf/(n + 1)
                    avg_fanspeed = avg_fanspeed/(n + 1)
                    self._log.debug('OAF: ' + str(oaf))
                    if(oaf - self.minimum_oa > self.afdd5_oaf_threshold): #Check to see if excess air is being brought into RTU
                        if not self.mat_missing:
                            ma_temp = float(volttron_data[mat_name])
                            oa_temp = float(volttron_data[ self.oat_name])
                            ra_temp  = float(volttron_data[self.rat_name])
                            potential_cooling_savings = 1.08 * self.cfm * (avg_fanspeed/100) * ((0.05 * oa_temp + 0.95 * ra_temp) - ma_temp)
                            potential_cooling_savings = potential_cooling_savings/(1000 * self.EER)
                            print 'fault kWh impact: ', potential_cooling_savings
                        self._log.debug("Excessive outdoor-air intake")
                        return 51.0, potential_cooling_savings
                    else:
                        self._log.debug("No fault detected during fault diagnostic")
                        return 50.0, 0.0
                else:
                    return 50.0, 0.0
            else:
                oa_bias = max(ra_temp - (oa_temp - self.afdd5_econ_differential * 5.0), self.high_limit - oa_temp + self.afdd5_econ_differential * 5.0)
                status = self.command_outdoor_air_temperature_bias(oa_bias)
                if not (status):
                    self._log.debug("Outside-air temperature bias was not set, controller lock error")    
                    return 54.0, potential_cooling_savings
            
                self._agent.sleep(self.seconds_to_steady_state)
                volttron_data = self._agent.get_new_data()
                cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                ma_temp = float(volttron_data[mat_name])
                oa_temp = float(volttron_data[ self.oat_name]) - oa_bias
                ra_temp  = float(volttron_data[self.rat_name])
                damper = float(volttron_data[self.damper_name])
                fan_speed = float(volttron_data[self.fan_speed])
                cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            
                if damper > self.afdd5_min_damper:
                    self._log.debug("Damper will not close, possible control fault")
                    if not self.mat_missing:
                        potential_cooling_savings = 1.08 * self.cfm * (fan_speed/100) * ((0.05 * oa_temp + 0.95 * ra_temp) - ma_temp)
                        potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                    return 53.0, potential_cooling_savings
                if (self.mat_missing and not cool_cmd1) or not self.mat_missing:
                    oaf = 0.0
                    avg_fanspeed = 0.0
                    for n in xrange(self.minutes_to_average):
                        cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                        if (self.mat_missing and cool_cmd1):
                            break
                        fan_speed = float(volttron_data[self.fan_speed])
                        ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki)
                        ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                        oa_temp = float(volttron_data[ self.oat_name]) - oa_bias
                        oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                        avg_fanspeed += fan_speed
                        if (n+1) < self.minutes_to_average:
                            volttron_data = self._agent.get_new_data()
                            
                    if oaf < 0 or oaf > 1.25:
                        self._log.debug("Unexpected value calculated for OAF")
                        return 56.0, potential_cooling_savings
                    
                    oaf = oaf/(n + 1)
                    avg_fanspeed = avg_fanspeed/(n + 1)
                    self._log.debug('OAF: ' + str(oaf))
                    if(oaf - self.minimum_oa > self.afdd5_oaf_threshold):
                        if not self.mat_missing:                    
                            ma_temp  = float(volttron_data[self.mat_name])
                            oa_temp  = float(volttron_data[ self.oat_name]) - oa_bias
                            ra_temp  = float(volttron_data[self.rat_name])
                            potential_cooling_savings = 1.08 * self.cfm * (avg_fanspeed/100) * ((0.05 * oa_temp + 0.95 * ra_temp) - ma_temp)
                            potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                        print 'fault kWh impact: ', potential_cooling_savings
                        self._log.debug("Excessive outdoor-air intake")
                        return 51.0, potential_cooling_savings
                    else:
                        self._log.debug("No fault detected during fault diagnostic")
                        return 50.0, 0.0
                return 50.0, 0.0
            
    #Insufficient outside-air ventilation diagnostic
    def afdd6(self):
        if self.mat_missing:
            mat_name = self.dat_name
        else:
            mat_name = self.mat_name
            
        volttron_data = self._agent.get_new_data()
        damper = float(volttron_data[self.damper_name])
        ma_temp = float(volttron_data[mat_name])
        oa_temp = float(volttron_data[self.oat_name])
        ra_temp  = float(volttron_data[self.rat_name])
        cool_call1 = int(volttron_data[self.coolcall1_name])
        cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            
        if not cool_call1: #economizer is off
        #OAF= [(ma_temp -ra_temp )/(oa_temp -ra_temp )]
            if damper >  self.afdd6_min_damper:
                self._log.debug('Damper should be at minimum, possible control fault')
                return 64.0 
            
            oaf = 0.0
            for n in xrange(self.minutes_to_average):
                cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                
                if cool_call1 or (self.mat_missing and cool_cmd1):
                    break
                
                ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki)
                ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                oa_temp = float(volttron_data[ self.oat_name])
                oaf += (ma_temp-ra_temp)/(oa_temp-ra_temp)
                if (n+1) < self.minutes_to_average:
                    volttron_data = self._agent.get_new_data()
                    
            if oaf < 0 or oaf > 1.25:
                    self._log.debug("Unexpected value calculated for OAF")
                    return 66.0    
                   
            oaf = oaf/(n + 1)
            self._log.debug('OAF: ' + str(oaf))
            if(self.afdd6_min_oa-oaf > self.afdd6_oaf_threshold):
                self._log.debug("Insufficient outdoor air intake")
                return 61.0
            else:
                self._log.debug("No fault detected during fault diagnostic")
                return 60.0
        elif (cool_call1 and ((oa_temp - self.afdd6_econ_differential) > ra_temp and 
              (oa_temp - self.afdd6_econ_differential) > self.high_limit and self.economizertype == 0) or
              ((oa_temp - self.afdd6_econ_differential) > self.high_limit and self.economizertype == 1)): #economizer should be off
            if damper >  self.afdd6_min_damper:
                self._log.debug('Damper should be at minimum, possible control fault')
                return 64.0
            
            if (self.mat_missing and not cool_cmd1) or not self.mat_missing:
                oaf = 0.0
                for n in xrange(self.minutes_to_average):
                    cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                    
                    if self.mat_missing and cool_cmd1:
                        break
                    
                    ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki)
                    ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                    oa_temp = float(volttron_data[ self.oat_name])
                    oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                    if (n+1) < self.minutes_to_average:
                        volttron_data = self._agent.get_new_data()
                        
                if oaf < 0 or oaf > 1.25:
                    self._log.debug("Unexpected value calculated for OAF")
                    return 66.0    
                    
                oaf = oaf/(n + 1)
                if(self.afdd6_min_oa-oaf> self.afdd6_oaf_threshold):
                    self._log.debug("Insufficient outdoor air intake")
                    return 61.0
                else:
                    self._log.debug("No fault detected during fault diagnostic")
                    return 60.0
            else:
                return 60.0
            
            return 60.0
        
        else:
            oa_bias = max(ra_temp - (oa_temp - self.afdd6_econ_differential *5.0), self.high_limit - oa_temp + self.afdd6_econ_differential * 5.0)
            status = self.command_outdoor_air_temperature_bias(oa_bias)
            if not (status):
                self._log.debug("Unsuccessful in setting OAT bias")    
                return 63.0
        
            self._agent.sleep(self.seconds_to_steady_state)
            volttron_data = self._agent.get_new_data()
            damper = float(volttron_data[self.damper_name])
            cool_cmd1 = int(volttron_data[self.coolcmd1_name])
            
            if damper >  self.afdd6_min_damper:
                self._log.debug("Damper did not close to minimum, possible control fault")
                return 64.0
         
            #OAF= [(ma_temp -ra_temp )/(oa_temp -ra_temp )]
            if (self.mat_missing and not cool_cmd1) or not self.mat_missing:
                oaf = 0.0
                for n in xrange(self.minutes_to_average):
                    cool_cmd1 = int(volttron_data[self.coolcmd1_name])
                    
                    if self.mat_missing and cool_cmd1:
                        break
                    
                    ma_temp = float(volttron_data[mat_name]) # Point name follows RTUNetwork wiki)
                    ra_temp = float(volttron_data[self.rat_name]) # Point name follows RTUNetwork wiki)
                    oa_temp = float(volttron_data[ self.oat_name]) - oa_bias
                    oaf +=(ma_temp-ra_temp)/(oa_temp-ra_temp)
                    if (n + 1) < self.minutes_to_average:
                        volttron_data = self._agent.get_new_data()
                        
                if oaf < 0 or oaf > 1.25:
                    self._log.debug("Unexpected value calculated for OAF")
                    return 66.0
                 
                oaf = oaf/(n + 1)
                
                if(self.afdd6_min_oa - oaf > self.afdd6_oaf_threshold):
                    self._log.debug("Insufficient outdoor-air intake")
                    return 61.0
                else:
                    self._log.debug("No fault detected during fault diagnostic")
                    return 60.0
            return 60.0


