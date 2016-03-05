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
from __future__ import absolute_import, print_function

import datetime
import errno
import logging
import os, os.path
from pprint import pprint
import sqlite3
import sys
import uuid

import gevent
import requests
from requests import ConnectionError
from zmq.utils import jsonapi

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from twisted.spread.pb import respond

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'

def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    connection = config.get('connection');
    
    assert connection
    assert connection.get('type') == 'openeis'
    
    params = connection.get('params')
    assert params
    
    uri = params.get('uri')
    assert uri
       
    login = params.get('login')
    assert login

    password = params.get('password')
    assert password
    # Auth will get passed to the server through the requests python framework.
    auth = (login, password)
    
    datasets = config.get("dataset_definitions")
    assert datasets
    assert len(datasets) > 0
    
    # This allows us to switch the identity based upon the param in the config
    # file.
    identity = config.get('identity', None)
    if identity:
        kwargs['identity'] = identity
    headers = {'content-type': 'application/json'}
        
    class OpenEISHistorian(BaseHistorian):
        '''An OpenEIS historian which allows the publishing of dynamic.
        
        This historian publishes to an openeis instance with the following 
        example json payload:
        
        dataset_extension = {
            "dataset_id": dataset_id,
            "point_map": 
            {
                "New building/WholeBuildingPower": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",50.12], ["2/5/2014 10:10",48.54]],
                "New building/OutdoorAirTemperature": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",10.12], ["2/5/2014 10:10",48.54]]
            }
        }
        
        The dataset must exist on the openeis webserver.  The mapping (defined)
        in the configuration file must include both the input (from device)
        topic and output (openeis schema topic).  See openeis.historian.config
        for a full description of how those are specified in the coniguration
        file.
        
        This service will publish to server/api/datasets/append endpoint.
        '''
        
        def publish_to_historian(self, to_publish_list):
            _log.debug("publish_to_historian number of items: {}"
                       .format(len(to_publish_list)))
            
            #pprint(to_publish_list)
            dataset_uri = uri + "/api/datasets/append"
            
            # Build a paylooad for each of the points in each of the dataset
            # definitions.
            for dsk, dsv in datasets.items():
                ds_id = dsv["dataset_id"]
                ds_points = dsv['points'] #[unicode(p) for p in dsv['points']]
                ignore_unmapped = dsv.get('ignore_unmapped_points', 0) 
                
                point_map = {}
                try_publish = []
                for to_pub in to_publish_list:
                    for point in ds_points:                      
                        if to_pub['topic'] in point.keys():
                            try_publish.append(to_pub)
                            # gets the value of the sensor for publishing.
                            openeis_sensor = point[to_pub['topic']]
                            if not openeis_sensor in point_map:
                                point_map[openeis_sensor] = []
                                
                            point_map[openeis_sensor].append([to_pub['timestamp'],
                                                               to_pub['value']])
                        else:
                            if ignore_unmapped:
                                self.report_handled(to_pub)
                            else:
                                err = 'Point {topic} was not found in point map.' \
                                    .format(**to_pub)
                                _log.error(err)
                                
                    #pprint(point_map)
                        
                if len(point_map) > 0:
                    payload = { 'dataset_id': ds_id,
                               'point_map': point_map}
                    payload = jsonapi.dumps(payload, 
                                            default=datetime.datetime.isoformat)
                    try:
                        #resp = requests.post(login_uri, auth=auth)
                        resp = requests.put(dataset_uri, verify=False, headers=headers, 
                                            data=payload)
                        if resp.status_code == requests.codes.ok:                       
                            self.report_handled(try_publish)
                    except ConnectionError:
                        _log.error('Unable to connect to openeis at {}'.format(uri))
                        return
                        
                        
            '''
            Transform the to_publish_list into a dictionary like the following
            
            dataset_extension = {
                "dataset_id": dataset_id,
                "point_map": 
                {
                    "New building/WholeBuildingPower": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",50.12], ["2/5/2014 10:10",48.54]],
                    "New building/OutdoorAirTemperature": [["2/5/2014 10:00",48.78], ["2/5/2014 10:05",10.12], ["2/5/2014 10:10",48.54]]
                }
            }
            '''           

        def query_historian(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
            raise Exception('Please use Openeis for the query interface.')
            
        def historian_setup(self):
            # TODO Setup connection to openeis.
            pass

    OpenEISHistorian.__name__ = 'OpenEISHistorian'
    return OpenEISHistorian(**kwargs)



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(historian)
        #utils.default_main(historian,
        #                   description='Historian agent that saves a history to a sqlite db.',
        #                   argv=argv,
        #                   no_pub_sub_socket=True)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
