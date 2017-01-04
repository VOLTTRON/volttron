import logging
import sys
import json

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics

from loadshape import Loadshape

utils.setup_logging()
_log = logging.getLogger(__name__)

class BaselineAgent(PublishMixin, BaseAgent):
    '''listens for and fulfills requests for generated baselines'''

    def __init__(self, config_path, **kwargs):
        super(BaselineAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

    def setup(self):
        self._agent_id = self.config['agentid']
        super(BaselineAgent, self).setup()
    
    @matching.match_exact('baseline/request')
    def on_request(self, topic, headers, message, match):
        '''process request for baseline'''
        
        message = json.loads(message[0])
        _log.debug("Received baseline request. message: %s" % message)
 
        requester = headers['requesterID']
        response_topic = "baseline/responses/%s" % requester
        response = self.process_request(message)
        
        self.publish_json(response_topic, headers, response)

    # ------------------------------------------------------- #
    # example baseline request:
    #    headers = {
    #        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
    #        'requesterID': 'requestingAgentID'
    #    }
    #    
    #    example_message = {
    #        "load_data": [(1379487600, 5), (1379488500, 5), ... (1379491200, 5)],
    #        "temp_data": [(1379487600, 72), (1379488500, 72), ... (1379491200, 72)],
    #        "timezone": 'America/Los_Angeles',
    #        "temp_units": "F",
    #        "sq_ft": 5600,
    #        "weighting_days": 14,
    #        "modeling_interval": 900,
    #        "step_size": 900
    #    }
    #    
    #    self.publish_json('baseline/request', headers, example_message)
    # ------------------------------------------------------- #

    def process_request(self, arg_set):        
        inst_args = ["load_data", "temp_data", "timezone", "temp_units", "sq_ft"]
        inst_args = { a_name: arg_set[a_name] for a_name in inst_args if arg_set.get(a_name)}
        
        baseline_args = ["start_at", "end_at", "weighting_days", "modeling_interval", "step_size"]
        baseline_args = { a_name: arg_set[a_name] for a_name in baseline_args if arg_set.get(a_name)}
        
        ls = Loadshape(**inst_args)
        baseline_series = ls.baseline(**baseline_args)
        
        response = {
            "baseline": baseline_series.data(),
            "error_stats": ls.error_stats
        }
        
        return response

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(BaselineAgent,
                        description='Baseline agent for VOLTTRON platform',
                        argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
