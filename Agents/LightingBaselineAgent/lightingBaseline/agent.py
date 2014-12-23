import logging
import sys
import json

from volttron.lite.agent import BaseAgent, PublishMixin
from volttron.lite.agent import utils, matching
from volttron.lite.messaging import headers as headers_mod
from volttron.lite.messaging import topics

utils.setup_logging()
_log = logging.getLogger(__name__)

class LightingBaselineAgent(PublishMixin, BaseAgent):
    '''listens for and fulfills requests for lighting load summary'''

    def __init__(self, config_path, **kwargs):
        super(LightingBaselineAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

    def setup(self):
        self._agent_id = self.config['agentid']
        super(LightingBaselineAgent, self).setup()
    
    @matching.match_exact('lighting_analysis/summary_request')
    def on_summary_request(self, topic, headers, message, match):
        '''process request for lighting summary'''
        
        message = json.loads(message[0])
        _log.debug("Received lighting summary request. message: %s" % message)
 
        requester = headers['requesterID']
        response_topic = "lighting_analysis/summary_response/%s" % requester
        response = self.process_summary_request(message)
        
        headers[headers_mod.TO] = headers[headers_mod.FROM] if headers_mod.FROM in headers else "Unknown"
        headers[headers_mod.FROM] = "lightingAnalysisAgent"
                           
        
        self.publish_json(response_topic, headers, response)

    # ------------------------------------------------------- #
    # example summary request:
    #    headers = {
    #        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
    #        'requesterID': 'requestingAgentID'
    #    }
    #    
    #    example_message = {
    #        "load_data": [(1379487600, 5), (1379488500, 5), ... (1379491200, 5)],    
    #        "timezone": 'America/Los_Angeles',
    #        "sq_ft": 5600,
    #        "workdays": '12345' 
    #    }
    #    
    #    self.publish_json('lightinganalysis/request', headers, example_message)
    # ------------------------------------------------------- #

    def process_summary_request(self, arg_set):        
        import lighting_baseline
        inst_args = ["load_data", "timezone",  "sq_ft", "workdays","workday_start" ]
        inst_args = { a_name: arg_set[a_name] for a_name in inst_args if arg_set.get(a_name)}
        
        summary_args = ["workdays", "workday_start"]
        summary_args = { a_name: arg_set[a_name] for a_name in summary_args if arg_set.get(a_name)}
        
        if "load_data" in inst_args:
            la = lighting_baseline.Lighting_Analysis(**inst_args)
        else:
            return {"error" : "Request is missing load data.  A request for lighting M&V summary must contain load_data."}
                
        summary = la.summary(**summary_args)
        
        response = {
            "summary_stats": summary
        }
        
        return response
    
    @matching.match_exact('lighting_analysis/comparison_request')
    def on_comparison_request(self, topic, headers, message, match):
        '''process request for lighting comparison'''
        
        message = json.loads(message[0])
        _log.debug("Received lighting comparison request. message: %s" % message)
 
        requester = headers['requesterID']
        response_topic = "lighting_analysis/comparison_responses/%s" % requester
        response = self.process_comparison_request(message)
        
        headers[headers_mod.TO] = headers[headers_mod.FROM] if headers_mod.FROM in headers else "Unknown"
        headers[headers_mod.FROM] = "lightingBaselineAgent"
                           
        
        self.publish_json(response_topic, headers, response)

    # ------------------------------------------------------- #
    # example comparison request:
    #    headers = {
    #        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
    #        'requesterID': 'requestingAgentID'
    #    }
    #    
    #    example_message = {
    #        "baseline_load_data": [(1379487600, 5), (1379488500, 5), ... (1379491200, 5)],
    #        "comparison_load_data": [(1379597600, 5), (1379589500, 5), ... (1379594200, 5)],
    #        "timezone": 'America/Los_Angeles',
    #        "sq_ft": 5600,
    #        "workdays": '12345' 
    #    }
    #    
    #    self.publish_json('lightinganalysis/request', headers, example_message)
    # ------------------------------------------------------- #

    def process_comparison_request(self, arg_set):        
        import lighting_baseline
        inst_args = ["baseline_load_data", "comparison_load_data", "timezone",  "sq_ft", "workdays","workday_start" ]
        inst_args = { a_name: arg_set[a_name] for a_name in inst_args if arg_set.get(a_name)}
        
        comparison_args = ["workdays", "workday_start"]
        comparison_args = { a_name: arg_set[a_name] for a_name in comparison_args if arg_set.get(a_name)}
        
        if "comparison_load_data" in inst_args and "baseline_load_data" in inst_args:
            la = lighting_baseline.Lighting_Compare(**inst_args)
        else:
            return {"error" : "Request is missing load data.  A request for lighting M&V comparison must contain both a baseline_load_data list and a comparison_load_data list"}
                
        comparison = la.change(**comparison_args)
        
        response = {
            "comparison_stats": comparison
        }
        
        return response

def main(argv=sys.argv):
    print "Starting lighting baseline agent main"
    '''Main method called by the eggsecutable.'''
    utils.default_main(LightingBaselineAgent,
                        description='Lighting baseline load analysis agent for VOLTTRON',
                        argv=argv)
    print "Finishing lighting baseline agent main"

if __name__ == '__main__':
    
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
