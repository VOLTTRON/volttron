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


import sys
import datetime

from volttron.lite.agent import BaseAgent, PublishMixin
from volttron.lite.agent import utils, matching
from volttron.lite.agent.utils import jsonapi


def GridlabdAgent(config_path, **kwargs):
    print "Loading config file"
    config = utils.load_config(config_path)
    agent_id = config['agentid']

    def get_config(name):
        try:
            value = kwargs.pop(name)
            return value
        except KeyError:
            return config.get(name, '')

    class Agent(PublishMixin, BaseAgent):
        """"Demonstration agent for Gridlabd communications"""
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)

        def setup(self):
            self.current_reading = {'Insolation': 10.0, 'Temperature': 20.0}
            super(Agent, self).setup()

        # Write function to handle Gridlabd messages
        @matching.match_exact('gridlabd/request')
        def handle_gridlabd_msg(self, topic, headers, message, match):
            print >> sys.stderr, message[0]

            gldmsg = jsonapi.loads(message[0])
            if gldmsg['method'] == 'input':
                self.input_schema = gldmsg['schema']
                self.publish_schema_response(gldmsg['method'], gldmsg['id'])
            elif gldmsg['method'] == 'output':
                self.output_schema = gldmsg['schema']
                self.publish_schema_response(gldmsg['method'], gldmsg['id'])
            elif gldmsg['method'] == 'start':
                self.publish_start_response(gldmsg['id'])
            elif gldmsg['method'] == 'sync':
                self.publish_sync_response(gldmsg['id'])
            elif gldmsg['method'] == 'term':
                self.publish_term_response(gldmsg['id'])

        def publish_schema_response(self, schema_type, id):
            print >> sys.stderr, 'publishing schema response'
            response = {'result': schema_type}
            response['id'] = id
            self.publish_json('gridlabd/response', {'agentID': agent_id}, response)

        def publish_start_response(self, id):
            # msg = {'result': 'start', 'data': {'x0': 0.0, 'x1': 1.0, 'clock': datetime.datetime.today().isoformat(' ')}}
            msg = self.build_response('start')
            msg['id'] = id
            self.publish_json('gridlabd/response', {'agentID': agent_id}, msg)

        def publish_sync_response(self, id):
            # msg = {'result': 'sync', 'data': {'x0': 0.0, 'x1': 1.0, 'clock': datetime.datetime.today().isoformat(' ')}}
            msg = self.build_response('sync')
            msg['id'] = id
            self.publish_json('gridlabd/response', {'agentID': agent_id}, msg)

        def publish_term_response(self, id):
            # msg = {'result': 'term', 'data': {'x0': 0.0, 'x1': 1.0, 'clock': datetime.datetime.today().isoformat(' ')}}
            msg = self.build_response('term')
            msg['id'] = id
            self.publish_json('gridlabd/response', {'agentID': agent_id}, msg)

        def build_response(self, method):
            msg = {'result': method, 'data': {'x0': 0.0, 'x1': 1.0, 'clock': datetime.datetime.today().isoformat(' ')}}
            data = {'clock': datetime.datetime.today().isoformat(' ')}
            for label in self.input_schema.keys():
                if(label in self.current_reading):
                    data[label] = self.current_reading[label]
            msg['data'] = data
            return msg

        # Write function to handle WeatherAgent messages
        @matching.match_exact('weather/temperature/temp_f')
        def handle_temp_msg(self, topic, headers, message, match):
            self.current_reading['Temperature'] = float(message[0])
            self.temperature = float(message[0])

            print >> sys.stderr, self.current_reading

        @matching.match_exact('weather/cloud_cover/solarradiation')
        def handle_solar_msg(self, topic, headers, message, match):
            try:
                self.current_reading['Insolation'] = float(message[0])
                self.solar_radiation = float(message[0])
            except ValueError:
                self.current_reading['Insolation'] = 0.0

            print >> sys.stderr, self.current_reading

    Agent.__name__ = 'GridlabdWeatherAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(GridlabdAgent,
                       description='Gridlabd link agent',
                       argv=argv)

if __name__ == '__main__':
    main()
