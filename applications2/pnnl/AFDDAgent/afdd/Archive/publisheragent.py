#!/usr/bin/env python

# 
# Copyright (c) 2015, Battelle Memorial Institute
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


import threading
import sys
import json
import time
import signal
import zmq
import time
#from xml.dom impmort minidom
import xml.etree.ElementTree as ET
import ast

from pkg_resources import resource_string
from datetime import datetime
from baseagent import BaseAgent
from simplejson.tests.test_pass1 import JSON

publish_address = 'ipc:///tmp/volttron-platform-agent-publish'
subscribe_address = 'ipc:///tmp/volttron-platform-agent-subscribe'

topic_delim = '/' # The delimiter between topics


def convert(input):
    if isinstance(input, dict):
        return {convert(key): convert(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [convert(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

class PublisherAgent(BaseAgent):
    """docstring for PublisherAgent"""
    def __init__(self, id, poll_time, source_file):
        super(PublisherAgent, self).__init__(poll_time)
        self._id = id
        self._poll_time = poll_time
        self._src_file = source_file

        # Load configuration file
        config_json = resource_string(__name__, 'config.ini')
        self._config = json.loads(config_json)
        
        self._rtu_path = convert(self._config['rtu_path'])
        self._lock_id = self.__class__.__name__
        self._has_lock = False
        
        self._keep_alive = True
        self._rtu_status = {}
        
        self.publish_to_topics()

    def publish_to_topics(self):
        f = open(self._src_file)
        header_line = f.readline().strip()
        headers = header_line.split(',')
        published_data = {}
        while (self._keep_alive):
            time.sleep(self._poll_time/1000) #sleep uses seconds
            now = time.time()
            line = f.readline()
            line = line.strip()
            data = line.split(',') 
            
            if (line):
                #Create 'all' message
                for i in xrange(0,len(headers)):
                    published_data[headers[i]] = data[i]
                published_all = json.dumps(published_data)
                #Pushing out the data
                print "publish %s %s" % ('RTU/'+ self._rtu_path + '/all',published_all)
                self.publish('RTU/'+ self._rtu_path + '/all', published_all) 
                #for i in xrange(0,len(headers)):
                    #print "publish %s %s" % ('RTU/'+ self._rtu_path + '/' + headers[i],data[i])
                    #self.publish('RTU/'+ self._rtu_path + '/' + headers[i], data[i])
            else:
                f.close()
                self.shutdown('RTU/'+ self._rtu_path, "shutdown due to out of data")

    def subscribe_to_topics(self):
        self.subscribe('RTU/' + self._rtu_path, self.consume_data)
    
    def consume_data(self, topic, messages):
        print topic, messages
        
    def post_loop(self):
        pass

    def shutdown(self,topic,message):
        super(PublisherAgent, self).shutdown(topic,message)

def main(argv = sys.argv):
    agent = PublisherAgent(id=0,poll_time=5000,source_file='data.csv')
    agent.start()


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass