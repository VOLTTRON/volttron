import sys
import logging
from datetime import timedelta as td, datetime as dt
from dateutil import parser

from collections import deque

from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.agent.utils import jsonapi, setup_logging
from volttron.platform.vip.agent import Agent, Core
import gevent
DATE_FORMAT = '%m-%d-%y %H:%M:%S'
__version__ = "2.0.0"

def test_deploy(config_path, **kwargs):

    config = utils.load_config(config_path)
    device_list = config.get('device_list')
    point_dict = config.get('point_list')
    agent_id = 'device_set_test'
    revert = config.get('revert')

    class tester(Agent):
        def __init__(self, **kwargs):
            super(tester, self).__init__(**kwargs)
            self.device_values = {}
            
        @Core.receiver('onstart')
        def testing(self, sender, **kwargs):
            print 'running test now'
            # for device in device_list:
                # for point in point_list:
                    # point_topic = device + '/' + point
                    # result = self.vip.rpc.call(
                            # 'platform.actuator', 'get_point', point_topic).get(timeout=4)
                            
                    # self.device_values[point_topic] = result
        
            _now = dt.now()
            str_now = _now.strftime(DATE_FORMAT)
            end = _now + td(minutes=1)
            str_end = end.strftime(DATE_FORMAT)
            schedule_request = []
            for device in device_list:
                schedule_request.append([device, str_now, str_end])
            result = self.vip.rpc.call(
                     'platform.actuator', 'request_new_schedule', agent_id,
                     'my_test', 'HIGH', schedule_request).get(timeout=4)
                        
            for device in device_list:
                for point, value in point_dict.items():
                    point_topic = device + '/' + point
                    
#                    val = value[0]
                    result = self.vip.rpc.call('platform.actuator', 'set_point', agent_id, point_topic, value).get(timeout=4)
                            
            return        
            if revert:          
                gevent.sleep(60)
                
                for device in device_list:
                    for point, value in point_dict.items():
                        point_topic = device + '/' + point
                        result = self.vip.rpc.call(
                                'platform.actuator', 'set_point', agent_id,
                                point_topic, value[1]).get(timeout=4)
                                
            result = self.vip.rpc.call(
                        'platform.actuator', 'request_cancel_schedule', agent_id,
                        'test').get(timeout=4)
                            
    return tester(**kwargs)


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(test_deploy)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
