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

class CumulativeSumAgent(PublishMixin, BaseAgent):
    '''listens for and fulfills requests for generated cumulative sums'''

    def __init__(self, config_path, **kwargs):
        super(CumulativeSumAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

    def setup(self):
        self._agent_id = self.config['agentid']
        super(CumulativeSumAgent, self).setup()
    
    @matching.match_exact('cumulativesum/request')
    def on_request(self, topic, headers, message, match):
        '''process request for cumulative sums'''
        
        message = json.loads(message[0])
        _log.debug("Received cumulative sum request. message: %s" % message)
 
        requester = headers['requesterID']
        response_topic = "cumulativesum/responses/%s" % requester
        response = self.process_request(message)
        
        self.publish_json(response_topic, headers, response)

    # ------------------------------------------------------- #
    # example cumulative sum request:
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
    #        "step_size": 900
    #    }
    #    
    #    self.publish_json('cumulativesum/request', headers, example_message)
    # ------------------------------------------------------- #

    def process_request(self, arg_set):        
        inst_args = ["load_data", "temp_data", "timezone", "temp_units", "sq_ft"]
        inst_args = { a_name: arg_set[a_name] for a_name in inst_args if arg_set.get(a_name)}
        
        sum_args = ["start_at", "end_at", "step_size"]
        sum_args = { a_name: arg_set[a_name] for a_name in sum_args if arg_set.get(a_name)}
        
        ls = Loadshape(**inst_args)
        sum_series = ls.cumulative_sum(**sum_args)
        
        response = {
            "cumulative_kwh_diff": sum_series.data(),
        }
        
        return response

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(CumulativeSumAgent,
                        description='Cumulative sum agent for VOLTTRON platform',
                        argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
