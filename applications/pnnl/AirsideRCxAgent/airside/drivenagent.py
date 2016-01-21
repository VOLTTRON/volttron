# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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
from datetime import datetime, timedelta as td
import logging
import sys
import re

from dateutil.parser import parse

from volttron.platform.agent import BaseAgent, PublishMixin, matching, utils
from volttron.platform.agent.driven import ConversionMapper
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import (headers as headers_mod, topics)
from copy import deepcopy

__author1__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'
__author2__ = 'Robert Lutes <robert.lutes@pnnl.gov>'
__copyright__ = 'Copyright (c) 2015, Battelle Memorial Institute'
__license__ = 'FreeBSD'


def DrivenAgent(config_path, **kwargs):
    '''Driven harness for deployment of OpenEIS applications in VOLTTRON.'''
    conf = utils.load_config(config_path)
    arguments = conf.get('arguments', None)
    assert arguments
    from_file = arguments.get('From File', False)
    mode = True if conf.get('mode', 'PASSIVE') == 'ACTIVE' else False
    utils.setup_logging()
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
    mode = True if conf.get('mode', 'PASSIVE') == 'ACTIVE' else False
    validation_error = ''
    device = dict((key, conf['device'][key])
                  for key in ['campus', 'building'])
    subdevices = []
    conv_map = conf.get('conversion_map')
    map_names = {}
    for key, value in conv_map.items():
        map_names[key.lower() if isinstance(key, str) else key] = value

    # this implies a sub-device listing
    multiple_dev = isinstance(conf['device']['unit'], dict)
    if multiple_dev:
        units = conf['device']['unit'].keys()

    for item in units:

        # modify the device dict so that unit is now pointing to unit_name
        subdevices.extend(conf['device']['unit'][item]['subdevices'])

    agent_id = conf.get('agentid')
    device.update({'unit': units})
    _analysis = deepcopy(device)
    _analysis_name = conf.get('device').get('analysis_name', 'analysis_name')
    _analysis.update({'analysis_name': _analysis_name})

    if not device:
        validation_error += 'Invalid agent_id specified in config\n'
    if not device:
        validation_error += 'Invalid device path specified in config\n'
    actuator_id = (
        agent_id + '_' + "{campus}/{building}/{unit}".format(**device))

    application = conf.get('application')
    if not application:
        validation_error += 'Invalid application specified in config\n'
    if validation_error:
        _log.error(validation_error)
        raise ValueError(validation_error)

    conf.update(conf.get('arguments'))
    converter = ConversionMapper()
    output_file = conf.get('output_file')
    base_dev = "devices/{campus}/{building}/".format(**device)
    devices_topic = (
        base_dev + '({})(/.*)?/all$'.format('|'.join(re.escape(p) for p in units)))

    unittype_map = conf.get('unittype_map', None)
    assert unittype_map

    klass = _get_class(application)
    # This instances is used to call the applications run method when
    # data comes in on the message bus.  It is constructed here
    # so that_process_results each time run is called the application
    # can keep it state.
    app_instance = klass(**conf)

    class Agent(PublishMixin, BaseAgent):
        '''Agent listens to message bus device and runs when data is published.
        '''
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self._update_event = None
            self._update_event_time = None
            self.keys = None
            # master is where we copy from to get a poppable list of
            # subdevices that should be present before we run the analysis.
            self._master_subdevices = subdevices
            self._needed_subdevices = []
            self._master_devices = units
            self._subdevice_values = {}
            self._needed_devices = []
            self._device_values = {}
            self._initialize_devices()
            self.received_input_datetime = None
            self._kwargs = kwargs
            self.commands = {}
            self.current_point = None
            self.current_key = None
            if output_file is not None:
                with open(output_file, 'w') as writer:
                    writer.close()
            self._header_written = False

        def _initialize_devices(self):
            self._needed_subdevices = deepcopy(self._master_subdevices)
            self._needed_devices = deepcopy(self._master_devices)
            self._subdevice_values = {}
            self._device_values = {}

        def _should_run_now(self):
            # Assumes the unit/all values will have values.
            if not len(self._device_values.keys()) > 0:
                return False
            return not (len(self._needed_subdevices) > 0 or
                        len(self._needed_devices) > 0)

        @matching.match_regex(devices_topic)
        def on_rec_analysis_message(self, topic, headers, message, matched):
            '''Subscribe to device data and assemble data set to pass

            to applications.
            '''
            obj = jsonapi.loads(message[0])
            if isinstance(obj, list):
                obj = obj[0]
            dev_list = topic.split('/')
            device_or_subdevice = dev_list[-2]
            device_id = [dev for dev in self._master_devices if dev == device_or_subdevice]
            subdevice_id = [dev for dev in self._master_subdevices if dev == device_or_subdevice]
            if not device_id and not subdevice_id:
                return
            if isinstance(device_or_subdevice, unicode):
                device_or_subdevice = (
                    device_or_subdevice.decode('utf-8').encode('ascii'))

            def agg_subdevice(obj):
                sub_obj = {}
                for key, value in obj.items():
                    sub_key = ''.join([key, '_', device_or_subdevice])
                    sub_obj[sub_key] = value
                if len(dev_list) > 5:
                    self._subdevice_values.update(sub_obj)
                    self._needed_subdevices.remove(device_or_subdevice)
                else:
                    self._device_values.update(sub_obj)
                    self._needed_devices.remove(device_or_subdevice)
                return
            # The below if statement is used to distinguish between unit/all
            # and unit/sub-device/all
            if (device_or_subdevice not in self._needed_devices and
                    device_or_subdevice not in self._needed_subdevices):
                _log.error("Warning device values already present, "
                           "reinitializing")
                self._initialize_devices()
            agg_subdevice(obj)

            if self._should_run_now():
                field_names = {}
                self._device_values.update(self._subdevice_values)
                for k, v in self._device_values.items():
                    field_names[k.lower() if isinstance(k, str) else k] = v
                if not converter.initialized and \
                        conv_map is not None:
                    converter.setup_conversion_map(
                        map_names,
                        field_names
                    )
                if from_file:
                    _timestamp = parse(headers.get('Date'), fuzzy=True)
                    self.received_input_datetime = _timestamp
                else:
                    _timestamp = datetime.now()
                    self.received_input_datetime = datetime.utcnow()

                obj = converter.process_row(field_names)
                results = app_instance.run(_timestamp, obj)
                # results = app_instance.run(
                # dateutil.parser.parse(self._subdevice_values['Timestamp'],
                #                       fuzzy=True), self._subdevice_values)
                self._process_results(results)
                self._initialize_devices()
            else:
                needed = deepcopy(self._needed_devices)
                needed.extend(self._needed_subdevices)
                _log.info("Still need {} before running."
                          .format(needed))

        def _process_results(self, results):
            '''Run driven application with converted data and write the app
            results to a file or database.
            '''
            _log.debug('Processing Results!')
            for key, value in results.commands.iteritems():
                _log.debug("COMMAND: {}->{}".format(key, value))
            for value in results.log_messages:
                _log.debug("LOG: {}".format(value))
            for key, value in results.table_output.iteritems():
                _log.debug("TABLE: {}->{}".format(key, value))
            if output_file is not None:
                if len(results.table_output.keys()) > 0:
                    for _, v in results.table_output.items():
                        fname = output_file  # +"-"+k+".csv"
                        for r in v:
                            with open(fname, 'a+') as f:
                                keys = r.keys()
                                fout = csv.DictWriter(f, keys)
                                if not self._header_written:
                                    fout.writeheader()
                                    self._header_written = True
                                # if not header_written:
                                    # fout.writerow(keys)
                                fout.writerow(r)
                                f.close()

            def get_unit(point):
                ''' Get a unit type based upon the regular expression in the config file.

                    if NOT found returns percent as a default unit.
                '''
                for k, v in unittype_map.items():
                    if re.match(k, point):
                        return v
                return 'percent'

            # publish to message bus.
            if len(results.table_output.keys()) > 0:
                headers = {
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                    headers_mod.DATE: str(self.received_input_datetime),
                }
                for _, v in results.table_output.items():
                    for r in v:
                        for key, value in r.iteritems():
                            if isinstance(value, bool):
                                value = int(value)
                            for item in units:
                                _analysis['unit'] = item
                                analysis_topic = topics.ANALYSIS_VALUE(
                                    point=key, **_analysis)

                                datatype = 'float'
                                if isinstance(value, int):
                                    datatype = 'int'
                                kbase = key[key.rfind('/')+1:]
                                message = [{kbase: value},
                                           {kbase: {'tz': 'US/Pacific',
                                                    'type': datatype,
                                                    'units': 'float',
                                                    }
                                            }]
                                self.publish_json(analysis_topic,
                                                  headers, message)

            if results.commands and mode:
                self.commands = results.commands
                if self.keys is None:
                    self.keys = self.commands.keys()
                self.schedule_task()

        def schedule_task(self):
            '''Schedule access to modify device controls.'''
            _log.debug('Schedule Device Access')
            headers = {
                'type':  'NEW_SCHEDULE',
                'requesterID': agent_id,
                'taskID': actuator_id,
                'priority': 'LOW'
                }
            start = datetime.now()
            end = start + td(seconds=30)
            start = str(start)
            end = str(end)
            self.publish_json(topics.ACTUATOR_SCHEDULE_REQUEST(), headers,
                              [["{campus}/{building}/{unit}".format(**device),
                                start, end]])

        def command_equip(self):
            '''Execute commands on configured device.'''
            self.current_key = self.keys[0]
            value = self.commands[self.current_key]
            headers = {
                'Content-Type': 'text/plain',
                'requesterID': agent_id,
                }
            self.publish(topics.ACTUATOR_SET(point=self.current_key, **device),
                         headers, str(value))

        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})
        @matching.match_exact(topics.ACTUATOR_SCHEDULE_RESULT())
        def schedule_result(self, topic, headers, message, match):
            '''Actuator response (FAILURE, SUCESS).'''
            _log.debug('Actuator Response')
            msg = jsonapi.loads(message[0])
            msg = msg['result']
            _log.debug('Schedule Device ACCESS')
            if self.keys:
                if msg == "SUCCESS":
                    self.command_equip()
                elif msg == "FAILURE":
                    _log.debug('Auto-correction of device failed.')

        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **device))
        def on_set_result(self, topic, headers, message, match):
            '''Setting of point on device was successful.'''
            _log.debug('Set Success:  {point} - {value}'
                       .format(point=self.current_key,
                               value=str(self.commands[self.current_key])))
            _log.debug('set_point({}, {})'.
                       format(self.current_key,
                              self.commands[self.current_key]))
            self.keys.remove(self.current_key)
            if self.keys:
                self.command_equip()
            else:
                _log.debug('Done with Commands - Release device lock.')
                headers = {
                    'type': 'CANCEL_SCHEDULE',
                    'requesterID': agent_id,
                    'taskID': actuator_id
                    }
                self.publish_json(topics.ACTUATOR_SCHEDULE_REQUEST(),
                                  headers, {})
                self.keys = None

        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **device))
        def on_set_error(self, topic, headers, message, match):
            '''Setting of point on device failed, log failure message.'''
            _log.debug('Set ERROR')
            msg = jsonapi.loads(message[0])
            msg = msg['type']
            _log.debug('Actuator Error: ({}, {}, {})'.
                       format(msg,
                              self.current_key,
                              self.commands[self.current_key]))
            self.keys.remove(self.current_key)
            if self.keys:
                self.command_equip()
            else:
                headers = {
                    'type':  'CANCEL_SCHEDULE',
                    'requesterID': agent_id,
                    'taskID': actuator_id
                    }
                self.publish_json(topics.ACTUATOR_SCHEDULE_REQUEST(),
                                  headers, {})
                self.keys = None

    Agent.__name__ = 'DrivenLoggerAgent'
    return Agent(**kwargs)


def _get_class(kls):
    '''Get driven application information.'''
    parts = kls.split('.')
    module = ".".join(parts[:-1])
    main_mod = __import__(module)
    for comp in parts[1:]:
        main_mod = getattr(main_mod, comp)
    return main_mod


def main(argv=sys.argv):
    ''' Main method.'''
    utils.default_main(DrivenAgent,
                       description='driven agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
