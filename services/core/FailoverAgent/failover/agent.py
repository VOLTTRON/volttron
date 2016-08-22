from __future__ import absolute_import

import logging
import sys
import gevent

from gevent.subprocess import Popen

from volttron.platform.vip.agent import Agent, Core, PubSub
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger()


class FailoverAgent(Agent):

    def __init__(self, config_path, **kwargs):
        super(FailoverAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)

        for k, v in config.iteritems():
            setattr(self, k, v)

        self.vc_timeout = 0
        self.remote_timeout = 0

        self._state = False, False
        self._state_machine = getattr(self, self.agent_id + '_state_machine')

        heartbeat = Agent(address=self.remote_vip,
                          heartbeat_autostart=True,
                          heartbeat_period=self.heartbeat_period)
        heartbeat.__class__.__name__ = self.agent_id
        event = gevent.event.Event()
        gevent.spawn(heartbeat.core.run, event)
        event.wait()
        self.heartbeat = heartbeat

    @PubSub.subscribe('pubsub', 'heartbeat')
    def on_match(self, peer, sender, bus, topic, headers, message):
        if topic.startswith('heartbeat/VolttronCentralAgent'):
            self.vc_timeout = self.timeout
        elif topic.startswith('heartbeat/' + self.remote_id):
            self.remote_timeout = self.timeout

    @Core.periodic(1)
    def check_pulse(self):
        self.vc_timeout -= 1
        self.remote_timeout -= 1

        vc_is_up = self.vc_timeout > 0
        remote_is_up = self.remote_timeout > 0
        current_state = remote_is_up, vc_is_up

        if current_state != self._state:
            self._state_machine(remote_is_up, vc_is_up)
            self._state = current_state

    def _agent_control(self, command):
        p = Popen(['volttron-ctl', command, '--tag', self.volttron_ctl_tag])
        p.wait()

    def primary_state_machine(self, secondary_is_up, vc_is_up):
        if secondary_is_up or vc_is_up:
            self._agent_control('start')
        else:
            self._agent_control('stop')

    def secondary_state_machine(self, primary_is_up, vc_is_up):
        if not primary_is_up and vc_is_up:
            pass # verify and start master
        else:
            self._agent_control('stop')

    def simple_primary_state_machine(self, secondary_is_up, vc_is_up):
        self._agent_control('start')

    def simple_secondary_state_machine(self, primary_is_up, vc_is_up):
        if primary_is_up:
            self._agent_control('stop')
        else:
            self._agent_control('start')


def main(argv=sys.argv):
    try:
        utils.vip_main(FailoverAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    sys.exit(main())
