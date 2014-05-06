# 
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. 
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies, 
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an 
# agency of the United States Government.  Neither the United States 
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization 
# that has cooperated in the development of these materials, makes 
# any warranty, express or implied, or assumes any legal liability 
# or responsibility for the accuracy, completeness, or usefulness or 
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or 
# service by trade name, trademark, manufacturer, or otherwise does 
# not necessarily constitute or imply its endorsement, recommendation, 
# r favoring by the United States Government or any agency thereof, 
# or Battelle Memorial Institute. The views and opinions of authors 
# expressed herein do not necessarily state or reflect those of the 
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#

# ****
# Note this driver is not in use until smap supports strings
# For now, consider it deprecated
# ****
#
try:
    import simplejson as json
except ImportError:
    import json
    
from smap import driver
from smap.util import periodicSequentialCall
from smap.contrib import dtutil

import os.path
import zmq

#Addresses agents use to setup the pub/sub
publish_address = 'ipc:///tmp/volttron-platform-agent-publish'
subscribe_address = 'ipc:///tmp/volttron-platform-agent-subscribe'

import logging

logging_levels = logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG

logging_string_map = {logging.getLevelName(level):level for level in logging_levels}

class Logger(driver.SmapDriver):    
    def setup(self, opts):
        self.setup_subscriber()
        self.interval = float(opts.get('interval',1))
        self.archiver_logging_level = logging_string_map.get(opts.get('level','INFO'))
        self.log_file = opts.get('file')
        
        if self.archiver_logging_level is None:
            raise ValueError('Invalid logging level')
        
        if not self.log_file is None: 
            logging.basicConfig(filename=self.log_file, level=logging.DEBUG)
        
        self.set_metadata('/', {'Extra/Driver' : 'volttron.drivers.logging.Logger',
                                'Instrument/SamplingPeriod' : str(self.interval)})
            
        for level in logging_levels:
            if level < self.archiver_logging_level:
                continue
            name = logging.getLevelName(level)
            print name
            self.add_timeseries('/' + name, 'Logs', data_type='string', description='Log Messages')
            
        self.setup_subscriber()
        self.setup_publisher()
        self.subscribe()
        
    def start(self):
        # Call read every minute seconds
        periodicSequentialCall(self.read).start(self.interval)
        
    def subscribe(self):
        for level in logging_string_map:
            topic = self.get_topic_for_logging('/') + '/' + level
            self._sub.subscribe = topic
            print "Subscribe to:", topic

    def read(self):
        while True:
            evt = self._poller.poll(0)
                #If evt is empty then we did not receive any messages, break
            if evt == None or evt == []:
                break
            else:
            #Examine the message we recieved
                message = self._sub.recv_multipart()
                print message
                
                if len(message) < 2:
                    self._push.send_multipart(['platform/loggererror', 'missing message'] + message)
                    continue
                
                tokens = message[0].split('/')
                log_level_string = tokens[-1].upper()
                
                log_level_value = logging_string_map.get(log_level_string)
                
                if log_level_value is None:
                    self._push.send_multipart(['platform/loggererror', 'invalid logging level'] + message)
                    continue
                
                log_message = '|'.join(message[1:])
#                 for level in logging_levels:
#                     if level < log_level_value:
#                         break
#                     self.add('/'+logging.getLevelName(level), log_message)
                  
                logging.log(log_level_value, log_message)
        
        
    def get_topic_for_logging(self, point):
        return 'LOG' + self._SmapDriver__join_id(point)
            
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
