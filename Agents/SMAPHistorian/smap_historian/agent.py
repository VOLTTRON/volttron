# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
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


import datetime
import logging
import requests
import sys
import uuid

from volttron.platform.agent.base_historian import BaseHistorianAgent
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import topics, headers as headers_mod
from zmq.utils import jsonapi
import settings


from smap import driver
from smap.core import SmapException
from smap.util import periodicSequentialCall


utils.setup_logging()
_log = logging.getLogger(__name__)
from pprint import pprint


def SMAPHistorianAgent(config_path, **kwargs):
    '''
    There is a potential for conflict if multiple historians are writing to
    the same sMAP Archiver. If historians create paths in the same parent 
    they could create duplicates. This agent maintains a local understanding of 
    topic in sMAP and will not know that another historian added a topic.
    If another historian creates: "campus/building/device/point1" that point 
    will not be in the local dictionary and this agent will create it with another 
    uuid.
    '''
    _config = utils.load_config(config_path)
    _path_uuids = {}

    class Agent(BaseHistorianAgent):
        '''This is a simple example of a historian agent that writes data
        to an sMAP historian. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        '''
        
        topic_list = []
        uuid_list = []
        
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
            

            print(len(to_publish_list))
            print(to_publish_list[0])
            #print(to_publish_list)
            
            # add items to global topic and uuid lists if they don't exist
            for item in to_publish_list:
                if 'topic' not in item.keys():
                    _log.error('topic or uuid not found in {}'.format(item))
                    continue
                if 'uuid' not in item.keys():
                    #TODO if the topic does not exist in smap, add to smap here
                    # create a uuid
                    payload = {'uuid': str(uuid.uuid4()), 'topic': item['topic']}
                    response = requests.post("{url}/backend/add/LEq1cEGc04RtcKX6riiX7eaML8Z82xEgQrp7".format(url=_config.get('archiver_url')), data=jsonapi.dumps(payload))
                    
                    _log.debug('Adding topic to smap: {}'.format(item['topic']))
                    self.topic_list.append(item['topic'])
                    self.uuid_list.append('a uuid here') #item['uuid'])
                    continue
            
            
            # check for empty list
            if (len(self.topic_list) == 0) or (len(self.uuid_list) == 0):
                raise ValueError('missing topic list or uuid list')
                return
            
            
            # format json string for request
            # Uuid string format:
            # uuid_data = 'uuid: "{}"'.format()
            
            testdata = {
  "/thing/stuff" : {
    "Metadata" : {
      "SourceName" : "MyTest",
      "Location" : { "City" : "Berkeley" }
    },
    "Properties": {
      "Timezone": "America/Los_Angeles",
      "UnitofMeasure": "Watt",
      "ReadingType": "double"
    },
    "Readings" : [[1351043674000, 0], [1351043675000, 1]],
    "uuid" : "f785849c-e3bf-11e4-afe2-080027b06a49"
  }
}
            
            
            
            #self.report_all_published()
#             c = self.conn.cursor()
#             print 'Publish info'
            for x in to_publish_list[:10]:
                 ts = x['timestamp']
                 topic = x['topic']
                 value = x['value']
                 
            # if topic does not exist
                # create that topic
            # else, push to that topic
#                 
#                 topic_id = self.topics.get(topic)
#                 
#                 if topic_id is None:
#                     c.execute('''INSERT INTO topics values (?,?)''', (None, topic))
#                     c.execute('''SELECT last_insert_rowid()''')
#                     row = c.fetchone()
#                     topic_id = row[0]
#                     self.topics[topic] = topic_id
#                 
#                 c.execute('''INSERT OR REPLACE INTO data values(?, ?, ?)''', 
#                           (ts,topic_id,jsonapi.dumps(value)))
#                 
#                 self.report_published(x)
#                 pprint(x)
#             print 'count:', len(to_publish_list)
#             
#             self.conn.commit()
#             c.close()            
        
        def historian_setup(self):
            #reset paths in case we ever use this to dynamically switch Archivers
            self._path_uuids = {}
            # Fetch existing paths
            source = _config["source"]
            archiver_url = _config["archiver_url"]
            payload = ('select uuid where Metadata/SourceName="{source}"'.format(source=source))
            
            r = requests.post("{url}/backend/api/query".format(url=archiver_url), data=payload)
            print(r)
            print(r.text)
            
            # get dictionary of response
            response = jsonapi.loads(r.text)
            for path in response:
                 self._path_uuids[path["Path"]] = path["uuid"]
                 
                 
            # get list of topics
            # if topic elements to be pushed are in the topics list, we're good
            # else, we need to create the missing path elements and assign uuids
             
            

#[{"Path": "/thing/stuff", "uuid": "f785849c-e3bf-11e4-afe2-080027b06a49"}, {"Path": "/sensor0", "uuid": "a9e2aec8-e3be-11e4-afe2-080027b06a49"}]


#             self.topics={}
#             self.conn = sqlite3.connect('data.sqlite', 
#                                          detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
#         
#             c = self.conn.cursor()
#             c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='data';")
#             
#             if c.fetchone() is None:
#                 self.conn.execute('''CREATE TABLE data 
#                                     (ts timestamp NOT NULL,
#                                      topic_id INTEGER NOT NULL, 
#                                      value_string TEXT NOT NULL, 
#                                      UNIQUE(ts, topic_id))''')
#             
#             
#             c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='topics';")
#         
#             if c.fetchone() is None:   
#                 self.conn.execute('''CREATE TABLE topics 
#                                             (topic_id INTEGER PRIMARY KEY, 
#                                              topic_name TEXT NOT NULL,
#                                              UNIQUE(topic_name))''')
#                 
#             else:
#                 c.execute("SELECT * FROM topics")
#                 for row in c:
#                     self.topics[row[1]] = row[0]
#         
#             c.close()
#             self.conn.commit()
        
    Agent.__name__ = 'SMAPHistorianAgent'
    return Agent(**kwargs)
            
    
    
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.default_main(SMAPHistorianAgent,
                           description='Historian agent that saves a history to an SMAP Archiver.',
                           argv=argv)
    except Exception as e:
        print e
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
