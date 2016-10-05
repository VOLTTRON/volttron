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
import datetime
import sys
import logging
from dateutil import parser

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import matching, utils, sched
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import topics
from volttron.platform.messaging import headers as headers_mod

MIME_PLAIN_TEXT = headers_mod.CONTENT_TYPE.PLAIN_TEXT
HEADER_NAME_DATE = headers_mod.DATE
HEADER_NAME_CONTENT_TYPE = headers_mod.CONTENT_TYPE
VALUE_RESPONSE_PREFIX = topics.ACTUATOR_VALUE()
ERROR_RESPONSE_PREFIX = topics.ACTUATOR_ERROR()
SCHEDULE_RESPONSE_SUCCESS = 'SUCCESS'
SCHEDULE_RESPONSE_FAILURE = 'FAILURE'
SCHEDULE_ACTION_NEW = 'NEW_SCHEDULE'
SCHEDULE_ACTION_CANCEL = 'CANCEL_SCHEDULE'

__authors__ = ['Robert Lutes <robert.lutes@pnnl.gov>',
               'Kyle Monson <kyle.monson@pnnl.gov>']
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'


def DataPub(config_path, **kwargs):
    '''Emulate device driver to publish data and Actuator
    agent for agent testing.
    '''
    conf = utils.load_config(config_path)
    custom_topic = conf.get('custom_topic', 0)
    pub_interval = float(conf.get('publish_interval'))
    if not custom_topic:
        device_path = (
            ''.join([conf.get('campus'), '/', conf.get('building'), '/']))
        BASETOPIC = conf.get('basetopic')
        dev_list = conf['unit']
    path = conf.get('input_file')

    class Agent(PublishMixin, BaseAgent):
        '''Simulate real device.  Publish csv data to message bus.

        Configuration consists of csv file and publish topic
        '''
        def __init__(self, **kwargs):
            '''Initialize data publisher class attributes.'''
            super(Agent, self).__init__(**kwargs)

            self._agent_id = conf.get('publisherid')
            self._src_file_handle = open(path)
            header_line = self._src_file_handle.readline().strip()
            self._headers = header_line.split(',')
            self.end_time = None
            self.start_time = None
            self.task_id = None
            utils.setup_logging()
            self._log = logging.getLogger(__name__)
            self.scheduled_event = None
            logging.basicConfig(
                level=logging.debug,
                format='%(asctime)s   %(levelname)-8s %(message)s',
                datefmt='%m-%d-%y %H:%M:%S')
            self._log.info('DATA PUBLISHER ID is PUBLISHER')

        def setup(self):
            '''This function is called immediately after initialization'''
            super(Agent, self).setup()

        @periodic(pub_interval)
        def publish_data_or_heartbeat(self):
            '''Publish data from file to message bus.'''
            _data = {}
            now = datetime.datetime.now().isoformat(' ')
            if not self._src_file_handle.closed:
                line = self._src_file_handle.readline()
                line = line.strip()
                data = line.split(',')
                if line:
                    # Create 'all' message
                    for i in xrange(0, len(self._headers)):
                        _data[self._headers[i]] = data[i]
                    if custom_topic:
                        # data_dict = jsonapi.dumps(_data)
                        self.publish_json(
                            custom_topic,
                            {HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                             HEADER_NAME_DATE: now}, _data)
                        return
                    sub_dev = {}
                    device_dict = {}
                    for _k, _v in dev_list.items():
                        for k, val in _data.items():
                            if k.startswith(_k):
                                pub_k = k[len(_k):]
                                device_dict.update({pub_k.split('_')[1]: val})
                                cur_top = (''.join([BASETOPIC, '/',
                                                    device_path,
                                                    _k, '/',
                                                    pub_k.split('_')[1]]))
                                self.publish_json(
                                    cur_top,
                                    {HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                                     HEADER_NAME_DATE: now}, val)
                    # device_dict = jsonapi.dumps(device_dict)
                        if device_dict:
                            self.publish_json(
                                BASETOPIC + '/' + device_path + _k + '/all',
                                {HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                                 HEADER_NAME_DATE: now}, device_dict)
                        for sub in dev_list[_k][dev_list[_k].keys()[0]]:
                            for k, val in _data.items():
                                if k.startswith(sub):
                                    pub_k = k[len(sub):]
                                    sub_dev.update({pub_k.split('_')[1]: val})
                                    cur_top = (''.join([BASETOPIC, '/',
                                                        device_path,
                                                        _k, '/', sub, '/',
                                                        pub_k.split('_')[1]]))
                                    self.publish_json(
                                        cur_top,
                                        {HEADER_NAME_CONTENT_TYPE:
                                            MIME_PLAIN_TEXT,
                                         HEADER_NAME_DATE: now}, val)
                                    # device_dict = jsonapi.dumps(device_dict)
                            if sub_dev:
                                topic = (''.join([BASETOPIC, '/', device_path,
                                                  _k, '/', sub, '/all']))
                                self.publish_json(
                                    topic,
                                    {HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                                     HEADER_NAME_DATE: now}, sub_dev)
                                sub_dev = {}
                        device_dict = {}
                else:
                    self._src_file_handle.close()
            else:
                self.publish_json(
                    'heartbeat/DataPublisher',
                    {
                        'AgentID': self._agent_id,
                        HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                        HEADER_NAME_DATE: now,
                    },
                    now)

        @matching.match_regex(topics.ACTUATOR_SET() + '/(.+)')
        def handle_set(self, topic, headers, message, match):
            '''Respond to ACTUATOR_SET topic.'''
            self._log.info('set actuator')
            point = match.group(1)
            _, _, _, point_name = point.rsplit('/', 4)
            requester = headers.get('requesterID')
            headers = self.get_headers(requester)
            value = jsonapi.loads(message[0])
            value_path = topic.replace('actuator/set', '')
            self.push_result_topic_pair(point_name, headers, value_path, value)

        @matching.match_exact(topics.ACTUATOR_SCHEDULE_REQUEST())
        def handle_schedule_request(self, topic, headers, message, match):
            '''Handle device schedule request.'''
            self._log.info('request received')
            request_type = headers.get('type')
            now = datetime.datetime.now()

            if request_type == SCHEDULE_ACTION_NEW:
                self.handle_new(headers, message)
            elif request_type == SCHEDULE_ACTION_CANCEL:
                self.handle_cancel(headers, now)
            else:
                self._log.debug('handle-schedule_request, invalid request')
                self.publish_json(topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                  {'result': SCHEDULE_RESPONSE_FAILURE,
                                   'data': {},
                                   'info': 'INVALID_REQUEST_TYPE'})

        def handle_new(self, headers, message):
            '''Send schedule request response.'''
            self._log.info('handle new schedule request')
            requester = headers.get('requesterID')
            self.task_id = headers.get('taskID')
            # priority = headers.get('priority')
            requests = []
            try:
                requests = jsonapi.loads(message[0])
                requests = requests[0]
            except (ValueError, IndexError) as ex:
                self._log.info('error, message not in expected format (json)')
                self._log.error('bad request: {request}, {error}'
                                .format(request=requests, error=str(ex)))
                requests = []
            _, start, end = requests
            self.start_time = parser.parse(start, fuzzy=True)
            self.end_time = parser.parse(end, fuzzy=True)
            event = sched.Event(self.announce, args=[requests, requester])
            self.scheduled_event = event
            self.schedule(self.start_time, event)
            topic = topics.ACTUATOR_SCHEDULE_RESULT()
            headers = self.get_headers(requester, task_id=self.task_id)
            headers['type'] = SCHEDULE_ACTION_NEW
            self.publish_json(topic, headers,
                              {
                                  'result': 'SUCCESS',
                                  'data': 'NONE',
                                  'info': 'NONE'
                              })

        def handle_cancel(self, headers, now):
            '''Handle schedule request cancel.'''
            task_id = headers.get('taskID')

            success = SCHEDULE_RESPONSE_SUCCESS
            self.scheduled_event.cancel()
            topic = topics.ACTUATOR_SCHEDULE_RESULT()
            self.publish_json(topic, headers, {'result': success,
                                               'info': task_id,
                                               'data': {}})

        def get_headers(self, requester, time=None, task_id=None):
            '''Construct headers for responses to
            schedule requests and device sets.
            '''
            headers = {}
            if time is not None:
                headers['time'] = time
            else:
                headers = {'time': str(datetime.datetime.utcnow())}
            if requester is not None:
                headers['requesterID'] = requester
            if task_id is not None:
                headers['taskID'] = task_id
            return headers

        def push_result_topic_pair(self, point, headers, value_path, *args):
            '''Send set success response.'''
            self.publish_json(topics.ACTUATOR_VALUE(point=point, **value_path),
                              headers, *args)

        def announce(self, device_path, requester):
            '''Emulate Actuator agent schedule announce.'''
            self._log.info('announce')
            now = datetime.datetime.now()
            header = self.get_headers(requester,
                                      time=str(now), task_id=self.task_id)
            header['window'] = str(self.end_time - now)
            topic = topics.ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}',
                                                                  device_path)
            self.publish_json(topic, header, {})
            next_time = now + datetime.timedelta(seconds=60)
            event = sched.Event(self.announce)
            self.scheduled_event = event
            self.schedule(next_time, event)

    Agent.__name__ = 'DataPub'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(DataPub,
                       description='Data publisher',
                       argv=argv)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
