# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

from datetime import datetime
import os
import sys

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green, utils, matching
from volttron.platform.agent.matching import match_all
from volttron.platform.agent.utils import ArgumentParser, load_config
from volttron.platform.messaging import topics
from volttron.platform.messaging import headers as headers_mod

MIME_PLAIN_TEXT = headers_mod.CONTENT_TYPE.PLAIN_TEXT
HEADER_NAME_DATE = headers_mod.DATE
HEADER_NAME_CONTENT_TYPE = headers_mod.CONTENT_TYPE

import json    
import settings


class PublisherAgent2(PublishMixin, BaseAgent):
    """docstring for PublisherAgent2"""
    def __init__(self, config_path, **kwargs):
        super(PublisherAgent2, self).__init__(**kwargs)
        self._config = load_config(config_path)
        
        self._src_file_handle = open(settings.source_file)
        header_line = self._src_file_handle.readline().strip()
        self._headers = header_line.split(',')
    
    def setup(self):
        # Demonstrate accessing a value from the config file
        print self._config['message']
        self._agent_id = self._config['agentid']
        self._rtu_path = settings.rtu_path
        # Always call the base class setup()
        super(PublisherAgent2, self).setup()
        
    # Demonstrate periodic decorator and settings access
    
    @match_all
    def on_match(self, topic, headers, message, match):
        '''Use match_all to receive all messages and print them out.'''
        #print "Topic: {topic}, Headers: {headers}, Message: {message}".format(topic=topic, headers=headers, message=message)

    @periodic(settings.check_4_new_data_time)    
    def publish_data_or_heartbeat(self):
        published_data = {}
        now = datetime.utcnow().isoformat(' ') + 'Z'
        if not self._src_file_handle.closed:
            line = self._src_file_handle.readline()
            line = line.strip()
            data = line.split(',')
            if (line):
                #Create 'all' message
                for i in xrange(0,len(self._headers)):
                    published_data[self._headers[i]] = data[i]
                all_data = json.dumps(published_data)
                #Pushing out the data
                self.publish(self._rtu_path + '/all', {'AgentID': self._agent_id,
                                                             HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                                                             HEADER_NAME_DATE: now}, all_data) 
            else:
                self._src_file_handle.close()
        else: #file is closed -> publish heartbeat
            self.publish('heartbeat/publisheragent2', {
                         'AgentID': self._agent_id,
                         HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                         HEADER_NAME_DATE: now,
                     }, now)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    # Parse options
    parser = ArgumentParser(prog=os.path.basename(argv[0]), description='Example VOLTTRON platform agent')
    opts = parser.parse_args(argv[1:])
    agent = PublisherAgent2(subscribe_address=opts.sub,
              publish_address=opts.pub, config_path=opts.config)
    agent.run()


if __name__ == '__main__':
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
