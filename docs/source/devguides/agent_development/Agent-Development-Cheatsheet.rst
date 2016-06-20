.. _Agent-Development-Cheatsheet:

=============================
Agent Development Cheat Sheet
=============================

This is a catalogue of features available in volttron
that are frequently useful in agent development.


Utilities
---------
These functions can be found in the *volttron.platform.agent.utils* module.
*logging* also needs to be imported to use the logger.

setup_logging
~~~~~~~~~~~~~
You'll probably see the following lines near the top of agent files:

.. code-block:: python

    utils.setup_logging()
    _log = logging.getLogger(__name__)

This code sets up the logger for this module so it can provide more useful
output. In most cases it will be better to use the logger in lieu of simply
printing messages with print.

load_config
~~~~~~~~~~~
load_config does just that. Give it the path to your config file and it will
parse the json and return a dictionary.

vip_main
~~~~~~~~
This is the function that is called to start your agent. You'll likely
see it in the main methods at the bottom of agents' files. Whatever is
passed to it (a class name or a function that returns an instance of
your agent) should accept a file path that can be parsed with load_config.


Core Agent Functionality
------------------------
These tools volttron.platform.vip.agent module.
Try importing 


Agent Lifecycle Events
~~~~~~~~~~~~~~~~~~~~~~
Each agent has four events that are triggered at different stages
of its life. These are onsetup, onstart, onstop, and onfinish. Registering
callbacks to these events are commonplace in agent development, with onstart
being the most frequently used.

The easiest way to register a callback is with a function decorator:

.. code-block:: python

    @Core.receiver('onstart')
    def function(self, sender, **kwargs):
        function_body

Periodic and Scheduled Function Calls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Functions and agent methods can be registered to be called periodically or scheduled
to be run at a particular time. Decorators or explicit access to an agent's core.periodic()
method can be used for this purpose. The latter is especially useful if, for example, a
decision needs to be made in an agent's onstart method as to whether a periodic call should
be initialized.

.. code-block:: python

    @Core.periodic(t)
    def function(self, ...):
        function_body

or

.. code-block:: python

    # inside some agent method
    self.core.periodic(t, function)


Subsystem
----------
These features are available to all Agent subclasses. No extra imports are required.

Remote Procedure Calls
~~~~~~~~~~~~~~~~~~~~~~
Remote Procedure Calls, or RPCs are a powerful way to interact with other agents.
To make a function available to call by a remote agent just add the export decorator:

.. code-block:: python

    @RPC.export
    def function(self, ...):
        function_body

*function* can now be called by a remote agent *agent* with

.. code-block:: python

    # vip identity is the identity (a string) of the agent
    # where function() is defined
    agent.vip.rpc.call(vip, 'function').get(timeout=t)

Pubsub
~~~~~~
Agents can publish and subscribe to topics. Like RPC, pubsub functions can be invoked
via decorators or inline through vip. The following function is called whenever
the agent sees a message starting with *topic_prefix*.

.. code-block:: python

    @PubSub.subscribe('pubsub', topic_prefix)
    def function(self, peer, sender, bus,  topic, headers, message):
        function_body

An agent can publish to a topic *topic* with the *self.vip.pubsub.publish* method.


Heartbeat
~~~~~~~~~
The heartbeat subsystem provides access to a periodic publish so that others
can observe the agent's status. Other agents can subscibe to the
*heartbeat* topic to see who is actively publishing to it.

It it turned off by default.

Health
~~~~~~
The health subsystem adds extra status information to the an agent's heartbeat.
Setting the status will start the heartbeat if it wasn't already.


Agent Skeleton
--------------

.. code-block:: python

    import logging
    
    from volttron.platform.vip.agent import Agent, Core, PubSub, RPC
    from volttron.platform.agent import utils
    
    utils.setup_logging()
    _log = logging.getLogger(__name__)
    
    
    class MyAgent(Agent):
        def __init__(self, config_path, **kwargs):
            self.config = utils.load_config(config_path)
    
        @Core.receiver('onsetup')
        def onsetup(self, sender, **kwargs):
            pass
    
        @Core.receiver('onstart')
        def onstart(self, sender, **kwargs):
            self.vip.heartbeat.start()
    
        @Core.receiver('onstop')
        def onstop(self, sender, **kwargs):
            pass
    
        @Core.receiver('onfinish')
        def onfinish(self, sender, **kwargs):
            pass
    
        @PubSub.subscribe('pubsub', 'some/topic')
        def on_match(self, peer, sender, bus,  topic, headers, message):
            pass
    
        @RPC.export
        def my_method(self):
            pass
    
    def main():
        utils.vip_main(MyAgent)
    
    if __name__ == '__main__':
        try:
            main()
        except KeyboardInterrupt:
            pass
