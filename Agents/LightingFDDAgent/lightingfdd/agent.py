#Copyright (c) 2014, The Regents of the University of California, Department
#of Energy contract-operators of the Lawrence Berkeley National Laboratory.
#All rights reserved.
#
#1. Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met:
#
#    (1) Redistributions of source code must retain the copyright notice, this
#    list of conditions and the following disclaimer.
#
#    (2) Redistributions in binary form must reproduce the copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#    (3) Neither the name of the University of California, Lawrence Berkeley
#    National Laboratory, U.S. Dept. of Energy nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
#2. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
#THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#3. You are under no obligation whatsoever to provide any bug fixes, patches,
#or upgrades to the features, functionality or performance of the source code
#("Enhancements") to anyone; however, if you choose to make your Enhancements
#available either publicly, or directly to Lawrence Berkeley National
#Laboratory, without imposing a separate written license agreement for such
#Enhancements, then you hereby grant the following license: a non-exclusive,
#royalty-free perpetual license to install, use, modify, prepare derivative
#works, incorporate into other computer software, distribute, and sublicense
#such enhancements or derivative works thereof, in binary and source code
#form.
#
#NOTE: This license corresponds to the "revised BSD" or "3-clause BSD" license
#and includes the following modification:  Paragraph 3. has been added.

import logging
import sys
import json

from volttron.lite.agent import BaseAgent, PublishMixin, periodic
from volttron.lite.agent import utils, matching
from volttron.lite.messaging import headers as headers_mod
from volttron.lite.messaging import topics

from lighting_fdd import Lighting_FDD

utils.setup_logging()
_log = logging.getLogger(__name__)

class LightingFDDAgent(PublishMixin, BaseAgent):
    '''listens for and fulfills requests for lighting system diagnosis'''

    def __init__(self, config_path, **kwargs):
        super(LightingFDDAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        
    def setup(self):
        self._agent_id = self.config['agentid']
        super(LightingFDDAgent, self).setup()        
    
    @matching.match_exact('lighting_fdd/request')
    def on_request(self, topic, headers, message, match):
        print "on_request"
        '''process request for lighting diagnostics'''
        
        self.publish_received_request()
        
        message = json.loads(message[0])
        _log.debug("Received lighting diagnostic request. message: %s" % message)
 
        requester = headers['requesterID'] if 'requesterID' in headers else None 
        response_topic = "lighting_fdd/responses/%s" % requester
        
        headers[headers_mod.TO] = headers[headers_mod.FROM] if headers_mod.FROM in headers else "Unknown"
        headers[headers_mod.FROM] = "LightingFDDAgent"
        
        response = self.process_request(message)
        
        self.publish_json(response_topic, headers, response)        

    def process_request(self, arg_set):        
        from datetime import timedelta
        args = ["implemented_schedule","relay_timeseries","override_timeseries","intended_schedule","load_timeseries","expected_load_min_change","expected_load_max_change","relay_time_comparison_epsilon","override_timeout", "compress_overrides_to_change_of_state"]        
        args = { a_name: arg_set[a_name] for a_name in args if arg_set.get(a_name) and arg_set.get(a_name) != "None"}
        
        if "relay_time_comparison_epsilon" in args:
            args["relay_time_comparison_epsilon"] = timedelta(minutes= float(args["relay_time_comparison_epsilon"]))
            
        if "implemented_schedule" not in args:
            return {"error" : "Request is missing implemented_schedule."}
        
        if "relay_timeseries" not in args:
            return {"error" : "Request is missing relay_timeseries."}
        
        if "override_timeseries" not in args:
            return {"error" : "Request is missing override_timeseries."}
        
        lighting_diagnostics = Lighting_FDD(**args)
        faults_with_implemented_schedule, faults_with_intended_schedule, schedule_change_suggestions, override_timeout_suggested_changes = lighting_diagnostics.get_faults()
        
        response = {
            "faults_with_implemented_schedule": str([str(x) for x in faults_with_implemented_schedule]) if faults_with_implemented_schedule else None,
            "faults_with_intended_schedule" : str([str(x) for x in faults_with_intended_schedule]) if faults_with_intended_schedule else None,
            "suggested_schedule_changes" : str(schedule_change_suggestions),
            "suggested_override_timeout_changes" : str(override_timeout_suggested_changes)
        }
                
        return response
        
    def publish_received_request(self):
        from datetime import datetime
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
        }
        self.publish('received_request/lighting_diagnostic_agent', headers, now)        

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(LightingFDDAgent,
                        description='Lighting FDD Agent for VOLTTRON',
                        argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
