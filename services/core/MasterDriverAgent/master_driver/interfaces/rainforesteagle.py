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

from csv import DictReader
import logging
import requests

from master_driver.interfaces import (BaseInterface,
                                      BaseRegister,
                                      BasicRevert,
                                      DriverInterfaceError)

_log = logging.getLogger(__name__)

# This driver uses the Rainforest Eagle REST API available on
# rainforestautomation.com/developer

## Accessible operations
# get_network_status
# get_instantaneous_demand
# get_price
# get_current_summation - implemented as two registers
# get_demand_peaks - implemeted as two registers

## Not implemented
# get_network_info
# list_network
# get_message
# confirm_message
# get_history_data
# reboot
# set_schedule
# get_schedule

auth = None
macid = None
address = None


class NetworkStatus(BaseRegister):
    def __init__(self):
        super(NetworkStatus, self).__init__('byte', True, 'NetworkStatus', 'string')

    def value(self):
        command = '<Command>\
                     <Name>get_network_status</Name>\
                     <Format>JSON</Format>\
                   </Command>'
        result = requests.post(address, auth=auth, data=command)

        if result.status_code != requests.codes.ok:
            return str(result.status_code)

        result = result.json()['NetworkStatus']
        return result['Status']


class InstantaneousDemand(BaseRegister):
    def __init__(self):
        super(InstantaneousDemand, self).__init__('byte', True, 'InstantaneousDemand', 'float')

    def value(self):
        command = '<Command>\
                     <Name>get_instantaneous_demand</Name>\
                     <MacId>{}</MacId>\
                     <Format>JSON</Format>\
                   </Command>'.format(macid)
        result = requests.post(address, auth=auth, data=command)

        result = result.json()['InstantaneousDemand']
        demand = float(int(result['Demand'], 16))

        multiplier = float(int(result['Multiplier'], 16))
        if multiplier == 0:
            multiplier = 1

        divisor = float(int(result['Divisor'], 16))
        if divisor == 0:
            divisor = 1

        return demand * (multiplier / divisor)


class PriceCluster(BaseRegister):
    def __init__(self):
        super(PriceCluster, self).__init__('byte', True, 'PriceCluster', 'float')

    def value(self):
        command = '<Command>\
                     <Name>get_price</Name>\
                     <MacId>{}</MacId>\
                     <Format>JSON</Format>\
                   </Command>'.format(macid)
        result = requests.post(address, auth=auth, data=command)

        result = result.json()['PriceCluster']
        price = float(int(result['Price'], 16))
        trailing_digits = int(result['TrailingDigits'], 16)

        return price / (10 ** trailing_digits)


def get_summation(key):
    command = '<Command>\
                 <Name>get_current_summation</Name>\
                 <MacId>{}</MacId>\
                 <Format>JSON</Format>\
               </Command>'.format(macid)
    result = requests.post(address, auth=auth, data=command)

    result = result.json()['CurrentSummation']
    summation = float(int(result[key], 16))

    multiplier = float(int(result['Multiplier'], 16))
    if multiplier == 0:
        multiplier = 1

    divisor = float(int(result['Divisor'], 16))
    if divisor == 0:
        divisor = 1

    return summation * (multiplier / divisor)


class SummationDelivered(BaseRegister):
    def __init__(self):
        super(SummationDelivered, self).__init__('byte', True, 'SummationDelivered', 'float')

    def value(self):
        return get_summation(self.__class__.__name__)


class SummationReceived(BaseRegister):
    def __init__(self):
        super(SummationReceived, self).__init__('byte', True, 'SummationReceived', 'float')

    def value(self):
        return get_summation(self.__class__.__name__)


def get_demand_peaks(key):
    command = '<Command>\
                 <Name>get_demand_peaks</Name>\
                 <Format>JSON</Format>\
               </Command>'
    result = requests.post(address, auth=auth, data=command)

    result = result.json()['DemandPeaks']
    return float(result[key])


class PeakDelivered(BaseRegister):
    def __init__(self):
        super(PeakDelivered, self).__init__('byte', True, 'PeakDelivered', 'float')

    def value(self):
        return get_demand_peaks(self.__class__.__name__)


class PeakReceived(BaseRegister):
    def __init__(self):
        super(PeakReceived, self).__init__('byte', True, 'PeakReceived', 'float')

    def value(self):
        return get_demand_peaks(self.__class__.__name__)


eagle_registers = {
    'NetworkStatus': NetworkStatus,
    'InstantaneousDemand': InstantaneousDemand,
    'PriceCluster': PriceCluster,
    'SummationDelivered': SummationDelivered,
    'SummationReceived': SummationReceived,
    'PeakDelivered': PeakDelivered,
    'PeakReceived': PeakReceived
}


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, register_config):
        global auth, macid, address

        username = config_dict['username']
        password = config_dict['password']
        auth = (username, password)

        macid = config_dict['macid']
        address = config_dict['address']

        if register_config is None:
            register_config = []

        for name in register_config:
            register = eagle_registers[name]
            self.insert_register(register())

        # Always add a network status register
        try:
            self.get_register_by_name('NetworkStatus')
        except DriverInterfaceError:
            self.insert_register(NetworkStatus())

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.value()

    def _set_point(self, point_name, value):
        pass

    def _scrape_all(self):
        # skip the scrape if there are anomalous network conditions
        ns_register = self.get_register_by_name('NetworkStatus')
        network_status = ns_register.value()
        if network_status != 'Connected':
            return {ns_register.point_name: network_status}

        # scrape points
        result = {}
        registers = self.get_registers_by_type('byte', True)
        for r in registers:
            result[r.point_name] = r.value()

        return result
