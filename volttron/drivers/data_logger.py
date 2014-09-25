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
import os
try:
    import simplejson as json
except ImportError:
    import json

from smap import driver
from smap.core import SmapException
from smap.util import periodicSequentialCall

from volttron.platform.messaging import headers as headers_mod, topics

import zmq


#Addresses agents use to setup the pub/sub
CAN_PUBLISH = False
CAN_SUBSCRIBE = False

publish_address = 'ipc://$VOLTTRON_HOME/run/no-publisher'
subscribe_address = 'ipc://$VOLTTRON_HOME/run/no-subscriber'
if 'AGENT_PUB_ADDR' in os.environ:
    publish_address = os.environ['AGENT_PUB_ADDR'] 
    CAN_PUBLISH = True
else:
    print("ERROR: NO PUBLISH ADDRESS IN ENVIRONMENT")
    CAN_PUBLISH = False
if 'AGENT_SUB_ADDR' in os.environ:
    subscribe_address = os.environ['AGENT_SUB_ADDR'] 
    CAN_SUBSCRIBE = True
else:
    print("ERROR: NO SUBSCRIBE ADDRESS IN ENVIRONMENT")
    CAN_SUBSCRIBE = False

logging_topic = 'datalogger/log'


class DataLogger(driver.SmapDriver):
    """docstring for DataLogger"""
    def setup(self, opts):
        self.known_timeseries = {}
        self.setup_subscriber()
        self.setup_publisher()

        # Subscribe to logging topic
        self.subscribe()
        
    

    def start(self):
        periodicSequentialCall(self.read).start(1)

    def read(self):
        while True:
            evt = self._poller.poll(0)
            #If evt is empty then we did not receive any messages, break
            if evt is None or evt == []:
                break
            else:
                #Examine the message we recieved
                message = self._sub.recv_multipart()

                # Parse the topic to get the location to store the data in
                path_elements = message[0][len(logging_topic):].split('/')[1:]
                headers = json.loads(message[1])
                sender = headers[headers_mod.FROM] if headers_mod.FROM in headers.keys() else ''
                data = message[2]

                # Parse out the data message
                try:
                    data = json.loads(data)

                except ValueError:
                    # data was not a valid JSON object.  Report error to requester
                    self._push.send_multipart(['datalogger/status', '{"' + headers_mod.TO + '" : "' + sender + '"}', "Message was not a valid JSON object."])
                    break

                # Parse out the SourceName
                source_name = headers['SourceName'] if 'SourceName' in headers.keys() else ''

                path = ""
                for path_element in path_elements:
                    if path == "":
                        path = path_element
                    else:
                        path = path + "/" + path_element
                    print 'Adding path:', path
                    if self.get_collection(path) is None:
                        self.add_collection(path)

                try:
                    # Create timeseries entries
                    for ts_string in data.keys():
                        if 'Readings' not in data[ts_string].keys() or 'Units' not in data[ts_string].keys():
                            self._push.send_multipart(['datalogger/status', '{"' + headers_mod.TO + '" : "'+sender+'"}', "Message missing required elements."])
                            break
                        ts_path = path + '/' + ts_string
                        ts = ""
                        if ts_path in self.known_timeseries.keys():
                            ts = self.known_timeseries[ts_path]
                        else:
                            units = data[ts_string]['Units']
                            dtype = 'double'
                            if 'data_type' in data[ts_string].keys():
                                dtype = data[ts_string]['data_type']
                            ts = self.add_timeseries(ts_path, units, data_type=dtype)
                            self.known_timeseries[ts_path] = ts

                        if type(data[ts_string]['Readings']) is list:
                            for item in data[ts_string]['Readings']:
                                ts.add(item[0], item[1])
                        else:
                            ts.add(data[ts_string]['Readings'])
                except SmapException as e:
                    self._push.send_multipart(['datalogger/status', '{"' + headers_mod.TO + '" : "'+sender+'"}', "Error loading data in smap\n%s"%e])
                    break
                except:
                    self._push.send_multipart(['datalogger/status', '{"to" : "'+sender+'"}', "Error loading data in smap"])
                    break

                self._push.send_multipart(['datalogger/status', '{"' + headers_mod.TO + '" : "'+sender+'"}', "Success"])

    def subscribe(self):
        self._sub.subscribe = logging_topic

    def setup_subscriber(self):
        #Subscribe to sub topic
        ctx = zmq.Context()
        self._sub = zmq.Socket(ctx, zmq.SUB)
        self._sub.connect(subscribe_address)

        #Setup a poller for use with the subscriber
        self._poller = zmq.Poller()
        self._poller.register(self._sub)

    def setup_publisher(self):
        #Connects to the broker's push topic
        #Broker will forward to the sub topic
        ctx = zmq.Context()
        self._push = zmq.Socket(ctx, zmq.PUSH)
        self._push.connect(publish_address)
