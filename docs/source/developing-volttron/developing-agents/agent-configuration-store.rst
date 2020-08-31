.. _Agent-Configuration-Store-Interface:

===================================
Agent Configuration Store Interface
===================================

The Agent Configuration Store Subsystem provides an interface for facilitating dynamic configuration via
the platform configuration store. It is intended to work alongside the original configuration file
to create a backwards compatible system for configuring agents with the bundled configuration file acting
as default settings for the agent.

If an Agent Author does not want to take advantage of the platform configuration store they need to make
no changes. To completely disable the Agent Configuration Store Subsystem an Agent may pass `enable_store=False`
to the `Agent.__init__` method.

The Agent Configuration Store Subsystem caches configurations as the platform sends updates to the agent.
Updates from the platform will usually trigger callbacks on the agent.

Agent access to the Configuration Store is managed through the `self.vip.config` object in the Agent class.


The "config" Configuration
**************************

The configuration name `config` is considered the canonical name of an Agents main configuration.
As such the Agent will always run callbacks for that configuration first at startup and when a
change to another configuration triggers any callbacks for `config`.


Configuration Callbacks
***********************

Agents may setup callbacks for different configuration events.  The callback method must have the following signature:

.. code-block:: python

    my_callback(self, config_name, action, contents)

.. note::

    The example above is for a class member method, however the method does not need to be a member of the agent class.

- **config_name** - The method to call when a configuration event occurs.
- **action** - The specific configuration event type that triggered the callback. Possible values are "NEW", "UPDATE",
  "DELETE". See :ref:`Configuration Events <Configuration-Store-Events>`
- **contents** - The actual contents of the configuration. Will be a string, list, or dictionary for the actions "NEW"
  and "UPDATE". None if the action is "DELETE".

.. note::

    All callbacks which are connected to the "NEW" event for a configuration will called during agent startup with the
    initial state of the configuration.


.. _Configuration-Store-Events:

Configuration Events
--------------------

- **NEW** - This event happens for every existing configuration at Agent startup and whenever a new configuration is
  added to the Configuration Store.
- **UPDATE** - This event happens every time a configuration is changed.
- **DELETE** - The event happens every time a configuration is removed from the store.


Setting Up a Callback
---------------------

A callback is setup with the `self.vip.config.subscribe` method.

.. note::

    Subscriptions may be setup at any point in the life cycle of an Agent. Ideally they are setup in __init__.


.. code-block:: python

    subscribe(callback, actions=["NEW", "UPDATE", "DELETE"], pattern="*")

- **callback** - The method to call when a configuration event occurs.
- **actions** - The specific configuration event that will trigger the callback. May be a string with the name of a
  single action or a list of actions.
- **pattern** - The pattern used to match configuration names to trigger the callback.


Configuration Name Pattern Matching
-----------------------------------

Configuration name matching uses Unix file name matching semantics. Specifically the python module :py:mod:`fnmatch` is
used.

Name matching is not case sensitive regardless of the platform VOLTTRON is running on.

For example, the pattern `devices/*` will trigger the supplied callback for any configuration name that starts with
`devices/`.

The default pattern matches all configurations.


Getting a Configuration
***********************

Once RPC methods are available to an agent (once onstart methods have been called or from any configuration callback)
the contents of any configuration may be acquired with the `self.vip.config.get` method.

.. code-block:: python

    get(config_name="config")

If the Configuration Subsystem has not been initialized with the starting values of the agent configuration that
will happen in order to satisfy the request.

If initialization occurs to satisfy the request callbacks will *not* be called before returning the results.

Typically an Agent will only obtain the contents of a configuration via a callback.
This method is included for agents that want to save state in the store and only need to
retrieve the contents of a configuration at startup and ignore any changes to the configuration going forward.


Setting a Configuration
***********************

Once RPC methods are available to an agent (once onstart methods have been called) the contents
of any configuration may be set with the `self.vip.config.set` method.

.. code-block:: python

    set(config_name, contents, trigger_callback=False, send_update=False)

The contents of the configuration may be a string, list, or dictionary.

This method is intended for agents that wish to maintain a copy of their state
in the store for retrieval at startup with the `self.vip.config.get` method.

.. warning::

    This method may **not** be called from a configuration callback. The Configuration Subsystem will
    detect this and raise a :py:class:`RuntimeError`, even if `trigger_callback` or `send_update` is False.

    The platform has a locking mechanism to prevent concurrent configuration updates to the Agent.
    Calling `self.vip.config.set` would cause the Agent and the Platform configuration store for that Agent to
    deadlock until a timeout occurs.

Optionally an agent may trigger any callbacks by setting `trigger_callback` to True. If `trigger_callback` is
set to False the platform will still send the updated configuration back to the agent. This ensures that a subsequent
call to `self.cip.config.get` will still return the correct value. This way the agent's configuration subsystem
is kept in sync with the platform's copy of the agent's configuration store at all times.

Optionally the agent may prevent the platform from sending the updated file to the agent by setting `send_update`
to False. This setting is available strictly for performance tuning.

.. warning::

    This setting will allow the agent's view of the configuration to fall out of sync with the platform.
    Subsequent calls to `self.vip.config.get` will return an old version of the file if it exists in the
    agent's view of the configuration store.

    This will also affect any configurations that reference the configuration changed with this setting.

    Care should be taken to ensure that the configuration is only retrieved at agent startup when using this
    option.


Setting a Default Configuration
*******************************

In order to more easily allow agents to use both the Configuration Store while still supporting configuration
via the tradition method of a bundled configuration file the `self.vip.config.set_default` method was created.

.. code-block:: python

    set_default(config_name, contents)

.. warning::

    This method may **not** be called once the Agent Configuration Store Subsystem has been initialized. This method
    should only be called from `__init__` or an `onsetup` method.

The `set_default` method adds a temporary configuration to the Agents Configuration Subsystem. Nothing is sent
to the platform. If a configuration with the same name exists in the platform store it will be presented to
a callback method in place of the default configuration.

The normal way to use this is to set the contents of the packaged Agent configuration as the default
contents for the configuration named `config`. This way the same callback used to process `config` configuration
in the Agent will be called when the Configuration Subsystem can be used to process the configuration file
packaged with the Agent.

.. note::

    No attempt is made to merge a default configuration with a configuration from the store.

If a configuration is deleted from the store and a default configuration exists with the same name
the Agent Configuration Subsystem will call the `UPDATE` callback for that configuration with
the contents of the default configuration.


Other Methods
*************

In a well thought out configuration scheme these methods should not be needed but are included for completeness.


List Configurations
-------------------

A current list of all configurations for the Agent may be called with the `self.vip.config.list` method.


Unsubscribe
-----------

All subscriptions can be removed with a call to the `self.vip.config.unsubscribe_all` method.


Delete
------

A configuration can be deleted with a call to the `self.vip.config.delete` method.

.. code-block:: python

    delete(config_name, trigger_callback=False)

.. note::

    This method may **not** be called from a callback for the same reason as the `self.vip.config.set` method.


Delete Default
--------------

A default configuration can be deleted with a call to the `self.vip.config.delete_default` method.

.. code-block:: python

    delete_default(config_name)

.. warning::

    This method may **not** be called once the Agent Configuration Store Subsystem has been initialized. This method should
    only be called from `__init__` or an `onsetup` method.


Example Agent
*************

The following example shows how to use set_default with a basic configuration and how to setup callbacks.

.. code-block:: python

    def my_agent(config_path, **kwargs):

        config = utils.load_config(config_path) #Now returns {} if config_path does not exist.

        setting1 = config.get("setting1", 42)
        setting2 = config.get("setting2", 2.5)

        return MyAgent(setting1, setting2, **kwargs)

    class MyAgent(Agent):
        def __init__(self, setting1=0, setting2=0.0, **kwargs):
            super(MyAgent, self).__init__(**kwargs)

            self.default_config = {"setting1": setting1,
                                   "setting2": setting2}

            self.vip.config.set_default("config", self.default_config)
            #Because we have a default config we don't have to worry about "DELETE"
            self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")
            self.vip.config.subscribe(self.configure_other, actions=["NEW", "UPDATE"], pattern="other_config/*")
            self.vip.config.subscribe(self.configure_delete, actions="DELETE", pattern="other_config/*")

        def configure_main(self, config_name, action, contents):
            #Ensure that we use default values from anything missing in the configuration.
            config = self.default_config.copy()
            config.update(contents)

            _log.debug("Configuring MyAgent")

            #Sanity check the types.
            try:
                setting1 = int(config["setting1"])
                setting2 = float(config["setting2"])
            except ValueError as e:
                _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
                #TODO: set a health status for the agent
                return

            _log.debug("Using setting1 {}, setting2 {}". format(setting1, setting2))
            #Do something with setting1 and setting2.

        def configure_other(self, config_name, action, contents):
            _log.debug("Configuring From {}".format(config_name))
            #Do something with contents of configuration.

        def configure_delete(self, config_name, action, contents):
            _log.debug("Removing {}".format(config_name))
            #Do something in response to the removed configuration.
