
from __future__ import absolute_import
import logging
import sys
import json
import time
import ast
from datetime import datetime
from volttron.platform.vip.agent import Agent, Core, PubSub, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from . import  thermostat_api

utils.setup_logging()
_log = logging.getLogger(__name__)

def thermostat_agent(config_path, **kwargs):
    """
        Thermostat Relay Agent

        Subscribes:
          For Control signals:
          TOPIC:  datalogger/log/esif/spl/set_THERMOSTAT_1
          POINTS: tstat_cool_sp [60.9,90.0] float
                  tstat_mode [0,2] int
          For synchronization:
          TOPIC:  datalogger/log/volttime
          POINTS: timestamp [<%Y-%m-%d %H:%M:%S>] string
        Publishes:
          TOPIC:  datalogger/log/esif/spl/state_THERMOSTAT_1
          POINTS: tstat_cool_sp [60.9,90.0] float
                  tstat_mode [0,2] int,"Thermostat operating mode"
                  tstat_temp [60.0,90.0] float
                  timestamp [<volttime>] float
    """
    config = utils.load_config(config_path)
    vip_identity = config.get("vip_identity", "radiothermostat")
    #pop off the uuid based identity
    kwargs.pop('identity', None)

    class ThermostatRelayAgent(Agent):
        '''
            Thermostat class, serves as a relay sending control
            signals to the hardware
        '''

        def __init__(self, **kwargs):
            '''
                Initialize class from config file
            '''
            super(ThermostatRelayAgent, self).__init__(**kwargs)
            self.config = utils.load_config(config_path)
            self.volttime = None
            self.task = 0
            # points of interest for demo
            self.point_name_map = {
                    'tstat_mode' : "tmode",
                    'tstat_temp_sensor' : "temp",
                    'tstat_heat_sp' : 't_heat',
                    'tstat_cool_sp' : "t_cool",
                    'tstat_fan_mode' : 'fmode',
                    'tstat_hvac_state' : 'tstate'
            }
            self.units_map = {
                    'tstat_mode' : "state",
                    'tstat_temp_sensor' : "F",
                    'tstat_heat_sp' : 'F',
                    'tstat_cool_sp' : "F",
                    'tstat_fan_mode' : 'state',
                    'tstat_hvac_state' : 'state'
            }




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
            self.vip.rpc.export(self.ping_thermostat)
            url = self.config['url_address']
            #  Inistantiate Real or Virtual applicance based on info in config file
            if url == "Fake":
                self.thermostat = thermostat_api.FakeThermostat()
            else:
                self.thermostat = thermostat_api.ThermostatInterface(url)

        @RPC.export
        def get_point(self, device, point_map):
            '''
                Get value of a point_name on a device
            '''
            result = {}
            query = {}
            query = json.loads(self.thermostat.tstat())
            point_map_obj = {}
            for point_name, properties in point_map.iteritems():
                try:
                    b = query[self.point_name_map[point_name]]
                    result.update({point_name : str(b) })
                except:
                    result.update({point_name : str("NA") })
            return result

        @RPC.export
        def set_point(self, device, point_map, value):
            '''
                Set value of a point_name on a device
            '''
            for point_name, properties in point_map.iteritems():
                if point_name == "tstat_mode":
                    self.thermostat.mode(int(value))
                elif point_name == "tstat_cool_sp":
                    self.thermostat.t_cool(value)
                elif point_name == "tstat_heat_sp":
                    self.thermostat.t_heat(value)
                else:
                    _log.debug("No such writable point found")
            return ("success")

        @RPC.export
        def ping_thermostat(self,device):
            host = self.config['url_address']
            print "Ping Thermostat agent!"


        @PubSub.subscribe('pubsub', 'datalogger/log/esif/spl/set_THERMOSTAT_1')
        def match_ctl_set(self, peer, sender, bus, topic, headers, message):
            '''
                Subscribe to Control signals from Supervisory controller
            '''
            # print "subscribe to control signals"
            path,point_name = topic.rsplit('/',1)
            value = message['Readings']

                if point_name == "tstat_mode":
                    self.thermostat.mode(int(value))
                elif point_name == "tstat_cool_sp":
                    self.thermostat.t_cool(float(value))
                else:
                    _log.debug("No such writable point found")


        @PubSub.subscribe('pubsub', 'datalogger/log/volttime')
        def match_all(self, peer, sender, bus, topic, headers, message):
            '''
                Subscribe to volttime and synchronize
            '''
            self.task = self.task + 1
            str_time = message['timestamp']['Readings']
            timestamp = time.strptime(str_time, "%Y-%m-%d %H:%M:%S")
            self.volttime = message['timestamp']['Readings']
            if (timestamp.tm_sec % 5) == 0 and (timestamp.tm_min % 1) == 0:
                headers = {
                    'AgentID': self._agent_id,
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                    headers_mod.DATE: datetime.now().isoformat(' ') + 'Z',
                }
                query = {}
                query = self.thermostat.tstat()
                # print query
                msg = {}
                for pub_name, query_name in self.point_name_map.iteritems():
                    try:
                        msg.update({pub_name: {'Readings' : query[query_name], 'Units' : self.units_map[pub_name]}})
                        # print pub_name,query_name,msg
                    except:
                        msg.update({pub_name: {'Readings' : "NA", 'Units' : self.units_map[pub_name]}})
                self.vip.pubsub.publish(
                    'pubsub', 'datalogger/log/esif/spl/state_THERMOSTAT_1', headers, msg)
                # print msg

    return ThermostatRelayAgent(identity=vip_identity, **kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(thermostat_agent)
    except Exception as exception:
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
