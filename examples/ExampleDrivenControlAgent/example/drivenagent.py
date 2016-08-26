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

from volttron.platform.agent import BaseAgent, PublishMixin, matching, utils
from volttron.platform.agent.driven import ConversionMapper
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import (headers as headers_mod, topics)

__author1__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'
__author2__ = 'Robert Lutes <robert.lutes@pnnl.gov>'
__copyright__ = 'Copyright (c) 2015, Battelle Memorial Institute'
__license__ = 'FreeBSD'
__version__ = '0.1'

def DrivenAgent(config_path, **kwargs):
    '''Driven harness for deployment of OpenEIS applications in VOLTTRON.'''
    config = utils.load_config(config_path)
    mode = True if config.get('mode', 'PASSIVE') == 'ACTIVE' else False
    validation_error = ''
    device = dict((key, config['device'][key])
                  for key in ['campus', 'building', 'unit'])
    agent_id = config.get('agentid')
    if not device:
        validation_error += 'Invalid agent_id specified in config\n'
    if not device:
        validation_error += 'Invalid device path specified in config\n'
    actuator_id = agent_id + '_' +"{campus}/{building}/{unit}".format(**device)
    application = config.get('application')
    if not application:
        validation_error += 'Invalid application specified in config\n'
    utils.setup_logging()
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
    if validation_error:
        _log.error(validation_error)
        raise ValueError(validation_error)
    config.update(config.get('arguments'))
    converter = ConversionMapper()
    output_file = config.get('output_file')
    klass = _get_class(application)

    # This instances is used to call the applications run method when
    # data comes in on the message bus.  It is constructed here so that
    # each time run is called the application can keep it state.
    app_instance = klass(**config)

    class Agent(PublishMixin, BaseAgent):
        '''Agent listens to message bus device and runs when data is published.
        '''
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self._update_event = None
            self._update_event_time = None
            self.keys = None
            self._device_states = {}
            self._kwargs = kwargs
            self.commands = {}
            self.current_point = None
            self.current_key = None
            self.received_input_datetime = None
            if output_file != None:
                with open(output_file, 'w') as writer:
                    writer.close()
            self._header_written = False

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **device))
        def on_received_message(self, topic, headers, message, matched):
            '''Subscribe to device data and convert data to correct type for
            the driven application.
            '''
            _log.debug("Message received")
            _log.debug("MESSAGE: " + jsonapi.dumps(message[0]))
            _log.debug("TOPIC: " + topic)
            data = jsonapi.loads(message[0])
            
            #TODO: grab the time from the header if it's there or use now if not
            self.received_input_datetime = datetime.utcnow()
            results = app_instance.run(self.received_input_datetime, data)
            self._process_results(results)

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
            # publish to output file if available.
            if output_file != None:
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
                            topic = topics.ANALYSIS_VALUE(point=key, **config['device']) #.replace('{analysis}', key)
                            #print "publishing {}->{}".format(topic, value)
                            self.publish_json(topic, headers, value)
            
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
            end = start + td(seconds=300)
            start = str(start)
            end = str(end)
            _log.debug("{campus}/{building}/{unit}".format(**device))
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
            print 'Actuator Response'
            msg = jsonapi.loads(message[0])
            msg = msg['result']
            _log.debug('Schedule Device ACCESS')
            if self.keys:
                if msg == "SUCCESS":
                    self.command_equip()
                elif msg == "FAILURE":
                    print 'auto correction failed'
                    _log.debug('Auto-correction of device failed.')

        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **device))
        def on_set_result(self, topic, headers, message, match):
            '''Setting of point on device was successful.'''
            print ('Set Success:  {point} - {value}'
                   .format(point=self.current_key,
                           value=str(self.commands[self.current_key])))
            _log.debug('set_point({}, {})'.
                       format(self.current_key,
                              self.commands[self.current_key]))
            self.keys.remove(self.current_key)
            if self.keys:
                self.command_equip()
            else:
                print 'Done with Commands - Release device lock.'
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
            print 'Set ERROR'
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

    Agent.__name__ = agent_id
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
                       description='Example VOLTTRON platform™ driven agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
