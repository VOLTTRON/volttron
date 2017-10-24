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
		03/30/16 - Initial.
		08/15/16 - Remove whitespace in config file.
		10/11/16 - Pass only device_id to VehicleDriver.
		03/01/17 - Call agent.GetPoint in get_point.
		04/17/17 - Updated for Volttron 4.0.
		10/01/17 - Updated for Volttron 5.0.
-------------------------------------------------------------------------------
'''
__author1__   = 'Carl Miller <carl.miller@pnnl.gov>'
__copyright__ = 'Copyright (c) 2017, Battelle Memorial Institute'
__license__   = 'FreeBSD'
__version__   = '0.3.0'

import random
from volttron.platform.agent import utils
try:
	from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
except:
	from services.core.MasterDriverAgent.master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert

from csv import DictReader
from StringIO import StringIO
import gevent
import logging
import sys
import os

# set DRIVER_PATH to path to your specific driver agent
DRIVER_PATH = "/home/volttron/GridAgents/VolttronAgents/Drivers"
sys.path.insert( 0, DRIVER_PATH )

_log = logging.getLogger(__name__)

# UDI - Universal Driver Interface
class Interface(BasicRevert, BaseInterface):
	def __init__(self, **kwargs):
		super(Interface, self).__init__(**kwargs)
		self.agent = None
		import argparse
		parser = argparse.ArgumentParser()
		parser.add_argument('-v', '--verbose', action='count' , dest="verbosity", default=0)		
		args = parser.parse_args()
		self._verboseness = args.verbosity

		if( self._verboseness == 0 ):
			verbiage = logging.ERROR 
		if( self._verboseness == 1 ):
			verbiage = logging.WARNING  # '-v'
		elif( self._verboseness == 2 ):
			verbiage = logging.INFO	 # '-vv'
		elif( self._verboseness >= 3 ): 
			verbiage = logging.DEBUG	# '-vvv'
		_log.setLevel(verbiage)

	def configure(self, config_dict, registry_config_dict): # 4.0 passes in a reg DICT not string now
		try:
			device_type = config_dict['device_type']
			if(device_type	 == "heater" ):
				from heaters.agent import HeaterDriver
				self.agent = HeaterDriver(None, config_dict['device_id'] )
			elif( device_type  == "meter" ):
				from meters.agent import MeterDriver
				self.agent = MeterDriver( None, config_dict['device_id'], )
			elif( device_type  == "vehicle" ):
				from vehicles.agent import VehicleDriver
				self.agent = VehicleDriver( None, config_dict['device_id'] )							 
			elif( device_type  == "thermostat" ):
				from hvac.agent import ThermostatDriver
				self.agent = ThermostatDriver( None, config_dict['device_id'] )
			elif( device_type  == "blinds" ):
				from blinds.agent import BlindsDriver
				self.agent = BlindsDriver( None, config_dict['device_id'] )
			else:
				raise RuntimeError("Unsupported Device Type: '{}'".format(device_type))

			self.parse_config(self.agent, device_type, config_dict, registry_config_dict)

			event = gevent.event.Event()
			gevent.spawn(self.agent.core.run, event)
			event.wait(timeout=5)

		except KeyError as e:
			_log.fatal("configure Failed accessing Key({}) in configuration file: {}".format(e,config_dict))
			raise SystemExit

		except RuntimeError as e:
			_log.fatal("configure Failed using configuration file: {}".format(config_dict))
			raise SystemExit(e)

		except Exception as e:
			_log.fatal("configure Failed({}) using configuration file: {}".format(e,config_dict))
			raise SystemExit

	#  get_point
	def get_point(self, point_name):
		register = self.get_register_by_name(point_name)
		value = self.agent.GetPoint( register )
		return value

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
	#	( on behalf of MasterDriverAgent )
	def _scrape_all(self):
		result = {}
		read_registers = self.get_registers_by_type("byte", True)
		write_registers = self.get_registers_by_type("byte", False)
		for register in read_registers + write_registers:
			if( self._verboseness == 2 ):
				_log.info( "Universal Scraping Value for '{}': {}".format(register.point_name, register._value))
			result[register.point_name] = register._value
		return result

	# this set each register to its default value (if it has one)
	def _reset_all(self):
		read_registers = self.get_registers_by_type("byte", True)
		write_registers = self.get_registers_by_type("byte", False)
		for register in read_registers + write_registers:
			old_value = register._value
			register._value = register._default_value			
			if( self._verboseness == 2 ):
				_log.info( "Hardware not reachable, Resetting Value for '{}' from {} to {}".format(register.point_name, old_value, register._value))

	'''
		parse_config
		***** NOTE:  you MUST install the csv file in --raw mode for universal drivers. *****
			volttron-ctl config store platform.driver registry_configs/meter.csv 
							../GridAgents/configs/registry_configs/meter.csv --raw
	'''
	def parse_config(self, agent, device_type, config_dict, reg_config_str):
		if reg_config_str is None:
			return

		config_str = (utils.strip_comments(reg_config_str).lstrip()).rstrip()

		import re
		# remove whitespace after delimiter,  but not within delimited value:
		config_str = re.sub(r',[\s]+', ',', config_str)

		# remove trailing whitespace within delimited value:
		config_str = re.sub(r'[\s]+,', ',', config_str)

		# remove trailing whitespace at end of line:
		# re.MULTILINE - When specified, '^' matches the beginning of the string andbeginning of each line (immediately following each newline)
		# and '$' matches end of the string and end of each line (immediately preceding each newline).
		config_str = re.sub(r'[\s]+$', '', config_str, flags=re.MULTILINE)

		_log.debug('Configuring {} Driver with {} and config_str {}'.format(device_type, config_dict, config_str))

		f = StringIO(config_str)
		regDict = DictReader(f)

		agent.ConfigureAgent(self, config_dict, regDict )
