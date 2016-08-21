import logging

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '0.1'


class AlertAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(AlertAgent, self).__init__(**kwargs)
        self.topic_wait_time = utils.load_config(config_path)
        self.topic_ttl = {}

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        for topic, seconds in self.topic_wait_time.iteritems():
            _log.debug("Expecting publish to {} every {} seconds".format(topic, seconds))
            self.topic_ttl[topic] = seconds
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self.reset_time)

    def reset_time(self, peer, sender, bus, topic, headers, message):
        self.topic_ttl[topic] = self.topic_wait_time[topic]

    @Core.periodic(1)
    def decrement_ttl(self):
        for topic in self.topic_wait_time.iterkeys():
            self.topic_ttl[topic] -= 1
            if self.topic_ttl[topic] == 0:
                status = Status.build(STATUS_BAD,
                                      context="{} not published within time limit".format(topic))
                self.vip.health.send_alert(topic, status)


def main():
    utils.vip_main(AlertAgent)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
