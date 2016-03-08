# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
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

#}}}
import csv
import datetime
import errno
import json
import logging
import os
import platform
import subprocess
import sys

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod, topics

date_format = "%s000.0"
readable_format = "%m/%d/%Y %H:%M:%S"
headers = {'time','host','process'}

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


def MobileExampleAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    config = utils.load_config(config_path)
    hosts = config['hosts']
    uuid = os.environ['AGENT_UUID']


    class Agent(PublishMixin, BaseAgent):
        '''This agent grabs a day's worth of data for a Catalyst's Data points
        out of the historian. It then sends the data on to an application
        in the cloud.
        '''
    
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
        
        def setup(self):
            self._command_to_execute = config.get('command_to_execute')
            self._results_csv = config.get('results_csv')
            # Always call the base class setup()
            super(Agent, self).setup()
            
            
            self.timer(2, self.exec_command)
            
        def exec_command(self):
            results = subprocess.check_output(self._command_to_execute.split(" "), shell=True)
            result_rows = results.split('\n')
            
            writeheaders = not os.path.isfile(self._results_csv)
            now = datetime.datetime.now()
            with open(self._results_csv,'a') as csvfile:
                dw = csv.DictWriter(csvfile, fieldnames = headers)
                if writeheaders: 
                    dw.writeheader()
                    
                hostname = platform.node()
                    
                for process in result_rows[1:]:
                    if (process != ''):
                        row = {'time':str(now),'host': hostname,'process': process}
                        dw.writerow(row)
            
            self.move()
            
        def move(self):
            count = 0
            try:
                file = open('count', 'r')
            except IOError as exc:
                if exc.errno != errno.ENOENT:
                    _log.error('error opening count file: %s', exc)
                    return
            else:
                try:
                    count = int(file.read().strip())
                except ValueError:
                    count = 0
                    
            if (count < len(hosts)):
                host = hosts[count]
                with open('count', 'w') as file:
                    file.write(str(count + 1))
                self.publish('platform/move/request/' + uuid, {}, host)  
            else: 
                _log.info("Agent done moving")
        
    Agent.__name__ = 'MobileExampleAgent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the platform.'''

    utils.default_main(MobileExampleAgent,
                   description='Mobile Example Agent',
                   argv=argv)


if __name__ == '__main__':
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
