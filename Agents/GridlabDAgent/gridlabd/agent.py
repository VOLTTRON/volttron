import sys
import json
import logging

from volttron.lite.agent import BaseAgent, PublishMixin
from volttron.lite.agent import utils, matching
from volttron.lite.agent.utils import jsonapi
from volttron.lite.messaging import headers as headers_mod

from json_link import json_link
from json_link.xchg import raw_xchg
from json_link.faults import fault_inject

from pkg_resources import resource_string

utils.setup_logging()
_log = logging.getLogger(__name__)

# Variables that are only used for output to file for demo period
criteria_labels = ['NO_curtailing', 'deltaT_zone_delta', 'Room_rtu', 'Power_rtu', 'deltaT_zone_sp']
matrix_rowstring = "%20s\t%15.2f%19.2f%10.2f%11.2f%16.2f"
criteria_labelstring = "\t\t\t%15s%19s%10s%11s%16s"


class LoggerWriter:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        if message != '\n':
            self.logger.log(self.level, message)


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
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.description_dict = {'remote': "Gridlab-d_volttron_agent", 'version': '0.0.1'}
            self.msg_num = 0
            # link = raw_xchg.SlaveXchg(opt.host_addr, opt.port, opt.sock_type,
            #                      opt_raw=opt.raw,
            #                      opt_binary=opt.binary,
            #                      opt_header=(not opt.no_head),
            #                      timeout=opt.timeout)
            address = get_config('address')
            self.link = raw_xchg.SlaveXchg(address,  # Hostname
                                           raw_xchg.DEFAULT_UDP_PORT,  # Port
                                           raw_xchg.UDP,  # Connection type
                                           opt_raw=False,  # Raw
                                           opt_binary=False,  # Binary
                                           opt_header=True,  # No head
                                           timeout=json_link.DEFAULT_SLAVE_TIMESTEP/json_link.DEFAULT_DELAY_DIVISOR)

        def setup(self):
            super(Agent, self).setup()
            self.handle_gridlabd_link('gridlabd/some.glm/start', {}, {}, '')

        @matching.match_glob('gridlabd/*/start')
        def handle_gridlabd_link(self, topic, headers, message, match):
            # TODO: Get parameters from config file

            self.msg_received = False
            while not self.msg_received:
                self.link.setupXchg()

                try:
                    data = self.link.receive()
                except raw_xchg.RawXchgTimeoutError:
                    continue

                if data is None:
                    continue

                print >> sys.stderr, "data:", data

                data = json.loads(data)

                # check the method to handle the cases that this agent will deal with directly
                if(data['method'] == 'init'):
                    reply = {'params': self.description_dict, 'result': 'init'}
                    reply['id'] = 1  # data['id'] + 1
                    reply = jsonapi.dumps(reply)
                    print reply
                    self.link.send(reply)
                    continue
                elif(data['method'] == 'term'):
                    pass

                self.msg_received = True

                # Otherwise push the message out on the bus and let the agent on the other end handle it.
                self.publish_json('gridlabd/request', {'agentID': agent_id}, data)

                # TODO: remove this once the other agent is written
                # response = {'result': data['method']}
                # response['id'] = data['id'] + 1
                # response = json.dumps(response)
                # print >> sys.stderr, ">>>>>> Sending: " + response
                # self.link.send(response)

        @matching.match_start('gridlabd/response')
        def handle_gridlabd_send(self, topic, headers, message, match):
            '''Function handles the response being sent back to gridlabd from agent'''
            # Extract gridlabd compatible message from message parameter

            # Build up response object
            # Serialize to JSON
            # Send to gridlabd
            print >> sys.stderr, '==== response received, sending to gridlabd ===='
            self.link.send(message[0])
            self.handle_gridlabd_link('gridlabd/some.glm/start', {}, {}, '')

    Agent.__name__ = 'GridlabdAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(GridlabdAgent,
                       description='Gridlabd link agent',
                       argv=argv)


if __name__ == '__main__':
    main()
