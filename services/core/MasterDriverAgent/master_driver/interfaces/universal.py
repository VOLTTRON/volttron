'''
Copyright (c) 2016, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an agency of the
United States Government.  Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any 
jurisdiction or organization that has cooperated in the development of these 
materials, makes any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or any information, 
apparatus, product, software, or process disclosed, or represents that its use
would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by trade 
name, trademark, manufacturer, or otherwise does not necessarily constitute or
imply its endorsement, recommendation, or favoring by the United States Government
or any agency thereof, or Battelle Memorial Institute. The views and opinions of
authors expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830

-------------------------------------------------------------------------------
    History
-------------------------------------------------------------------------------
'''
__author1__   = 'Carl Miller <carl.miller@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__   = 'FreeBSD'
__version__   = '0.0.5'

import random
from volttron.platform.agent import utils
from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from csv import DictReader
from StringIO import StringIO
import gevent
import logging
import sys

# set DRIVER_PATH to path to your specific driver agent
#DRIVER_PATH = "/home/volttron/volttron/examples/GridAgentDrivers"
DRIVER_PATH = "/home/volttron/GridAgents/VolttronAgents/Drivers"
sys.path.insert( 0, DRIVER_PATH )
from heaters.agent  import HeaterDriver
from meters.agent   import MeterDriver
from hvac.agent     import ThermostatDriver
#from vehicles.agent import VehicleDriver

_log = logging.getLogger(__name__)

# UDI - Universal Driver Interface
class Interface(BasicRevert, BaseInterface):
    # 
    #  __init__
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.agent = None

    # config_dict: 'filename'.config, specified in the 'master-driver.agent' file.
    # registry_config_str: points csv file
    def configure(self, config_dict, registry_config_str):
        try:
            device_type = config_dict['device_type']
        
            if(device_type     == "heater" ):
                #self.agent = HeaterDriver(DRIVER_PATH+"/heaters/heater.cfg", config_dict['device_id'] )
                self.agent = HeaterDriver(None, config_dict['device_id'] )
            elif( device_type  == "meter" ):
                self.agent = MeterDriver( None, config_dict['device_id'] )
            elif( device_type  == "thermostat" ):
                self.agent = ThermostatDriver( None, config_dict['device_id'] )
            elif( device_type  == "vehicle" ):
                self.agent = VehicleDriver( DRIVER_PATH+"/vehicles/vehicles.ini", \
                                               config_dict['device_id'], config_dict['unit_num'] )                             
            else:
                _log.fatal("Unsupported Device Type: '{}'".format(self.device_type))
                sys.exit(-1)
                
            self.parse_config(self.agent, device_type, config_dict, registry_config_str)
            
            event = gevent.event.Event()
            gevent.spawn(self.agent.core.run, event)
            event.wait(timeout=5)
            
        except KeyError as e:
            _log.fatal("configure Failed accessing Key({}) in configuration file: {}".format(e,config_dict))
            sys.exit(1)
        
        except Exception as e:
            _log.fatal("configure Failed({}) using configuration file: {}".format(e,config_dict))
            sys.exit(1)
    #  get_point
    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        self.agent.GetPoint( register )
 
        return register._value
    
    #  _set_point
    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError("Trying to write to a point configured read only: " + point_name)

        if( self.agent.SetPoint( register, value ) ):
            register._value = register.reg_type(value)
            self.point_map[point_name]._value = register._value

        return register._value

    # this gets called periodically via DriverAgent::periodic_read()
    #    ( on behalf of MasterDriverAgent )
    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            _log.debug( "Scraping Value for '{}': {}".format(register.point_name, register._value))
            result[register.point_name] = register._value

        return result
    
    # 
    #  parse_config
    def parse_config(self, agent, device_type, config_dict, reg_config_str):
        if reg_config_str is None:
            return

        config_str = (utils.strip_comments(reg_config_str).lstrip()).rstrip()
        _log.debug('Configuring {} Driver with {} and config_str {}'.format(device_type, config_dict, config_str))
         
        f = StringIO(config_str)
        regDict = DictReader(f)
        
        agent.ConfigureAgent(self, config_dict, regDict )
