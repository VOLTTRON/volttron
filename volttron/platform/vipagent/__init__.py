
from __future__ import absolute_import, print_function

from . import core as _core, subsystems


class Agent(object):
    class Subsystems(object):
        def __init__(self, owner, core):
            self.ping = subsystems.Ping(core)
            self.rpc = subsystems.RPC(core, owner)
            self.hello = subsystems.Hello(core)
            self.pubsub = subsystems.PubSub(core, self.rpc)
            self.channel = subsystems.Channel(core)

    def __init__(self, identity=None, address=None, context=None):
        self.core = _core.Core(identity=identity, address=address, context=context)
        self.vip = Agent.Subsystems(self, self.core)
