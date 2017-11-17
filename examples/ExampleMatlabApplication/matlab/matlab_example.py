# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of the United States Government. Neither the
# United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any
# jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product, process, or service by trade name,
# trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions
# of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency
# thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY under
# Contract DE-AC05-76RL01830
# }}}

import zmq

config_url = "tcp://localhost:5556"
data_url = "tcp://localhost:5557"
recv_timeout = 10000

context = zmq.Context()

config_socket = context.socket(zmq.PAIR)
config_socket.connect(config_url)

data_socket = context.socket(zmq.PAIR)
data_socket.connect(data_url)

#Wait for config request for given seconds
print("Waiting for config request")
event = config_socket.poll(recv_timeout)
#If there request received send config parameters and values
if event > 0 and config_socket.recv_string() == "config":
    try:
        print("Sending config_params")
        config_params = {"zone_temperature_list": ["ZoneTemperature1", "ZoneTemperature2"],
                        "zone_setpoint_list": ["ZoneTemperatureSP1", "ZoneTemperatureSP2"]}
        config_socket.send_json(config_params,zmq.NOBLOCK)
        
        print("Sending data")
        data = {"zone_temperature_list": ["72.3", "78.5"]}
        data_socket.send_json(data,zmq.NOBLOCK)
        
    except ZMQError:
        print("No Matlab process running to send message")
        
    print("Waiting for matlab results")        
    #wait for message from matlab
    event = data_socket.poll(recv_timeout)
    if event > 0:
        msg = data_socket.recv_json()
        print("Received commands"+msg)
else:
    print('Config request not received. Exiting.')

        
config_socket.close();
data_socket.close();