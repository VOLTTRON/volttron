import sys
import json
import logging
import datetime

from volttron.lite.agent import BaseAgent, PublishMixin, periodic
from volttron.lite.agent import utils, matching
from volttron.lite.agent.utils import jsonapi
from volttron.lite.messaging import headers as headers_mod

from json_link import json_link
from json_link.xchg import raw_xchg
from json_link.faults import fault_inject

from pkg_resources import resource_string


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
