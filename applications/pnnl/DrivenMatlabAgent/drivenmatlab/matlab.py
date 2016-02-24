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
from airside.diagnostics.satemp_rcx import SupplyTempRcx
from airside.diagnostics.stcpr_rcx import DuctStaticRcx
from airside.diagnostics.reset_sched_rcx import SchedResetRcx


class Application(AbstractDrivenAgent):
    
    def __init__(self, **kwargs):
        
        config_url = kwargs.pop('config_url')
        data_url = kwargs.pop('data_url')
        self.recv_timeout = kwargs.pop('recv_timeout')
        
        context = zmq.Context()
        
        self.config_socket = context.socket(zmq.PAIR)
        self.config_socket.connect(config_url)
        
        self.data_socket = context.socket(zmq.PAIR)
        self.data_socket.connect(data_url)
        
        self.config_params = kwargs
        
        print "Checking for config request from Matlab"
        event = config_socket.poll(self.recv_timeout)
        if event > 0 and config_socket.recv_string() == "config":
            try:
                print("Sending config_params")
                config_socket.send_json(self.config_params,zmq.NOBLOCK)
                
                print("Sending data")
                #TODO: Correct json format
                data = {"current_time": cur_time,
                        "points": points}
                data_socket.send_json(data,zmq.NOBLOCK)
            
            except ZMQError:
                print("No Matlab process running to send message. Exiting.")
                
            print("Waiting for matlab results")        
            event = data_socket.poll(recv_timeout)
            if event > 0:
                matlab_result = data_socket.recv_json()
                result = Results()
                if 'commands' in matlab_result:
                    commands = matlab_result['commands']
                    for point, value in commands:
                        result.command(point, value);
                        
                if 'logs' in matlab_result:
                    logs = matlab_result['logs']
                    for message in logs:
                        result.log(message);
                        
                if 'table_data' in matlab_result:
                    table_data = matlab_result['table_data']
                    for table in table_data:
                        rows = table_data[table]
                        for row in rows:
                            print(row)
                            result.insert_table_row(table, row)  
                
                #print(result.commands)
                #print(result.log_messages)
                #print(result.table_output)
                
                return matlab_result
                        
        else:
            print('Config request not received. Exiting.')

    def run(self, cur_time, points):
        
        try: 
            print("Sending data")
            #TODO: Correct json format
            data = {"current_time": cur_time,
                    "points": points}
            data_socket.send_json(data,zmq.NOBLOCK)
            
        except ZMQError:
            print("No Matlab process running to send message. Exiting.")
                
        print("Waiting for matlab results")        
        event = data_socket.poll(recv_timeout)
        if event > 0:
            matlab_result = data_socket.recv_json()
            result = Results()
            if 'commands' in matlab_result:
                commands = matlab_result['commands']
                for point, value in commands:
                    result.command(point, value);
                    
            if 'logs' in matlab_result:
                logs = matlab_result['logs']
                for message in logs:
                    result.log(message);
                    
            if 'table_data' in matlab_result:
                table_data = matlab_result['table_data']
                for table in table_data:
                    rows = table_data[table]
                    for row in rows:
                        print(row)
                        result.insert_table_row(table, row)  
            
            #print(result.commands)
            #print(result.log_messages)
            #print(result.table_output)
            
            return matlab_result
