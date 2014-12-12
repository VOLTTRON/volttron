# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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
#}}}
import os
import datetime
import sys
import json
import settings
import logging
from dateutil import parser
from zmq.utils import jsonapi

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import matching, utils, green, sched
from volttron.platform.agent.utils import  load_config
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.agent.sched import EventWithTime
from volttron.platform.agent.matching import match_all
from volttron.platform.messaging import headers as headers_mod

MIME_PLAIN_TEXT = headers_mod.CONTENT_TYPE.PLAIN_TEXT
HEADER_NAME_DATE = headers_mod.DATE
HEADER_NAME_CONTENT_TYPE = headers_mod.CONTENT_TYPE
VALUE_RESPONSE_PREFIX = topics.ACTUATOR_VALUE()
ERROR_RESPONSE_PREFIX = topics.ACTUATOR_ERROR()
SCHEDULE_RESPONSE_FAILURE = 'FAILURE'
SCHEDULE_ACTION_NEW = 'NEW_SCHEDULE'

   
def DataPub(**kwargs):
    rtu_path = settings.rtu_path
    campus, building, unit = rtu_path.rsplit('/', 3)
    rtu_path = {'campus': campus, 'building': building, 'unit': unit}

    class Agent(PublishMixin, BaseAgent):
        '''Simulate real device.  Publish csv data to message bus.
        
        Configuration consists of csv file and device path (campus/building/device)
        '''
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            path = os.path.abspath(settings.source_file)
            print path
            self._src_file_handle = open(path)
            header_line = self._src_file_handle.readline().strip()
            self._headers = header_line.split(',')
            self.end_time = None
            self.start_time = None
            self.task_id = None
            utils.setup_logging()
            self._log = logging.getLogger(__name__)
            logging.basicConfig(level=logging.debug,
                                format='%(asctime)s   %(levelname)-8s %(message)s',
                                datefmt='%m-%d-%y %H:%M:%S')

        def setup(self):
            '''This function is called imediately after initialization'''
            super(Agent, self).setup()
            self._agent_id = settings.publisherid

        @periodic(settings.check_4_new_data_time)
        def publish_data_or_heartbeat(self):
            published_data = {}
            now = datetime.datetime.now().isoformat(' ')
            if not self._src_file_handle.closed:
                line = self._src_file_handle.readline()
                line = line.strip()
                data = line.split(',')
                if (line):
                    # Create 'all' message
                    for i in xrange(0, len(self._headers)):
                        published_data[self._headers[i]] = data[i]
                    all_data = json.dumps(published_data)
                    print all_data
                    # Pushing out the data
                    self.publish(topics.DEVICES_VALUE(point='all', **rtu_path),
                                 {HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                                  HEADER_NAME_DATE: now}, all_data)
                else:
                    self._src_file_handle.close()
            else:  # file is closed -> publish heartbeat
                self.publish('heartbeat/DataPublisher',
                             {
                                 'AgentID': self._agent_id,
                                 HEADER_NAME_CONTENT_TYPE: MIME_PLAIN_TEXT,
                                 HEADER_NAME_DATE: now,
                             }, now)

        @matching.match_regex(topics.ACTUATOR_SET() + '/(.+)')
        def handle_set(self, topic, headers, message, match):
            print 'set actuator'
            point = match.group(1)
            discard1, discard2, discard3, point_name = point.rsplit('/', 4)
            requester = headers.get('requesterID')
            headers = self.get_headers(requester)
            value = jsonapi.loads(message[0])
            self.push_result_topic_pair(point_name, headers, value)

        @matching.match_exact(topics.ACTUATOR_SCHEDULE_REQUEST())
        def handle_schedule_request(self, topic, headers, message, match):
            print 'request received'
            request_type = headers.get('type')
            now = datetime.datetime.now()

            if request_type == SCHEDULE_ACTION_NEW:
                self.handle_new(headers, message, now)
            else:
                self._log.debug('handle-schedule_request, invalid request type')
                self.publish_json(topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                  {
                    'result': SCHEDULE_RESPONSE_FAILURE,
                    'data': {},
                    'info': 'INVALID_REQUEST_TYPE'
                    })

        def handle_new(self, headers, message, now):
            print 'handle new'
            requester = headers.get('requesterID')
            self.task_id = headers.get('taskID')
            # priority = headers.get('priority')
            try:
                requests = jsonapi.loads(message[0])
                requests = requests[0]
            except (ValueError, IndexError) as ex:
                # Could be ValueError of JSONDecodeError depending
                # on if simples json was used.  JSONDecodeError
                # inherits from ValueError
                # We let the schedule manager tell us this is a bad request.
                self._log.error('bad request: {request}, {error}'
                                .format(request=requests, error=str(ex)))
                requests = []
            device, start, end = requests
            self.start_time = parser.parse(start, fuzzy=True)
            self.end_time = parser.parse(end, fuzzy=True)
            event = sched.Event(self.announce)
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

        def get_headers(self, requester, time=None, task_id=None):
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

        def push_result_topic_pair(self, point, headers, *args):
            self.publish_json(topics.ACTUATOR_VALUE(point=point, **rtu_path), headers, *args)

        def announce(self):
            print 'announce'
            now = datetime.datetime.now()
            header = self.get_headers(settings.agent_id, time=str(now), task_id=self.task_id)
            header['window'] = str(self.end_time - now)
            topic = topics.ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}', settings.device)
            self.publish_json(topic, header, {})
            next_time =  now + datetime.timedelta(seconds=60)

    Agent.__name__ = 'DataPub'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(DataPub,
                       description='Data publisher',
                       argv=argv)

if __name__ == '__main__':
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
