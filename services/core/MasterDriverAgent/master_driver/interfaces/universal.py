#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830


import random

from volttron.platform.agent import utils
from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from csv import DictReader
from StringIO import StringIO
import gevent
import logging
import sys

# set DRIVER_PATH to path to your specific driver agent
#DRIVER_PATH = "/home/volttron/volttron/applications/pnnl/GridAgentDrivers"
DRIVER_PATH = "/home/volttron/GridAgents/VolttronAgents/Drivers"
sys.path.insert( 0, DRIVER_PATH )
from heaters.agent  import HeaterDriver
#from meters.agent   import MeterDriver
#from vehicles.agent import VehicleDriver

__author1__   = 'Carl Miller <carl.miller@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__   = 'FreeBSD'

_log = logging.getLogger(__name__)

# UDI - Universal Driver Interface
class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.device_type = None
        self.unit = None
        self.agent = None

    def configure(self, config_dict, registry_config_str):
       
        self.device_type = config_dict['device_type']
        
        if(self.device_type == "heater" ):
            self.agent = HeaterDriver(DRIVER_PATH+"/heaters/heater.cfg", config_dict['device_id'] )
        elif( self.device_type  == "meter" ):
            self.agent = MeterDriver( config_dict['device_id'] )
        elif( self.device_type  == "vehicle" ):
            self.agent = VehicleDriver( DRIVER_PATH+"/vehicles/vehicles.ini", \
                                        config_dict['device_id'], config_dict['unit_num'] )
        
        self.parse_config(self.agent, config_dict, registry_config_str)
        
        event = gevent.event.Event()
        gevent.spawn(self.agent.core.run, event)
        event.wait(timeout=5)
        
    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        self.agent.GetPoint( register )
 
        return register._value
    #def set_point(self, point_name, value):
    #    _log.debug('Setting point {}->{}'.format(point_name, value))
    #    self._set_point(point_name, value)
    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError("Trying to write to a point configured read only: " + point_name)
        if( self.agent.SetPoint( register, value ) ):
            register._value = register.reg_type(value)

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
    
    def parse_config(self, agent, config_dict, reg_config_str):
        if reg_config_str is None:
            return

        config_str = utils.strip_comments(reg_config_str).lstrip()
        _log.debug('Configure with {} and config_str {}'.format(config_dict, config_str))
         
        f = StringIO(config_str)
        regDict = DictReader(f)
        
        self.agent.ConfigureAgent(self, config_dict, regDict )
