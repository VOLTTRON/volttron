
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
        This Agent works in the driver framework of VOLTTRON-3.0

        vip_identity : 'radiothermostat'

        topic : 'esif/spl/THERMOSTAT_1'
        This is setup in the config file for the driver interface, which is
        part of the MasterDriverAgent

        The points on this applinace are also in the thermostat_dev.csv
        file, which is present in the MasterDriverAgent

        April 2016
        NREL

    """
    config = utils.load_config(config_path)
    vip_identity = config.get("vip_identity", "radiothermostat")
    kwargs.pop('identity', None)

    class ThermostatRelayAgent(Agent):
        '''
            Thermostat class, serves as a relay sending control
            signals to the hardware, and querying the appliance for
            the current status

        '''

        def __init__(self, **kwargs):
            '''
                Initialize class from config file
            '''
            super(ThermostatRelayAgent, self).__init__(**kwargs)
            self.config = utils.load_config(config_path)
            # translation from radiothermostat point_name to datamodel
            self.point_name_map = {
                    'tstat_mode' : "tmode",
                    'tstat_temp_sensor' : "temp",
                    'tstat_heat_sp' : 't_heat',
                    'tstat_cool_sp' : "t_cool",
                    'tstat_fan_mode' : 'fmode',
                    'tstat_hvac_state' : 'tstate'
            }
            # point name present in a default query to the thermostat
            self.query_point_name = {
                    'tstat_mode',
                    'tstat_temp_sensor',
                    'tstat_heat_sp',
                    'tstat_cool_sp',
                    'tstat_fan_mode',
                    'tstat_hvac_state',
                    'override',
                    'hold'
            }
            # list of program modes/names
            self.program_name = {
                'heat_pgm_week',
                'heat_pgm_mon',
                'heat_pgm_tue',
                'heat_pgm_wed',
                'heat_pgm_thu',
                'heat_pgm_fri',
                'heat_pgm_sat',
                'heat_pgm_sun',
                'cool_pgm_week',
                'cool_pgm_mon',
                'cool_pgm_tue',
                'cool_pgm_wed',
                'cool_pgm_thu',
                'cool_pgm_fri',
                'cool_pgm_sat',
                'cool_pgm_sun'
            }


        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            '''
                Setup the class and export RPC methods
            '''
            _log.info(self.config['message'])
            self._agent_id = self.config['agentid']
            self.vip.rpc.export(self.set_point)
            self.vip.rpc.export(self.get_point)
            self.vip.rpc.export(self.ping_thermostat)
            url = self.config['url_address']
            self.thermostat = thermostat_api.ThermostatInterface(url)

        @RPC.export
        def get_point(self, device, point_map):
            '''
                Get value of a point_name on a device
            '''
            result = {}
            query = {}
            point_map_obj = {}
            for point_name, properties in point_map.iteritems():
                query = json.loads(self.thermostat.tstat())
                if point_name in self.query_point_name:
                    try:
                        db = query[self.point_name_map[point_name]]
                        result.update({point_name : str(db) })
                    except:
                        result.update({point_name : str("NA") })
                else:
                    pgm,day = point_name.rsplit('_',1)
                    if pgm == 'heat_pgm':
                        if day == 'week':
                            query = self.thermostat.get_heat_pgm()
                            result.update({point_name : str(query)})
                        else:
                            query = self.thermostat.get_heat_pgm(day)
                            result.update({point_name : str(query)})
                    elif pgm == 'cool_pgm':
                        if day == 'week':
                            query = self.thermostat.get_cool_pgm()
                            result.update({point_name : str(query)})
                        else:
                            query = self.thermostat.get_cool_pgm(day)
                            result.update({point_name : str(query)})
            return str(result)

        @RPC.export
        def set_point(self, device, point_map, value):
            '''
                Set value of a point_name on a device
            '''
            result = {}
            for point_name, properties in point_map.iteritems():

                if point_name in self.program_name:
                    pgm,day = point_name.rsplit('_',1)
                    if pgm == 'heat_pgm':
                        if(day == 'week'):
                            result = self.thermostat.set_heat_pgm(value)
                        else:
                            result = self.thermostat.set_heat_pgm(value, day)
                    elif pgm == 'cool_pgm':
                        if(day == 'week'):
                            result = self.thermostat.set_cool_pgm(value)
                        else:
                            result = self.thermostat.set_cool_pgm(value, day)
                elif point_name == "tstat_mode":
                    result = self.thermostat.mode(int(value))
                elif point_name == "tstat_cool_sp":
                    result = self.thermostat.t_cool(value)
                elif point_name == "tstat_heat_sp":
                    result = self.thermostat.t_heat(value)
                elif point_name == 'energy_led':
                    result = self.thermostat.energy_led(value)
                else:
                    _log.debug("No such writable point found")
            return (str(result))


        @RPC.export
        def ping_thermostat(self,device):
            host = self.config['url_address']
            print "Ping Thermostat agent!"


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
