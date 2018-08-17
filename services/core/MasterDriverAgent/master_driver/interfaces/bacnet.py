
# Copyright (c) 2017, Battelle Memorial Institute
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
#
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


from master_driver.interfaces import BaseInterface, BaseRegister
import logging

from datetime import datetime, timedelta

from master_driver.driver_exceptions import DriverConfigError
from volttron.platform.vip.agent import errors
from volttron.platform.jsonrpc import RemoteError

#Logging is completely configured by now.
_log = logging.getLogger(__name__)

class Register(BaseRegister):
    def __init__(self, instance_number, object_type, property_name, read_only, pointName, units,
                 description = '',
                 priority = None,
                 list_index = None):
        super(Register, self).__init__("byte", read_only, pointName, units, description = '')
        self.instance_number = int(instance_number)
        self.object_type = object_type
        self.property = property_name
        self.priority = priority
        self.index = list_index

DEFAULT_COV_LIFETIME = 180
COV_UPDATE_BUFFER = 3

class Interface(BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.register_count = 10000
        self.register_count_divisor = 1
        self.cov_points = []

    def configure(self, config_dict, registry_config_str):
        self.min_priority = config_dict.get("min_priority", 8)
        self.parse_config(registry_config_str)
        self.target_address = config_dict.get("device_address")
        self.device_id = int(config_dict.get("device_id"))

        self.cov_lifetime = config_dict.get("cov_lifetime", DEFAULT_COV_LIFETIME)

        self.proxy_address = config_dict.get("proxy_address", "platform.bacnet_proxy")

        self.max_per_request = config_dict.get("max_per_request")
        self.use_read_multiple = config_dict.get("use_read_multiple", True)
        self.timeout = float(config_dict.get("timeout", 30.0))

        self.ping_retry_interval = timedelta(seconds=config_dict.get("ping_retry_interval", 5.0))
        self.scheduled_ping = None

        self.ping_target()

        # list of points to establish change of value subscriptions with, generated from the registry config
        for point_name in self.cov_points:
            self.establish_cov_subscription(point_name, DEFAULT_COV_LIFETIME, True)

    def schedule_ping(self):
        if self.scheduled_ping is None:
            now = datetime.now()
            next_try = now + self.ping_retry_interval
            self.scheduled_ping = self.core.schedule(next_try, self.ping_target)

    def ping_target(self):
        #Some devices (mostly RemoteStation addresses behind routers) will not be reachable without
        # first establishing the route to the device. Sending a directed WhoIsRequest is will
        # settle that for us when the response comes back.

        pinged = False
        try:
            self.vip.rpc.call(self.proxy_address, 'ping_device', self.target_address, self.device_id).get(timeout=self.timeout)
            pinged = True
        except errors.Unreachable:
            _log.warning("Unable to reach BACnet proxy.")

        except errors.VIPError:
            _log.warning("Error trying to ping device.")

        self.scheduled_ping = None

        #Schedule retry.
        if not pinged:
            self.schedule_ping()


    def get_point(self, point_name, get_priority_array=False):
        register = self.get_register_by_name(point_name)
        property_name = "priorityArray" if get_priority_array else register.property
        register_index = None if get_priority_array else register.index
        result = self.vip.rpc.call(self.proxy_address, 'read_property',
                                   self.target_address, register.object_type,
                                   register.instance_number, property_name, register_index).get(timeout=self.timeout)
        return result

    def set_point(self, point_name, value, priority=None):
        #TODO: support writing from an array.
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)

        if priority is not None and priority < self.min_priority:
            raise  IOError("Trying to write with a priority lower than the minimum of "+str(self.min_priority))

        #We've already validated the register priority against the min priority.
        args = [self.target_address, value,
                register.object_type,
                register.instance_number,
                register.property,
                priority if priority is not None else register.priority,
                register.index]
        result = self.vip.rpc.call(self.proxy_address, 'write_property', *args).get(timeout=self.timeout)
        return result

    def scrape_all(self):
        #TODO: support reading from an array.
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        for register in read_registers + write_registers:
            point_map[register.point_name] = [register.object_type,
                                              register.instance_number,
                                              register.property,
                                              register.index]

        while True:
            try:
                result = self.vip.rpc.call(self.proxy_address, 'read_properties',
                                               self.target_address, point_map,
                                               self.max_per_request, self.use_read_multiple).get(timeout=self.timeout)
            except RemoteError as e:
                if "segmentationNotSupported" in e.message:
                    if self.max_per_request <= 1:
                        _log.error("Receiving a segmentationNotSupported error with 'max_per_request' setting of 1.")
                        raise
                    self.register_count_divisor += 1
                    self.max_per_request = max(int(self.register_count/self.register_count_divisor), 1)
                    _log.info("Device requires a lower max_per_request setting. Trying: "+str(self.max_per_request))
                    continue
                else:
                    raise
            except errors.Unreachable:
                #If the Proxy is not running bail.
                _log.warning("Unable to reach BACnet proxy.")
                self.schedule_ping()
                raise
            else:
                break

        return result

    def revert_all(self, priority=None):
        """Revert entrire device to it's default state"""
        #TODO: Add multipoint write support
        write_registers = self.get_registers_by_type("byte", False)
        for register in write_registers:
            self.revert_point(register.point_name, priority=priority)

    def revert_point(self, point_name, priority=None):
        """Revert point to it's default state"""
        self.set_point(point_name, None, priority=priority)


    def parse_config(self, configDict):
        if configDict is None:
            return

        self.register_count = len(configDict)

        for regDef in configDict:
            #Skip lines that have no address yet.
            if not regDef.get('Volttron Point Name'):
                continue

            io_type = regDef.get('BACnet Object Type')
            read_only = regDef.get('Writable').lower() != 'true'
            point_name = regDef.get('Volttron Point Name')

            # checks if the point is flagged for change of value
            is_cov = regDef.get("COV Flag", 'false').lower() == "true"

            index = int(regDef.get('Index'))

            list_index = regDef.get('Array Index', '')
            list_index = list_index.strip()

            if not list_index:
                list_index = None
            else:
                list_index = int(list_index)

            priority = regDef.get('Write Priority', '')
            priority = priority.strip()
            if not priority:
                priority = None
            else:
                priority = int(priority)

                if priority < self.min_priority:
                    message = "{point} configured with a priority {priority} which is lower than than minimum {min}."
                    raise DriverConfigError(message.format(point=point_name,
                                                           priority=priority,
                                                           min=self.min_priority))

            description = regDef.get('Notes', '')
            units = regDef.get('Units')
            property_name = regDef.get('Property')

            register = Register(index,
                                io_type,
                                property_name,
                                read_only,
                                point_name,
                                units,
                                description = description,
                                priority = priority,
                                list_index = list_index)

            self.insert_register(register)

            if is_cov:
                self.cov_points.append(point_name)


    def establish_cov_subscription(self, point_name, lifetime, renew=False):
        """Asks the BACnet proxy to establish a COV subscription for the point via RPC.
        If lifetime is specified, the subscription will live for that period, else the
        subscription will last indefinitely. Default period of 3 minutes. If renew is
        True, the the core scheduler will call this method again near the expiration
        of the subscription."""
        register = self.get_register_by_name(point_name)
        try:
            self.vip.rpc.call(self.proxy_address, 'create_COV_subscription', self.target_address,
                              point_name, register.object_type, register.instance_number,
                              lifetime=lifetime)
        except errors.Unreachable:
            _log.warning("Unable to establish a subscription via the bacnet proxy as it was unreachable.")
        # Schedule COV resubscribe
        if renew and (lifetime > COV_UPDATE_BUFFER):
            now = datetime.now()
            next_sub_update = now + timedelta(seconds=(lifetime - COV_UPDATE_BUFFER))
            self.core.schedule(next_sub_update, self.establish_cov_subscription, point_name, lifetime,
                               renew)
