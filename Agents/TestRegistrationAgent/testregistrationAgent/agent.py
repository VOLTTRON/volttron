import logging
import sys

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod, topics

utils.setup_logging()
_log = logging.getLogger(__name__)


class TestRegistrationAgent(PublishMixin, BaseAgent):

    def __init__(self, config_path, **kwargs):
        super(TestRegistrationAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
    def setup(self):
        self._agent_id = self.config['agentid']
        super(TestRegistrationAgent, self).setup()   
        self.run_tests()
        
    def run_tests(self):
        _log.debug("Attempting to register devices")
        self.post_register_test()
        _log.debug("Attempting to list registered devices")
        self.post_list_registered_test()
        _log.debug("Attempting to unregister devices")
        self.post_unregister_test()     
        _log.debug("Attempting to list registered devices")
        self.post_list_registered_test()
        _log.debug("Attempting to see if individual devices are registered")
        self.post_is_registered_test()
            
    def post_register_test(self):        
        headers = {'requesterID' : self._agent_id, "From" : "RegistrationAgentTester"}
        msg = {"agents_to_register" : {"agent_1" : "agent_1 info", "agent_2" : "agent_2_info"} }        
        self.publish_json("registration/register", headers, msg)
            
    @matching.match_exact("registration/register/response")    
    def on_test_register_response(self, topic, headers, message, match):        
        try:                    
            print "Received registration response.\nMessage: {msg}".format(msg = message)
        except:
            print "FAILURE due to exception: %s" % sys.exc_info()[0]
            
    def post_unregister_test(self):        
        headers = {'requesterID' : self._agent_id, "From" : "RegistrationAgentTester"}
        msg = {"agents_to_unregister" : ["agent_1", "agent_3"]}        
        self.publish_json("registration/unregister", headers, msg)
            
    @matching.match_exact("registration/unregister/response")    
    def on_test_unregister_response(self, topic, headers, message, match):        
        try:                    
            print "Received unregistration response.\nMessage: {msg}".format(msg = message)
        except:
            print "FAILURE due to exception: %s" % sys.exc_info()[0]
            
    def post_list_registered_test(self):        
        headers = {'requesterID' : self._agent_id, "From" : "RegistrationAgentTester"}
        msg = {}        
        self.publish_json("registration/list", headers, msg)
            
    @matching.match_exact("registration/list/response")    
    def on_test_list_registered_response(self, topic, headers, message, match):        
        try:                    
            print "Received list_registered response.\nMessage: {msg}".format(msg = message)
        except:
            print "FAILURE due to exception: %s" % sys.exc_info()[0]
            
    def post_is_registered_test(self):        
        headers = {'requesterID' : self._agent_id, "From" : "RegistrationAgentTester"}
        msg = {"agents" : ["agent_1"]}                
        self.publish_json("registration/is_registered", headers, msg)
        msg = {"agents" : ["agent_2"]}
        self.publish_json("registration/is_registered", headers, msg)
        msg = {"agents" : ["agent_3"]}
        self.publish_json("registration/is_registered", headers, msg)
        msg = {"agents" : ["agent_1", "agent_2", "agent_3"]}
        self.publish_json("registration/is_registered", headers, msg)
        
            
    @matching.match_exact("registration/is_registered/response")    
    def on_test_is_registered_response(self, topic, headers, message, match):        
        try:                    
            print "Received is_registered response.\nMessage: {msg}".format(msg = message)
        except:
            print "FAILURE due to exception: %s" % sys.exc_info()[0]
            
        
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(TestRegistrationAgent,
                        description='Testing agent for Archiver Agent in VOLTTRON Lite',
                        argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
