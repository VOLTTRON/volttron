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

from __future__ import absolute_import
import logging
import sys
import time
import json
from datetime import datetime
from volttron.platform.vip.agent import Agent, Core, PubSub, compat, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from . import settings
from . import CEA_2045
utils.setup_logging()
_log = logging.getLogger(__name__)

def cea_2045_agent(config_path, **kwargs):
    """
    CEA2045 standard relay agent

    Subscribes:
      For Control signals:
      TOPIC:  datalogger/log/esif/spl/set_CEA2045_1
      POINTS: cea2045state ['emergency','normal','shed'] enum
      For synchronization:
      TOPIC:  datalogger/log/volttime
      POINTS: timestamp [<%Y-%m-%d %H:%M:%S>] string
    Publishes:
      TOPIC:  datalogger/log/esif/spl/state_CEA2045_1
      POINTS: cea2045state ['Running Normal','Running Curtailed Grid',
      'Idle Grid','Idle Normal','SGD Error Condition',
      'Running Heightened Grid'] enum
              cea2045_rate [0,3] int
              timestamp [<volttime>] float
    """
    config = utils.load_config(config_path)
    vip_identity = config.get("vip_identity", "cea2045")
    kwargs.pop('identity', None)

    class CEA2045RelayAgent(Agent):
        '''
            CEA2045 class, serves as a relay sending control
            signals to the hardware
        '''

        def __init__(self, **kwargs):
            '''
                Initialize class from config file
            '''
            super(CEA2045RelayAgent, self).__init__(**kwargs)
            self.config = utils.load_config(config_path)
            self.volttime = None
            self.mode_CEA2045_array = ['emergency','shed','normal']
            # possible states of the appliance
            self.cea_rate = {
                    'Running Normal' : 2,
                    'Running Curtailed Grid' : 1,
                    'Idle Grid' : 0,
                    'Idle Normal': 0,
                    'SGD Error Condition':0,
                    'Running Heightened Grid':3
                    }
            self.device1_mode = {'cea2045state' : 'Idle Normal'}
            self.device2_mode = None
            self.task = 0
            # points of interest for demo
            self.point_name_map = {
                'cea2045state': 'cea2045state'
            }
            self.writable_points = {'cea2045state'}

        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            '''
                Setup the class and export RPC methods
            '''
            # Demonstrate accessing a value from the config file
            _log.info(self.config['message'])
            self._agent_id = self.config['agentid']
            self.vip.rpc.export(self.set_point)
            self.vip.rpc.export(self.get_point)
            device1_usb_port = self.config['device1_usb_port']
            device1_baud_rate = self.config['device1_baud_rate']
            self.device_type = self.config['device_type']
            if device1_usb_port == "None" or device1_baud_rate == 0:
                self.device1=CEA_2045.FakeSerial()
            else:
                self.device1=CEA_2045.CEA2045Interface(device1_usb_port,device1_baud_rate)


        @Core.receiver('onstart')
        def starting(self, sender, **kwargs):
            '''
                Initialize the CEA-2045 device
            '''
            self.device1.initialize(self.device_type)


        @PubSub.subscribe('pubsub', 'datalogger/log/esif/spl/set_CEA2045_1/cea2045state')
        def on_match_set(self, peer, sender, bus,  topic, headers, message):
            '''
                Subscribe to Control signals from Supervisory controller
            '''
            path,point_name = topic.rsplit('/',1)
            value = message['Readings']
            self.device1.send_msg(value)
            self.device1.recv_msg()
            self.device1.recv_msg()
            self.device1.send_msg('link_ack')
            time.sleep(1)
            self.device1.send_msg('query')
            self.device1.recv_msg()
            mode = self.device1.recv_msg()
            self.device1.send_msg('link_ack')
            print mode
            if mode != None:
                result_dict = {}
                result_dict={ point_name :CEA_2045.switch_query_response(mode['opcode2'])}
                self.device1_mode = result_dict


        @RPC.export
        def get_point(self,device,point_name):
            '''
                Subscribe to Control signals from Supervisory controller
            '''
            mode = ''
            if point_name == "cea2045state" :
                if device == "device1":
                    self.device1.send_msg('query')
                    self.device1.recv_msg()
                    mode = self.device1.recv_msg()
                    self.device1.send_msg('link_ack')
                    if mode != None:
                        result_dict = {}
                        result_dict={ point_name :CEA_2045.switch_query_response(mode['opcode2'])}
                        self.device1_mode = result_dict
                        return result_dict
                else:
                    _log.exception("Device not found")
            elif point_name == None:
                if device == "device1":
                    self.device1.send_msg('query')
                    self.device1.recv_msg()
                    mode = self.device1.recv_msg()
                    self.device1.send_msg('link_ack')
                    if mode != None:
                        result_dict = {}
                        result_dict={ point_name :CEA_2045.switch_query_response(mode['opcode2'])}
                        self.device1_mode = result_dict
                        return result_dict

            else:
                _log.exception("Point not found")

        @RPC.export
        def set_point(self,device,point_name,value):
            '''
                Set value of a point_name on a device
            '''
            if point_name == "cea2045state" :
                if device == "device1":
                    self.device1.send_msg(value)
                    self.device1.recv_msg()
                    mode = self.device1.recv_msg()
                    self.device1.send_msg('link_ack')
                    if mode != None:
                        result_dict = {}
                        result_dict={ point_name :CEA_2045.switch_query_response(mode['opcode2'])}
                        self.device1_mode = result_dict
                        return result_dict
                else:
                    _log.exception("Device not found")
            else:
                _log.exception("Point not found")

        @PubSub.subscribe('pubsub', 'datalogger/log/volttime')
        def on_match_all(self, peer, sender, bus,  topic, headers, message):
            '''
                Subscribe to volttime and synchronize
            '''
            str_time = message['timestamp']['Readings']
            timestamp=time.strptime(str_time,"%Y-%m-%d %H:%M:%S")
            self.volttime = message['timestamp']['Readings']
            if timestamp.tm_sec % 10 == 0 and timestamp.tm_min % 1 == 0:
                now = datetime.now().isoformat(' ') + 'Z'
                headers = {
                    'AgentID': self._agent_id,
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                    headers_mod.DATE: now,
                }
                pub_msg={}
                self.device1_mode = self.get_point('device1','cea2045state')
                temp_mode = str(self.device1_mode['cea2045state'])
                pub_msg['cea2045state']={'Readings':temp_mode,'Units':'state'}
                pub_msg['cea2045_rate']={'Readings':self.cea_rate[temp_mode],'Units':'level'}
                pub_msg['timestamp']={'Readings':str(self.volttime),'Units':'ts'}
                self.vip.pubsub.publish(
                    'pubsub', 'datalogger/log/esif/spl/state_CEA2045_1',headers, pub_msg)
                print pub_msg


        @Core.periodic(60)
        def keep_connection_alive(self):
            '''
                Send heartbeat to keep CEA-2045 link alive
            '''
            self.device1.send_msg('comm_status_good')
            self.device1.recv_msg()
            self.device1.recv_msg()
            self.device1.send_msg('link_ack')

    return CEA2045RelayAgent(identity=vip_identity, **kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(cea_2045_agent)
    except Exception as e:
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
