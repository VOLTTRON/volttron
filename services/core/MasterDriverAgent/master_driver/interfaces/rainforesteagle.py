# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

from csv import DictReader
import logging
import requests

from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert

_log = logging.getLogger(__name__)

## Ignored operations
# get_network_info - seems less useful than get_network_status
# get_message
# confirm_message
# reboot

## Accessible operations
# get_network_status
# get_instantaneous_demand
# get_price

## Not implemented
# get_current_summation - returns two things
# get_history_data - requires time arguments
# set_schedule - multiple params
# get_schedule - optional event enum argument

auth = None
macid = None
address = None

REGISTER_TYPE = 'byte'

class NetworkStatus(BaseRegister):
    def __init__(self):
        super(NetworkStatus, self).__init__(REGISTER_TYPE, True, 'NetworkStatus', 'string')

    @property
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
        super(InstantaneousDemand, self).__init__(REGISTER_TYPE, True, 'InstantaneousDemand', 'string')

    @property
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
        super(PriceCluster, self).__init__(REGISTER_TYPE, True, 'PriceCluster', 'string')

    @property
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


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, registry_config_str):
        global auth, macid, address

        username = config_dict['username']
        password = config_dict['password']
        auth = (username, password)

        macid = config_dict['macid']
        address = config_dict['address']

        self.insert_register(NetworkStatus())
        self.insert_register(InstantaneousDemand())
        self.insert_register(PriceCluster())

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)

        return register.value

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError(
                "Trying to write to a point configured read only: " + point_name)

        register.value = register.reg_type(value)
        return register.value

    def _scrape_all(self):
        # Skip the scrape if there are anomalous network conditions
        ns_register = self.get_register_by_name('NetworkStatus')
        network_status = ns_register.value
        if network_status != 'Connected':
            return {ns_register.point_name: network_status}

        result = {}
        registers = self.get_registers_by_type(REGISTER_TYPE, True)
        for r in registers:
            result[r.point_name] = r.value

        return result
