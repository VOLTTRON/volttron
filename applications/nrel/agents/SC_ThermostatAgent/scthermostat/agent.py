"""
Example Control Agent

April 2016
NREL

"""

from __future__ import absolute_import
from datetime import datetime
import logging
import sys
import time
import random
import json
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from . import settings


utils.setup_logging()
_log = logging.getLogger(__name__)

class SCHouseAgent(Agent):
    '''
    Publishes example control signals to control the Thermostat Relay
    '''
    def __init__(self, config_path, **kwargs):
        ''' SCHouseAgent initialization function'''
        super(SCHouseAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        '''SCHouse setup function'''
        # Demonstrate accessing a value from the config file
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        self.cea_ctl = ['emergency','normal','shed']

    @Core.receiver('onstart')
    def begining(self, sender, **kwargs):
        '''on start'''
        start_time = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())
        timestamp=time.strptime(start_time,"%Y-%m-%d %H:%M:%S")
        end_time = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.mktime(timestamp) + 600))
        msgs = [
                    ["esif/spl/THERMOSTAT_1", #First time slot.
                     str(start_time),     #Start of time slot.
                     str(end_time)]   #End of time slot.
                ]
        print json.dumps(self.vip.rpc.call('platform.actuator','request_new_schedule','rpc_ctl',"007",'HIGH',msgs).get())

    @Core.receiver('onstop')
    def ending(self, sender, **kwargs):
        ''' at the end'''
        self.vip.rpc.call('platform.actuator','request_cancel_schedule','rpc_ctl',"007")

    @Core.periodic(settings.HEARTBEAT_PERIOD)
    def example_controls(self):
            ''' Function that sends example controls peridically '''

            input_led_point = random.randrange(0,2,1)
            input_setpoint = random.randrange(75,85,1)
            input_heat_pgm_week= {"0": [360, 90, 480, 90, 1080, 90, 1320, 90], "1": [360, 90, 480, 90, 1080, 90, 1320, 90], "2": [360, 70, 480, 70, 1080, 70, 1320, 70], "3": [360, 70, 480, 70, 1080, 70, 1320, 70], "4": [360, 70, 480, 70, 1080, 70, 1320, 70], "5": [360, 70, 480, 70, 1080, 70, 1320, 70], "6": [360, 70, 480, 70, 1080, 70, 1320, 70]}
            input_cool_pgm_week= {
                    "0": [360, 90, 480, 90, 1080, 90, 1320, 90],
                    "1": [360, 90, 480, 90, 1080, 90, 1320, 90],
                    "2": [360, 70, 480, 70, 1080, 70, 1320, 70],
                    "3": [360, 70, 480, 70, 1080, 70, 1320, 70],
                    "4": [360, 70, 480, 70, 1080, 70, 1320, 70],
                    "5": [360, 70, 480, 70, 1080, 70, 1320, 70],
                    "6": [360, 70, 480, 70, 1080, 70, 1320, 70]
                }
            input_cool_pgm_day= "360,90,480,90,1080,90,1320,90"
            input_heat_pgm_day= "360,90,480,90,1080,90,1320,90"
            input_tstat_mode = random.randrange(0,2,1)

            # Example control signals to get and set values, revert points to default states
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/energy_led",input_led_point).get()
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/heat_pgm_week",input_cool_pgm_week).get()
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/cool_pgm_week", input_cool_pgm_week).get()
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/heat_pgm_tue",input_cool_pgm_day).get()
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/cool_pgm_wed", input_cool_pgm_day).get()
            # print self.vip.rpc.call('platform.actuator','revert_point','rpc_ctl',"esif/spl/THERMOSTAT_1/cool_pgm_week").get()
            # print self.vip.rpc.call('platform.actuator','revert_point','rpc_ctl',"esif/spl/THERMOSTAT_1/heat_pgm_week").get()
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/tstat_heat_sp",input_setpoint).get()
            # print self.vip.rpc.call('platform.actuator','set_point','rpc_ctl',"esif/spl/THERMOSTAT_1/tstat_cool_sp",input_setpoint).get()
            # print self.vip.rpc.call('platform.actuator','get_point',"esif/spl/THERMOSTAT_1/tstat_temp_sensor").get()
            # print self.vip.rpc.call('platform.actuator','get_point',"esif/spl/THERMOSTAT_1/tstat_mode").get()
            # print self.vip.rpc.call('platform.actuator','revert_device','rpc_ctl',"esif/spl/THERMOSTAT_1").get()



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(SCHouseAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
