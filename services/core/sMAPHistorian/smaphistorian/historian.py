# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of the FreeBSD Project.
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

#}}}

import calendar
import datetime
import logging
import requests
import sys
import uuid
import time

import pytz
from pytz import timezone

from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import topics, headers as headers_mod
from zmq.utils import jsonapi

from smap import driver
from smap.core import SmapException
from smap.util import periodicSequentialCall

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'


def SMAPHistorianAgent(config_path, **kwargs):
    '''
    There is a potential for conflict if multiple historians are writing to
    the same sMAP Archiver. If historians create paths in the same parent
    they could create duplicates. This agent maintains a local understanding of
    topic in sMAP and will not know that another historian added a topic.
    If another historian creates: "campus/building/device/point1" that point
    will not be in the local dictionary and this agent will create it with
    another uuid.
    '''
    _config = utils.load_config(config_path)
    _backend_url = '{}/backend'.format(_config['archiver_url'])
    _add_url = '{backend_url}/add/{key}'.format(backend_url=_backend_url,
                                                key=_config.get('key'))

    class Agent(BaseHistorian):
        '''This is a simple example of a historian agent that writes data
        to an sMAP historian. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        '''

        def publish_to_historian(self, to_publish_list):
            '''
            to_publish_list is a list of dictionaries that have the following
            keys:

                'timestamp' - a datetime of the timestamp
                'value' - a decimal or integer. ex: -39.9900016784668
                'topic' - a unicode string representing the topic
                'source' - a unicode string representing the source, typically
                            'scrape'
                'id' - an integer
                'meta' - a dictionary of metadata
                   meta dictionary keys are (unicode strings):
                       'units' - ex: 'F'
                       'type' - ex: 'float'
                       'tz' - ex: 'America/Los_Angeles'
            '''
            success = []
            failure = []

            publish = {}

            # add items to global topic and uuid lists if they don't exist
            for item in to_publish_list:
                
                if 'topic' not in item.keys():
                    _log.error('topic or uuid not found in {}'.format(item))
                    continue

                topic = item['topic']
                # in order for things to show up in smap they need to have
                # a rooted topic.
                if topic[0] != '/':
                    topic = '/'+topic

                meta = item['meta']

                if meta['type'] not in ('float', 'double', 'boolean', 'integer', 'int'):
                    _log.warn('Ignoring point due to invalid type: {}'
                              .format(item))

                    # Clear the bad point from the publish list so it doesn't
                    # stay around.
                    self.report_handled(item)
                    continue

                # Auto convert bools to ints for smap.
                if meta['type'] == 'boolean':
                    item['value'] = int(item['value'])
                    meta['type'] = 'integer'
                # handle int as well as integer types.
                if meta['type'] == 'int':
                    meta['type'] = 'integer'

                item_uuid = self._topic_to_uuid.get(topic, None)
                if item_uuid is None:
                    item_uuid = str(uuid.uuid4())
                    # just in case of duplicate
                    while item_uuid in self._topic_to_uuid.values():
                        item_uuid = str(uuid.uuid4())


                # protect data if SourceName already present
                if 'SourceName' in meta.keys():
                    meta['OldSourceName'] = meta['SourceName']

                meta['SourceName'] = _config['source']
                # Default to utc.               
                if item['source'] in ('scrape', 'analysis'):
                    if ('timestamp' not in item or 'tz' not in meta):
                        _log.error('Invalid timestamp specified for item: {}'
                               .format(item))
                        self.report_handled(item)
                        continue
                    utc = item['timestamp']
                    mytz = timezone(meta['tz'])
                    mydt = utc.astimezone(mytz)


                if item['source'] == 'log':
                    mydt = item['timestamp']
                    if 'tz' not in meta:
                        
                        if mydt.tzinfo is None:
                            mydt = mydt.astimezone(pytz.UTC)
                        meta['tz'] = str(mydt.tzinfo)
                    else:
                       mytz = timezone(meta['tz'])
                       mydt = mydt.astimezone(pytz.UTC)
#                        mydt = mydt.astimezone(mytz)
                #Smap wants UTC. Take date to UTC and we should have saved original TZ
                

                        
                
            #    utc = item['timestamp']
            #    mytz = timezone(meta['tz'])
            #    mydt = utc.astimezone(mytz)
#                 meta.pop('tz',None)
                publish[topic] = \
                {'Metadata': meta,
                 'Properties': {'Timezone': meta['tz'],
                                'UnitofMeasure': meta['units'],
                                'ReadingType': meta['type']
                               },
                 'Readings': [[calendar.timegm(mydt.utctimetuple())*1000, item['value']]],
                 'uuid': item_uuid
                }
                
            response = requests.post(_add_url, data=jsonapi.dumps(publish),verify=False)
            
            if response.ok:
                for topic in publish.keys():
                    if topic not in self._topic_to_uuid.keys():
                        _log.info('Adding new topic: {}'.format(topic))
                        self._topic_to_uuid[topic] = publish[topic]['uuid']

                self.report_all_handled()
            else:
                _log.error('Invalid response from server for {}'
                           .format(jsonapi.dumps(publish)))

        def historian_setup(self):
            # reset paths in case we ever use this to dynamically switch
            # Archivers
            self._topic_to_uuid = {}
            # Fetch existing paths
            source = _config["source"]
            archiver_url = _config["archiver_url"]
            payload = ('select uuid where Metadata/SourceName="{source}"'
                       .format(source=source))

            resp = requests.post("{url}/backend/api/query?key={key}"
                                 .format(url=archiver_url, key=_config['key']), data=payload,verify=False)

            # get dictionary of response
            response = jsonapi.loads(resp.text)
            for path in response:
                self._topic_to_uuid[path["Path"]] = path["uuid"]

    Agent.__name__ = 'SMAPHistorianAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(SMAPHistorianAgent)
    except Exception as e:
        _log.error(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
