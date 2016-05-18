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
import csv
import logging
import sys
import gevent
from collections import defaultdict
from datetime import datetime as dt, timedelta as td
from copy import deepcopy
from dateutil.parser import parse

from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.agent.utils import jsonapi, setup_logging
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent.driven import ConversionMapper
from volttron.platform.messaging import (headers as headers_mod, topics)

__version__ = "3.5.0"

__author1__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'
__author2__ = 'Robert Lutes <robert.lutes@pnnl.gov>'
__author3__ = 'Poorva Sharma <poorva.sharma@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'
DATE_FORMAT = '%m-%d-%y %H:%M'

utils.setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.info,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt=DATE_FORMAT)


def driven_agent(config_path, **kwargs):
    """Reads agent configuration and converts it to run driven agent.
    :param kwargs: Any driver specific parameters"""
    config = utils.load_config(config_path)
    arguments = config.get('arguments')
    mode = True if config.get('mode', 'PASSIVE') == 'ACTIVE' else False
    multiple_devices = isinstance(config['device']['unit'], dict)
    campus_building_config = config['device']
    analysis_name = campus_building_config.get('analysis_name', 'analysis_name')
    analysis_dict = {'analysis_name': analysis_name}
    arguments.update(analysis_dict)
    agent_id = config.get('agentid', None)
    actuator_id = agent_id if agent_id is not None else analysis_name
    campus_building = dict((key, campus_building_config[key]) for key in ['campus', 'building'])
    analysis = deepcopy(campus_building)
    analysis.update(analysis_dict)
    device_config = config['device']['unit']
    command_devices = device_config.keys()
    device_topic_dict = {}
    device_topic_list = []
    subdevices_list = []
    vip_destination = config.get('vip_destination', None)
    from_file = config.get('from_file')
    for device_name in device_config:
        device_topic = topics.DEVICES_VALUE(campus=campus_building.get('campus'),
                                            building=campus_building.get('building'),
                                            unit=device_name,
                                            path='',
                                            point='all')
        device_topic_dict.update({device_topic: device_name})
        device_topic_list.append(device_name)
        if multiple_devices:
            for subdevice in device_config[device_name]['subdevices']:
                subdevices_list.append(subdevice)
                subdevice_topic = topics.DEVICES_VALUE(campus=campus_building.get('campus'),
                                                       building=campus_building.get('building'),
                                                       unit=device_name,
                                                       path=subdevice,
                                                       point='all')
                subdevice_name = device_name + "/" + subdevice
                device_topic_dict.update({subdevice_topic: subdevice_name})
                device_topic_list.append(subdevice_name)

    base_actuator_path = topics.RPC_DEVICE_PATH(campus=campus_building.get('campus', ''),
                                                building=campus_building.get('building', ''),
                                                unit=None,
                                                path='',
                                                point=None)
    device_lock_duration = config.get('device_lock_duration', 1.25)
    conversion_map = config.get('conversion_map')
    map_names = {}
    for key, value in conversion_map.items():
        map_names[key.lower() if isinstance(key, str) else key] = value
    application = config.get('application')
    validation_error = ''
    if not application:
        validation_error = 'Invalid application specified in config\n'
    if validation_error:
        _log.error(validation_error)
        raise ValueError(validation_error)
    config.update(config.get('arguments'))
    converter = ConversionMapper()
    output_file_prefix = config.get('output_file')
    #unittype_map = config.get('unittype_map', None)
    #assert unittype_map

    klass = _get_class(application)
    # This instances is used to call the applications run method when
    # data comes in on the message bus.  It is constructed here
    # so that_process_results each time run is called the application
    # can keep it state.
    app_instance = klass(**arguments)


    class DrivenAgent(Agent):
        """Agent listens to message bus device and runs when data is published.
        """

        def __init__(self, **kwargs):
            """
            Initializes agent
            :param kwargs: Any driver specific parameters"""

            super(DrivenAgent, self).__init__(**kwargs)

            # master is where we copy from to get a poppable list of
            # subdevices that should be present before we run the analysis.
            self._master_devices = device_topic_list
            self._needed_devices = []
            self._device_values = {}
            self._initialize_devices()
            self.received_input_datetime = None
            self._kwargs = kwargs
            self._header_written = False
            self.file_creation_set = set()
            self.actuation_vip = self.vip.rpc
            if vip_destination:
                self.agent = self.setup_remote_actuation(vip_destination)
                self.actuation_vip = self.agent.vip.rpc

        def _initialize_devices(self):
            self._needed_devices = deepcopy(self._master_devices)
            self._device_values = {}

        def setup_remote_actuation(self, vip_destination):
            event = gevent.event.Event()
            agent = Agent(address=vip_destination)
            gevent.spawn(agent.core.run, event)
            event.wait(timeout=15)
            return agent

        @Core.receiver('onstart')
        def starup(self, sender, **kwargs):
            """
            Starts up the agent and subscribes to device topics
            based on agent configuration.
            :param sender:
            :param kwargs: Any driver specific parameters
            :type sender: str"""
            self._initialize_devices()
            for device_topic in device_topic_dict:
                _log.info('Subscribing to ' + device_topic)
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_topic,
                                          callback=self.on_analysis_message)

        def _should_run_now(self):
            """
            Checks if messages from all the devices are received
                before running application
            :returns: True or False based on received messages.
            :rtype: boolean"""
            # Assumes the unit/all values will have values.
            if not len(self._device_values.keys()) > 0:
                return False
            return not len(self._needed_devices) > 0

        def on_analysis_message(self, peer, sender, bus, topic, headers, message):
            """
            Subscribe to device data and assemble data set to pass
                to applications.
            :param peer:
            :param sender: device name
            :param bus:
            :param topic: device path topic
            :param headers: message headers
            :param message: message containing points and values dict
                    from device with point type
            :type peer: str
            :type sender: str
            :type bus: str
            :type topic: str
            :type headers: dict
            :type message: dict"""

            device_data = message[0]
            if isinstance(device_data, list):
                device_data = device_data[0]

            def aggregate_subdevice(device_data):
                tagged_device_data = {}
                device_tag = device_topic_dict[topic]
                if device_tag not in self._needed_devices:
                    return False
                for key, value in device_data.items():
                    device_data_tag = '&'.join([key, device_tag])
                    tagged_device_data[device_data_tag] = value
                self._device_values.update(tagged_device_data)
                self._needed_devices.remove(device_tag)
                return True

            device_needed = aggregate_subdevice(device_data)
            if not device_needed:
                _log.error("Warning device values already present, "
                           "reinitializing")
                self._initialize_devices()
            if self._should_run_now():
                field_names = {}
                for key, value in self._device_values.items():
                    field_names[key.lower() if isinstance(key, str) else key] = value
                if not converter.initialized and conversion_map is not None:
                    converter.setup_conversion_map(map_names, field_names)
                if from_file:
                    _timestamp = parse(headers.get('Date'))
                    self.received_input_datetime = _timestamp
                else:
                    _timestamp = dt.now()
                    self.received_input_datetime = dt.utcnow()

                device_data = converter.process_row(field_names)
                results = app_instance.run(_timestamp, device_data)
                # results = app_instance.run(
                # dateutil.parser.parse(self._subdevice_values['Timestamp'],
                #                       fuzzy=True), self._subdevice_values)
                self._process_results(results)
                self._initialize_devices()
            else:
                _log.info("Still need {} before running.".format(self._needed_devices))

        def _process_results(self, results):
            """
            Runs driven application with converted data. Calls appropriate
                methods to process commands, log and table_data in results.
            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven
            :returns: Same as results param.
            :rtype: Results object \\volttron.platform.agent.driven"""
            _log.info('Processing Results!')
            actuator_error = True
            if mode:
                if results.devices:
                    actuator_error = self.actuator_request(results.devices)
                elif results.commands:
                    actuator_error = self.actuator_request(command_devices)
                if not actuator_error:
                    results = self.actuator_set(results)
            for value in results.log_messages:
                _log.info("LOG: {}".format(value))
            for key, value in results.table_output.items():
                _log.info("TABLE: {}->{}".format(key, value))
            if output_file_prefix is not None:
                results = self.create_file_output(results)
            if len(results.table_output.keys()):
                results = self.publish_analysis_results(results)
            return results

        def publish_analysis_results(self, results):
            """
            Publish table_data in analysis results to the message bus for
                capture by the data historian.

            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven
            :returns: Same as results param.
            :rtype: Results object \\volttron.platform.agent.driven"""

            headers = {
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                headers_mod.DATE: str(self.received_input_datetime),
            }
            for app, analysis_table in results.table_output.items():
                try:
                    name_timestamp = app.split('&')
                    _name = name_timestamp[0]
                    timestamp = name_timestamp[1]
                except:
                    _name = app
                    timestamp = str(self.received_input_datetime)
                headers = {
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                    headers_mod.DATE: timestamp,
                }

                # The keys in this publish should look like the following
                # with the values being a dictionary of points off of these
                # base topics
                #
                # Schedule-Reset ACCx/data/interior_ahu/vav1600e
                # Schedule-Reset ACCx/data/interior_ahu/vav1534
                to_publish = defaultdict(list)
                for entry in analysis_table:
                    for key, value in entry.items():
                        for _device in command_devices:
                            analysis['unit'] = _device
                            analysis_topic = topics.ANALYSIS_VALUE(point=key, **analysis)
                            datatype = 'float'
                            if isinstance(value, int):
                                datatype = 'int'
                            kbase = key[key.rfind('/') + 1:]
                            topic_without_point = analysis_topic[:analysis_topic.rfind('/')]

                            if not to_publish[topic_without_point]:
                                to_publish[topic_without_point] = [{}, {}]

                            to_publish[topic_without_point][0][kbase] = value
                            to_publish[topic_without_point][1][kbase] = {
                                'tz': 'US/Pacific',
                                'type': datatype,
                                'units': 'float',
                                }

                for equipment, _analysis in to_publish.items():
                    self.vip.pubsub.publish('pubsub', equipment, headers, _analysis)

                to_publish.clear()
            return results

        def create_file_output(self, results):
            """
            Create results/data files for testing and algorithm validation
            if table data is present in the results.

            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven
            :returns: Same as results param.
            :rtype: Results object \\volttron.platform.agent.driven"""
            for key, value in results.table_output.items():
                name_timestamp = key.split('&')
                _name = name_timestamp[0]
                timestamp = name_timestamp[1]
                file_name = output_file_prefix + "-" + _name + ".csv"
                if file_name not in self.file_creation_set:
                    self._header_written = False
                self.file_creation_set.update([file_name])
                for row in value:
                    with open(file_name, 'a+') as file_to_write:
                        row.update({'Timestamp': timestamp})
                        _keys = row.keys()
                        file_output = csv.DictWriter(file_to_write, _keys)
                        if not self._header_written:
                            file_output.writeheader()
                            self._header_written = True
                        file_output.writerow(row)
                    file_to_write.close()
            return results

        def actuator_request(self, command_equip):
            """
            Calls the actuator's request_new_schedule method to get
                    device schedule
            :param command_equip: contains the names of the devices
                that will be scheduled with the ActuatorAgent.
            :type: dict or list
            :returns: Return result from request_new_schedule method
                and True or False for error in scheduling device.
            :rtype: boolean
            :Return Values:

                request_error = True/False

            warning:: Calling without previously scheduling a device and not within
                         the time allotted will raise a LockError"""

            _now = dt.now()
            str_now = _now.strftime(DATE_FORMAT)
            _end = _now + td(minutes=device_lock_duration)
            str_end = _end.strftime(DATE_FORMAT)
            for device in command_equip:
                actuation_device = base_actuator_path(unit=device, point='')
                schedule_request = [[actuation_device, str_now, str_end]]
                try:
                    _log.info('Make Request {} for start {} and end {}'.format(actuation_device, str_now, str_end))
                    result = self.actuation_vip.call('platform.actuator',
                                                     'request_new_schedule',
                                                     actuator_id, actuation_device, 'HIGH',
                                                     schedule_request).get(timeout=15)
                except RemoteError as ex:
                    _log.warning("Failed to schedule device {} (RemoteError): {}".format(device, str(ex)))
                    request_error = True
                if result['result'] == 'FAILURE':
                    if result['info'] == 'TASK_ID_ALREADY_EXISTS':
                        _log.info('Task to schedule device already exists ' + device)
                        request_error = False
                    else:
                        _log.warn('Failed to schedule device (unavailable) ' + device)
                        request_error = True
                else:
                    request_error = False

            return request_error

        def actuator_set(self, results):
            """
            Calls the actuator's set_point method to set point on device

            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven"""

            def make_actuator_set(device, point_value_dict):
                for point, new_value in point_value_dict.items():
                    point_path = base_actuator_path(unit=device, point=point)
                    try:
                        _log.info('Set point {} to {}'.format(point_path, new_value))
                        result = self.actuation_vip.call('platform.actuator', 'set_point',
                                                         actuator_id, point_path,
                                                         new_value).get(timeout=15)
                    except RemoteError as ex:
                        _log.warning("Failed to set {} to {}: {}".format(point_path, new_value, str(ex)))
                        continue

            for device, point_value_dict in results.devices.items():
                make_actuator_set(device, point_value_dict)

            for device in command_devices:
                make_actuator_set(device, results.commands)
            return results

    DrivenAgent.__name__ = 'DrivenLoggerAgent'
    return DrivenAgent(**kwargs)


def _get_class(kls):
    """Get driven application information."""
    parts = kls.split('.')
    module = ".".join(parts[:-1])
    main_mod = __import__(module)
    for comp in parts[1:]:
        main_mod = getattr(main_mod, comp)
    return main_mod


def main(argv=sys.argv):
    ''' Main method.'''
    utils.vip_main(driven_agent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
