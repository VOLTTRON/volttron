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

#}}}

import sys
import requests
from requests import ConnectionError

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils
from volttron.platform.agent.utils import jsonapi
from volttron.platform.agent.matching import match_all, match_start
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics

import settings

__version__ = '0.1'

def build_paths(path, result_data, timeseries, delim='/'):
    p = ''
    last_found = result_data
    for pathelement in path.split(delim):
        if pathelement in last_found:
            last_found = last_found[pathelement]
        else:
            last_found[pathelement] = {}
            last_found = last_found[pathelement]
    timeseries[path] = last_found
    return (result_data, timeseries)


def ArchiverAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            value = kwargs.pop(name)
        except KeyError:
            return config[name]

    agent_id = get_config('agentid')
    source_name = get_config('source_name')
    archiver_url = get_config('archiver_url')

    class Agent(PublishMixin, BaseAgent):
        def __init__(self, **kwargs):
                super(Agent, self).__init__(**kwargs)
    #         self.subscribe(settings.REQUEST_TOPIC, self.handle_request)

        @match_start(topics.BASE_ARCHIVER_REQUEST)
        def handle_request(self, topic, headers, message, matched):
            # Path is part of topic.
            path = topic[len(topics.BASE_ARCHIVER_REQUEST):]

            # Range is message.  It will either be "start"-"end" or 1h, 1d,
            # etc... from now
            range_str = message[0]
            source = headers.get('SourceName', source_name)

            # Find UUID for path
            payload = ('select uuid where Metadata/SourceName="{}" '
                       'and Path="{}"'.format(source, path))

            done = False
            retries = 0
            uuid_list = []
            while not done and retries <= 5:
                # TODO: Need to do some error handling here!
                try:
                    r = requests.post(archiver_url, data=payload)
                    if r.status_code == 200:
                        # Data should be a list of dictionaries at this point in time
                        uuid_list = jsonapi.loads(r.text)
                        done = True
                    else:
                        print str(retries) + ": " + str(r.status_code) + ": " + payload
                        retries += 1
                except ValueError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1
                except ConnectionError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1
                    #Can get a 503 network busy
                    #TODO: Respond with error

            # TODO: Need to do some error handling here!

            # Data should be a list of dictionaries at this point in time
            if not uuid_list:
                # TODO: log this error
                return
            payload_template = "select data in {} where {{}}".format(range_str)

            uuid_clause = "uuid='{}'".format(uuid_list[0]['uuid'])
            for stream in uuid_list[1:]:
                uuid_clause.append(" or uuid='{}'".format(stream['uuid']))
            payload = payload_template.format(uuid_clause)

            full_data = None
            tries = 0
            done = False
            while not done and retries <= 5:
            # TODO: Need to do some error handling here!
                try:
                    r = requests.post(archiver_url, data=payload)
                    if 'Syntax error' in r.text:
                        # TODO Log this error
                        self.publish(topics.BASE_ARCHIVER_RESPONSE + path, None, 'Syntax error in date range')
                        return

            # Request data for UUID in range
            #[{"uuid": "5b94d5ed-1e1d-51cf-a6d8-afae5c055292", "Readings": [[1368750281000.0, 75.5], [1368750341000.0, 75.5], ...
                    done = True
                except ValueError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1
                except ConnectionError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1

            if 'Syntax error' in r.text:
                # TODO Log this error
                self.publish(topics.BASE_ARCHIVER_RESPONSE + path,
                             None, 'Syntax error in date range')
                return

            # Request data for UUID in range
            #[{"uuid": "5b94d5ed-1e1d-51cf-a6d8-afae5c055292",
            # "Readings": [[1368750281000.0, 75.5], [1368750341000.0, 75.5], ...
            full_data = jsonapi.loads(r.text)
            data = full_data[0].get('Readings', [])
            pub_headers = {headers_mod.FROM: 'ArchiverAgent',
                           headers_mod.TO: headers[headers_mod.FROM] if headers_mod.FROM in headers else 'Unknown'}
            if data > 0:
                # There was data for this stream in the specified range.
                # Convert data to json and publish
                self.publish_json(topics.BASE_ARCHIVER_RESPONSE + path, pub_headers, data)

        @match_start(topics.BASE_ARCHIVER_FULL_REQUEST)
        def handle_full_request(self, topic, headers, message, matched):
            # Path is part of topic.
            path = topic[len(topics.BASE_ARCHIVER_FULL_REQUEST):]
            result_layout = headers.get('ResultLayout', 'HIERARCHICAL')

            # Range is message.  It will either be "start"-"end" or 1h, 1d,
            # etc... from now
            range_str = message[0]
            source = headers.get('SourceName', source_name)

            # Find UUID for path
            payload = ('select * where Metadata/SourceName="{}" '
                       'and Path~"{}"'.format(source, path))

            done = False
            retries = 0
            while not done and retries <= 5:
                # TODO: Need to do some error handling here!
                try:
                    r = requests.post(archiver_url, data=payload)
                    if r.status_code == 200:
                        # Data should be a list of dictionaries at this point in time
                        uuid_list = jsonapi.loads(r.text)
                        done = True
                    else:
                        print str(retries) + ": " + str(r.status_code) + ": " + payload
                        retries += 1
                except ValueError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1
                except ConnectionError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1
                    #Can get a 503 network busy
                    #TODO: Respond with error

            # TODO: Need to do some error handling here!

            # Data should be a list of dictionaries at this point in time
            if not uuid_list:
                # TODO: log this error
                return

            timeseries = {}
            hierarchichal = {}

            payload_template = "select data in {} where {{}}".format(range_str)
            if len(uuid_list) == 0:
                return

            uuid_clause = "uuid='{}'".format(uuid_list[0]['uuid'])
            for stream in uuid_list[1:]:
                uuid_clause += (" or uuid='{}'".format(stream['uuid']))
            payload = payload_template.format(uuid_clause)
#
            # Request data and store Readings in timeseries[path]
            full_data = None
            tries = 0
            done = False
            while not done and retries <= 5:
            # TODO: Need to do some error handling here!
                try:
                    r = requests.post(archiver_url, data=payload)
                    if 'Syntax error' in r.text:
                        # TODO Log this error
                        self.publish(topics.BASE_ARCHIVER_RESPONSE + path, None, 'Syntax error in date range')
                        return

            # Request data for UUID in range
            #[{"uuid": "5b94d5ed-1e1d-51cf-a6d8-afae5c055292", "Readings": [[1368750281000.0, 75.5], [1368750341000.0, 75.5], ...
                    done = True
                except ValueError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1
                except ConnectionError as e:
                    print str(retries) + ": " + str(e) + ": " + payload
                    retries += 1

            if 'Syntax error' in r.text:
                # TODO Log this error
                self.publish(topics.BASE_ARCHIVER_RESPONSE + path,
                             None, 'Syntax error in date range')
                return

            # Request data for UUID in range
            #[{"uuid": "5b94d5ed-1e1d-51cf-a6d8-afae5c055292",
            # "Readings": [[1368750281000.0, 75.5], [1368750341000.0, 75.5], ...

            full_data = jsonapi.loads(r.text)
            
            reading_dict = {}
            
            for readings in full_data:
                reading_dict[readings['uuid']] = readings.get('Readings', [])
            
            for stream in uuid_list:
#                 uuid_clause += (" or uuid='{}'".format(stream['uuid']))
                path = stream['Path']
                print stream
                (hierarchichal, timeseries) = build_paths(path, hierarchichal, timeseries)
                timeseries[path]['uuid'] = stream['uuid']
                timeseries[path]['Properties'] = stream['Properties']
                timeseries[path]['Path'] = path
                timeseries[path]['Readings'] = reading_dict[stream['uuid']]
                                 
            pub_headers = {headers_mod.FROM: 'ArchiverAgent',
                           headers_mod.TO: headers[headers_mod.FROM] if headers_mod.FROM in headers else 'Unknown'}

            if result_layout == 'FLAT':
                self.publish_json(topics.BASE_ARCHIVER_RESPONSE + path, pub_headers, timeseries)
            else:
                self.publish_json(topics.BASE_ARCHIVER_RESPONSE + path, pub_headers, hierarchichal)

    Agent.__name__ = 'ArchiverAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(ArchiverAgent,
                       description='VOLTTRON platform™ archiver agent',
                       argv=argv)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        pass
