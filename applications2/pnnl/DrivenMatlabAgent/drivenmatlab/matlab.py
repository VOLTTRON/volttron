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
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
import zmq
import time
import json
from zmq import ZMQError

class Application(AbstractDrivenAgent):
    
    def __init__(self, **kwargs):
        """
        Make connection with Matlab application via zmq. 
        Waits for config request from Matlab and sends back config
        parameters Matlab application. 
        :param kwargs: Any driver specific parameters"""
        
        self.log = logging.getLogger(__name__)
        config_url = kwargs.pop('config_url')
        data_url = kwargs.pop('data_url')
        self.recv_timeout = kwargs.pop('recv_timeout')
        
        context = zmq.Context()
        
        self.config_socket = context.socket(zmq.PAIR)
        self.config_socket.connect(config_url)
        
        self.data_socket = context.socket(zmq.PAIR)
        self.data_socket.connect(data_url)
        
        print "Checking for config request from Matlab"
        event = self.config_socket.poll(self.recv_timeout)
        if event > 0 and self.config_socket.recv_string() == "config":
            try:
                print("Sending config params")
                self.config_socket.send_json(kwargs,zmq.NOBLOCK)
                
            except :
                print("No Matlab process running to send message. Exiting.")
                
                                    
        else:
            print('Config request not received. Exiting.')

    def run(self, cur_time, points):
        """
        Sends device points to Matlab application and waits for response.
        Creates and returns Results object from received response from 
        Matlab application. 
        :param cur_time: timestamp
        :param points: device point name and value 
        :type cur_time: datetime.datetime
        :type points: dict
        :Returns Results object containing commands for devices, 
                    log messages and table data.
        :rtype results: Results object \\volttron.platform.agent.driven"""
        
        try: 
            self.data_socket.send_pyobj(points,zmq.NOBLOCK)
            
        except zmq.error.ZMQError:
            print("No Matlab process running to send message. Exiting.")
                
        print("Waiting for matlab results")        
        event = self.data_socket.poll(self.recv_timeout)
        if event > 0:
            matlab_result = self.data_socket.recv_json()
            matlab_result = eval(matlab_result)
            result = Results()
            if 'commands' in matlab_result:
                commands = matlab_result['commands']
                for device, point_value_dict in commands.items():
                    for point, value in point_value_dict:
                        result.command(point, value, device);
                    
            if 'logs' in matlab_result:
                logs = matlab_result['logs']
                for message in logs:
                    result.log(message);
                    
            if 'table_data' in matlab_result:
                table_data = matlab_result['table_data']
                for table in table_data:
                    rows = table_data[table]
                    for row in rows:
                        result.insert_table_row(table, row)  
            
            return result
