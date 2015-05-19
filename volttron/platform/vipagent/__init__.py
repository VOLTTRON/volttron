
from __future__ import absolute_import, print_function

from . import core, subsystems


class Agent(object):
    def __init__(self, identity=None, address=None, context=None, **kwargs):
        super(Agent, self).__init__(**kwargs)
        self.core = core.Core(
            identity=identity, address=address, context=context)
        self.ping = subsystems.Ping(self.core)
        self.rpc = subsystems.RPC(self.core, self)
        self.hello = subsystems.Hello(self.core)
        self.pubsub = subsystems.PubSub(self.core, self.rpc)
        self.channel = subsystems.Channel(self.core)

    @subsystems.RPC.export
    def hello(self, name):
        return 'hi, ' + name
