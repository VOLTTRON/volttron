import os

import gevent

from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent import Agent
from volttrontesting.utils.platformwrapper import PlatformWrapper


def build_agent(platform: PlatformWrapper, identity=None, agent_class=None):
    """Builds an agent instance with the passed platform as its bus.

    The agent identity will be set.  If the identity is set to None
    then a random identity will be created.
    """
    if agent_class is None:
        agent_class = Agent
        
    os.environ['VOLTTRON_HOME'] = platform.volttron_home
    agent = platform.build_agent(identity, agent_class=agent_class)
    gevent.sleep(0.1) # switch context for a bit
    os.environ.pop('VOLTTRON_HOME')
    return agent


def build_agent_with_key(platform: PlatformWrapper, identity=None):
    """Create an agent instance that has a generated public and private key.

    The passed platform will be the vip-address of the agent and the
     identity will be set.  If the identity is set to None then a random
     identity will be created.
    """
    os.environ['VOLTTRON_HOME'] = platform.volttron_home
    keys = KeyStore(os.path.join(platform.volttron_home,
                                          identity + '.keys'))
    keys.generate()
    agent = platform.build_agent(identity=identity,
                                  serverkey=platform.publickey,
                                  publickey=keys.public,
                                  secretkey=keys.secret)
    # Make publickey easily accessible for these tests
    agent.publickey = keys.public
    gevent.sleep(0.1) # switch context for a bit
    os.environ.pop('VOLTTRON_HOME')
    return agent
