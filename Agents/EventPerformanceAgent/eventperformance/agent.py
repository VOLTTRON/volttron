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

class EventPerformanceAgent(PublishMixin, BaseAgent):
    '''listens for and fulfills requests for generated event performance statistics'''

    def __init__(self, config_path, **kwargs):
        super(EventPerformanceAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

    def setup(self):
        self._agent_id = self.config['agentid']
        super(EventPerformanceAgent, self).setup()
    
    @matching.match_exact('eventperformance/request')
    def on_request(self, topic, headers, message, match):
        '''process request for event performance'''
        
        message = json.loads(message[0])
        _log.debug("Received event performance request. message: %s" % message)
 
        requester = headers['requesterID']
        response_topic = "eventperformance/responses/%s" % requester
        response = self.process_request(message)
        
        self.publish_json(response_topic, headers, response)

    # ------------------------------------------------------- #
    # example event performance request:
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
    #        "start_at": "09-27-2013 00:00:00",
    #        "end_at": "09-28-2013 00:00:00"
    #    }
    #    
    #    self.publish_json('eventperformance/request', headers, example_message)
    # ------------------------------------------------------- #

    def process_request(self, arg_set):        
        inst_args = ["load_data", "temp_data", "timezone", "temp_units", "sq_ft"]
        inst_args = { a_name: arg_set[a_name] for a_name in inst_args if arg_set.get(a_name)}
        
        event_args = ["start_at", "end_at"]
        event_args = { a_name: arg_set[a_name] for a_name in event_args if arg_set.get(a_name)}
        
        ls = Loadshape(**inst_args)
        event_performance_data = ls.event_performance(**event_args)
        
        return event_performance_data

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(EventPerformanceAgent,
                        description='Baseline agent for VOLTTRON platform',
                        argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
