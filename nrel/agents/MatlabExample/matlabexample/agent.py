'''
Copyright (c) 2016, Alliance for Sustainable Energy, LLC
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted provided
that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this list of conditions
and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or
promote products derived from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''


'''
Matlab Example

An example that uses a matlab controller in VOLTTRON
for more information, refer to
http://www.mathworks.com/help/matlab/matlab-engine-for-python.html


'''

from __future__ import absolute_import

import matlab.engine
from datetime import datetime
import logging
import sys
from volttron.platform.vip.agent import Agent, Core, PubSub, compat, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

import numpy as np
from . import settings

# to use the Matlab API
import matlab.engine

utils.setup_logging()
_log = logging.getLogger(__name__)

class MatlabExampleAgent(Agent):
    ''' Simple example calling a Matlab function from VOLTTORN'''

    def __init__(self, config_path, **kwargs):
        super(MatlabExampleAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.eng = matlab.engine.start_matlab()

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']

    @Core.periodic(20)
    def run_matlab_controller(self):
            A_np = np.random.rand(3,3)
            A = matlab.double(A_np.tolist())
            B = self.eng.expm(A)
            print B

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(MatlabExampleAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        testing(sys.argv[1])

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
