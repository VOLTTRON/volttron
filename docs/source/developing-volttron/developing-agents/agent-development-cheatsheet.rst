.. _Agent-Development-Cheatsheet:

=============================
Agent Development Cheat Sheet
=============================

This is a catalogue of features available in volttron
that are frequently useful in agent development.


Utilities
=========

These functions can be found in the `volttron.platform.agent.utils` module. `logging` also needs to be imported to use
the logger.


setup_logging
-------------

You'll probably see the following lines near the top of agent files:

.. code-block:: python

    utils.setup_logging()
    _log = logging.getLogger(__name__)

This code sets up the logger for this module so it can provide more useful output.  In most cases it will be better to
use the logger in lieu of simply printing messages with print.


load_config
-----------

Given the path to your config file `load_config` will parse the json and return a dictionary.


vip_main
--------

This is the function that is called to start your agent.  You'll likely see it in the main methods at the bottom of
agents' files.  Whatever is passed to it (a class name or a function that returns an instance of your agent) should
accept a file path that can be parsed with `load_config`.


Core Agent Functionality
========================

These tools are included in the `volttron.platform.vip.agent` module;  Import the module to use the included agent
functions.


Agent Lifecycle Events
----------------------

Each agent has four events that are triggered at different stages of its life. These are `onsetup`, `onstart`, `onstop`,
and `onfinish`.  Registering callbacks to these events are commonplace in agent development, with onstart being the most
frequently used.

The easiest way to register a callback is with a function decorator:

.. code-block:: python

    @Core.receiver('onstart')
    def function(self, sender, **kwargs):
        function_body


Periodic and Scheduled Function Calls
=====================================

Functions and agent methods can be registered to be called periodically or scheduled to run at a particular time using
the `Core.schedule` decorator or by calling an agent's `core.schedule()` method. The latter is especially useful if, for
example, a decision needs to be made in an agent's onstart method as to whether a call should be scheduled.

.. code-block:: python

    from volttron.platform.scheduling import cron, periodic

    @Core.schedule(t)
    def function(self):
        ...

    @Core.schedule(periodic(t))
    def periodic_function(self):
        ...

    @Core.schedule(cron('0 1 * * *'))
    def cron_function(self):
       ...

or

.. code-block:: python

    # inside some agent method
    self.core.schedule(t, function)
    self.core.schedule(periodic(t), periodic_function)
    self.core.schedule(cron('0 1 * * *'), cron_function)


Subsystem
=========

These features are available to all Agent subclasses. No extra imports are required.


Remote Procedure Calls
----------------------

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
------

Agents can publish and subscribe to topics. Like RPC, pubsub functions can be invoked via decorators or inline through
vip. The following function is called whenever the agent sees a message starting with *topic_prefix*.

.. code-block:: python

    @PubSub.subscribe('pubsub', topic_prefix)
    def function(self, peer, sender, bus,  topic, headers, message):
        function_body

An agent can publish to a topic *topic* with the `self.vip.pubsub.publish` method.

An agent can remove a subscriptions with `self.vip.pubsub.unsubscribe`. Giving None as values for the prefix and
callback argument will unsubscribe from everything on that bus. This is handy for subscriptions that must be updated
base on a configuration setting.


Configuration Store
-------------------

Support for the configuration store is done by subscribing to configuration changes with `self.vip.config.subscribe`.

.. code-block:: python

    self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")

See :ref:`Agent Configuration Store <Agent-Configuration-Store>`


Heartbeat
---------

The heartbeat subsystem provides access to a periodic publish so that others can observe the agent's status. Other
agents can subscribe to the *heartbeat* topic to see who is actively publishing to it. It it turned off by default.


Health
------

The health subsystem adds extra status information to the an agent's heartbeat. Setting the status will start the
heartbeat if it wasn't already.


Agent Skeleton Code
===================

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
