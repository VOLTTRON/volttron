import logging
import sys

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod, topics
import json

utils.setup_logging()
_log = logging.getLogger(__name__)

REGISTER_TOPIC = "registration/register"
UNREGISTER_TOPIC = "registration/unregister"
LIST_REGISTRATIONS_TOPIC = "registration/list"
IS_REGISTERED_TOPIC = "registration/is_registered"

REGISTER_RESPONSE_TOPIC = REGISTER_TOPIC + "/response"
UNREGISTER_RESPONSE_TOPIC = UNREGISTER_TOPIC + "/response"
LIST_REGISTRATIONS_RESPONSE_TOPIC = LIST_REGISTRATIONS_TOPIC + "/response"
IS_REGISTERED_RESPONSE_TOPIC = IS_REGISTERED_TOPIC + "/response"


class RegistrationAgent(PublishMixin, BaseAgent):

    def __init__(self, config_path, **kwargs):
        super(RegistrationAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        
    def setup(self):
        self._agent_id = self.config['agentid']
        self.registered_agents = {}
        super(RegistrationAgent, self).setup()             
        
    def get_response_headers(self, headers):
        headers[headers_mod.TO] = headers[headers_mod.FROM] if headers_mod.FROM in headers else "Unknown"
        headers[headers_mod.FROM] = "registrationAgent"
        
        return headers           
    
    @matching.match_exact(REGISTER_TOPIC)
    def on_register_request(self, topic, headers, message, match):
       
        headers = self.get_response_headers(headers)
        message = json.loads(message[0])
        
        if "agents_to_register" not in message:
            msg = {"error" : "Missing agents_to_register field"}
        else:
            msg = {}
            for agent_id, registration_data in message["agents_to_register"].iteritems():
                if agent_id in self.registered_agents:
                    msg[agent_id] = "Is already registered."
                else:
                    try:
                        self.registered_agents[agent_id] = registration_data
                        msg[agent_id] = "Successfully registered."
                    except Exception as e:
                        msg[agent_id] = "Error registering: {e}".format(e = e)
        
        self.publish_json(REGISTER_RESPONSE_TOPIC, headers, msg)
            
            
            
    @matching.match_exact(UNREGISTER_TOPIC)
    def on_unregister_request(self, topic, headers, message, match):
        headers = self.get_response_headers(headers)
        message = json.loads(message[0])
        if "agents_to_unregister" not in message:
            msg = {"error" : "Missing agents_to_unregister field"}
        else:
            msg = {}
            for agent_id in message["agents_to_unregister"]:
                if agent_id not in self.registered_agents:
                    msg[agent_id] = "Is not registered."
                else:
                    try:
                        del self.registered_agents[agent_id]
                        msg[agent_id] = "Successfully unregistered."
                    except Exception as e:
                        msg[agent_id] = "Error unregistering: {e}".format(e = e)
        
        self.publish_json(UNREGISTER_RESPONSE_TOPIC, headers, msg)
            
    @matching.match_exact(LIST_REGISTRATIONS_TOPIC)
    def on_list_registered_request(self, topic, headers, message, match):        
        headers = self.get_response_headers(headers)                
        msg = self.registered_agents
        #self.publish_json(REGISTER_RESPONSE_TOPIC, headers, msg)
        self.publish_json(LIST_REGISTRATIONS_RESPONSE_TOPIC, headers, msg)
            
    @matching.match_exact(IS_REGISTERED_TOPIC)
    def on_is_registered_request(self, topic, headers, message, match):
        
        headers = self.get_response_headers(headers)
        message = json.loads(message[0])
        
        if "agents" not in message:
            msg = {"error" : "Missing agents field in message"}            
        else:
            msg = {}
            for agent in message["agents"]:            
                if agent in self.registered_agents:
                    msg[agent] = {"is_registered: " : True, "data" : self.registered_agents[agent]}
                else:
                    msg[agent] = {"is_registered" : False}
        
        self.publish_json(IS_REGISTERED_RESPONSE_TOPIC, headers, msg)
            
        
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(RegistrationAgent,
                        description='Registration agent for VOLTTRON Lite',
                        argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
