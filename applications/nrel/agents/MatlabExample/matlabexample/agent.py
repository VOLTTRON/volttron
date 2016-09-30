'''
-------------------------------------
National Renewable Energy Laboratory
-------------------------------------
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
