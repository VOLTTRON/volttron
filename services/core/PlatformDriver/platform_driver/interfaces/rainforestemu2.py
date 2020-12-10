# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
import time
import sys

from master_driver.interfaces import (BaseInterface,
                                      BaseRegister,
                                      BasicRevert,
                                      DriverInterfaceError)

_log = logging.getLogger(__name__)


## Accessible operations
# get_network_info
# get_instantaneous_demand
# get_price

emu_instance = None
EMU_SLEEP_TIME = 5

# String required for some ops but unknown purpose
EMU_REFRESH = "Y"

class NetworkInfo(BaseRegister):
    def __init__(self):
        super(NetworkInfo, self).__init__('byte', True, 'NetworkInfo', 'string')

    def value(self):
        emu_instance.start_serial()
        emu_instance.get_network_info()
        time.sleep(EMU_SLEEP_TIME)
        emu_instance.stop_serial()
        return emu_instance.NetworkInfo.Status


class InstantaneousDemand(BaseRegister):
    def __init__(self):
        super(InstantaneousDemand, self).__init__('byte', True, 'InstantaneousDemand', 'float')

    def value(self):
        emu_instance.start_serial()
        emu_instance.get_instantaneous_demand(EMU_REFRESH)
        time.sleep(5)
        emu_instance.stop_serial()
        result = emu_instance.InstantaneousDemand
        demand = float(int(result.Demand, 16))

        multiplier = float(int(result.Multiplier, 16))
        if multiplier == 0:
            multiplier = 1

        divisor = float(int(result.Divisor, 16))
        if divisor == 0:
            divisor = 1

        return demand * (multiplier / divisor)


class PriceCluster(BaseRegister):
    def __init__(self):
        super(PriceCluster, self).__init__('byte', True, 'PriceCluster', 'float')

    def value(self):
        emu_instance.start_serial()
        emu_instance.get_current_price(EMU_REFRESH)
        time.sleep(EMU_SLEEP_TIME)
        emu_instance.stop_serial()
        result = emu_instance.PriceCluster
        price = float(int(result.Price, 16))
        trailing_digits = int(result.TrailingDigits, 16)

        return price / (10 ** trailing_digits)


registers = {
    'NetworkInfo': NetworkInfo,
    'InstantaneousDemand': InstantaneousDemand,
    'PriceCluster': PriceCluster
}


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, register_config):
        global emu_instance

        emu_library_path = config_dict["emu_library_path"]
        sys.path.append(emu_library_path)
        from emu import emu

        tty = config_dict['tty']
        emu_instance = emu(tty)

        if register_config is None:
            register_config = []

        for name in register_config:
            register = registers[name]
            self.insert_register(register())

        # Always add a network info register
        try:
            self.get_register_by_name('NetworkInfo')
        except DriverInterfaceError:
            self.insert_register(NetworkInfo())

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.value()

    def _set_point(self, point_name, value):
        pass

    def _scrape_all(self):
        # skip the scrape if there are anomalous network conditions
        ns_register = self.get_register_by_name('NetworkInfo')
        network_status = ns_register.value()
        if network_status != 'Connected':
            return {ns_register.point_name: network_status}

        # scrape points
        result = {}
        registers = self.get_registers_by_type('byte', True)
        for r in registers:
            result[r.point_name] = r.value()

        return result
