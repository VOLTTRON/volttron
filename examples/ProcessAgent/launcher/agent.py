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
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


from datetime import datetime
import logging
import os
import signal
import subprocess
import sys
import time

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod

import settings


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ ='0.1'

class ProcessAgent(BaseAgent):
    def __init__(self, subscribe_address, process, **kwargs):
        BaseAgent.__init__(self, subscribe_address, **kwargs)
        self.process = process
    def setup(self):
        BaseAgent.setup(self)
    
    @periodic(1)
    def poll_process(self):
        if self.process.poll() is not None:
            self._sub.close()
            
    def finish(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            time.sleep(2)
        if self.process.poll() is None:
            self.process.terminate()
            time.sleep(2)
            
        if self.process.poll() is None:
            self.process.kill()
            time.sleep(2)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    p_process = None
    
    try:
        
        config_path = os.environ.get('AGENT_CONFIG')
        sub_path = os.environ.get('AGENT_SUB_ADDR') 
        config = utils.load_config(config_path)
        
        command = config['exec']
        
        p_process = subprocess.Popen(command.split())
        agent = ProcessAgent(sub_path, p_process)
        agent.run()
        
    except Exception as e:
        _log.exception('unhandled exception')
    
    finally:
        if p_process is None:
            return 1
        if p_process.poll() is None:
            p_process.send_signal(signal.SIGINT)
            time.sleep(2)
        if p_process.poll() is None:
            p_process.terminate()
            time.sleep(2)
            
        if p_process.poll() is None:
            p_process.kill()
            time.sleep(2)
            
        return p_process.poll()

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
