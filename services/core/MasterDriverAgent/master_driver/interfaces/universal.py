# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

'''

-------------------------------------------------------------------------------
	History
		03/30/16 - Initial.
		08/15/16 - Remove whitespace in config file.
		10/11/16 - Pass only device_id to VehicleDriver.
		03/01/17 - Call agent.GetPoint in get_point.
		04/17/17 - Updated for Volttron 4.0.
-------------------------------------------------------------------------------
'''
__author1__   = 'Carl Miller <carl.miller@pnnl.gov>'
__copyright__ = 'Copyright (c) 2019, Battelle Memorial Institute'
__license__   = 'Apache 2.0'
__version__   = '0.2.0'

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
from heaters.agent  import HeaterDriver
from meters.agent   import MeterDriver
from hvac.agent		import ThermostatDriver
from blinds.agent	import BlindsDriver
from vehicles.agent	import VehicleDriver

_log = logging.getLogger(__name__)

# UDI - Universal Driver Interface
class Interface(BasicRevert, BaseInterface):
	def __init__(self, **kwargs):
		super(Interface, self).__init__(**kwargs)
		# the following are new in bacnet 4.0 driver, do we need to do too?
		#self.register_count = 10000
		#self.register_count_divisor = 1
		
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
	'''
	 config_dict: 'filename'.config, specified in the 'master-driver.agent' file.
	 registry_config_str: points csv file
	 def configure(self, config_dict, registry_config_str):
	 when 4.0 master driver is started, class ConfigStore is instantiated:
	 	volttron/platform/vip/agent/subsystems/configstore.py which exports initial_update()
			which calls volttron/platform/store.py: def get_configs(self):
				self.vip.rpc.call(identity, "config.initial_update" sets list of registry_configs
				
	scripts/install_master_driver_configs.py calls 'manage_store' rpc, which is in volttron/platform/store.py
					which calls process_raw_config(), which stores it as a dict.
					process_raw_config() is also called by process_store() in store.py 
					when the platform starts ( class ConfigStoreService):
					    processing_raw_config 'registry_configs/meter.csv' (config_type: csv) 
	process_store() is called by _setup using a 'PersistentDict', i.e.:
		store_path '/home/carl/.volttron/configuration_store/platform.driver.store'

	install_master_driver_configs.py stores them as config_type="csv", it is useful for batch processing alot
	of files at once, like when upgrading from 3.5 to 4.0
	
	to add single config to store, activate and start platform then:
		List current configs:
			volttron-ctl config list platform.driver
				config
				devices/PNNL/LABHOME_B/METER1
				registry_configs/meter.csv
		Delete current configs:
			volttron-ctl config delete platform.driver registry_configs/meter.csv # note lack of prefix './GridAgents/configs/'
			volttron-ctl config delete platform.driver devices/PNNL/LABHOME_B/METER1
		To store the driver configuration run the command:
			delete any files from ../GridAgents/configs
			volttron-ctl config store platform.driver devices/PNNL/LABHOME_B ../GridAgents/configs/devices/PNNL/LABHOME_B/METER1
			
		To store the registry configuration run the command (note the **--raw option)
			volttron-ctl config store platform.driver registry_configs/meter.csv ../GridAgents/configs/registry_configs/meter.csv --raw
		
		***** NOTE:  you MUST install the csv file in --raw mode for universal drivers. *****

	'''

	def configure(self, config_dict, registry_config_dict): # 4.0 passes in a reg DICT not string now
		try:
			device_type = config_dict['device_type']
			''' see ./volttron/volttron/platform/vip/agent/__init__.py for Agent object definition
				every agent has a .core and .vip:
					vip.ping 
					vip.rpc
					vip.hello
					vip.pubsub
					vip.health
					vip.heartbeat
					vip.config
			'''
			if(device_type	 == "heater" ):
				self.agent = HeaterDriver(None, config_dict['device_id'] )
			elif( device_type  == "meter" ):
				self.agent = MeterDriver( None, config_dict['device_id'], )
			elif( device_type  == "thermostat" ):
				self.agent = ThermostatDriver( None, config_dict['device_id'] )
			elif( device_type  == "blinds" ):
				self.agent = BlindsDriver( None, config_dict['device_id'] )							 
			elif( device_type  == "vehicle" ):
				self.agent = VehicleDriver( None, config_dict['device_id'] )							 
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
		#if( self._verboseness == 2 ):
		#	_log.debug( "Universal get_point called for '{}', value: {}.".format(point_name, value))
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
			#_log.info( "point_map[register]._value = {}".format(self.point_map[register.point_name]._value))
			if( self._verboseness == 2 ):
				_log.info( "Hardware not reachable, Resetting Value for '{}' from {} to {}".format(register.point_name, old_value, register._value))

			'''
				We maybe could have used revert_point( register.point_name ), but that is more for reverting the hardware to its default
				value (calls set_point, which complains for read_only points), _reset_all is used to set the registry values to a default
				when the hardware is not reachable....
				
				if register in self.defaults:
				self.point_map[register]._value = self.defaults[register]
				if( self._verboseness == 2 ):
					_log.info( "Universal Resetting Value for '{}' from {} to {}".format(register.point_name, old_value, register._value))
			else:
				if( self._verboseness == 2 ):
					_log.info( "No Default Value Found while Resetting '{}'.".format(register.point_name))
			'''

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
