.. _Agent-Configuration-Store:

=========================
Agent Configuration Store
=========================

This document describes the configuration store feature and explains how an agent uses it.

The configuration store enables users to store agent configurations on the platform and allows the agent to
automatically retrieve them during runtime.  Users may update the configurations and the agent will automatically be
informed of the changes.


Compatibility
=============

Supporting the configuration store will *not* be required by Agents, however the usage will be strongly encouraged as it
should substantially improve user experience.

The previous method for configuring an agent will still be available to agents (and in some cases required), however
agents can be created to only work with the configuration store and not support the old method at all.

It will be possible to create an agent to use the traditional method for configuration to establish defaults if no
configuration exist in the platform configuration store.


Configuration Names and Paths
=============================

Any valid OS file path name is a valid configuration name.  Any leading or trailing "/", "\" and whitespace is removed
by the store.

The canonical name for the main agent configuration is `config`.

The configuration subsystem remembers the case of configuration names.  Name matching is case insensitive both on the
Agent and platform side.  Configuration names are reported to agent callbacks in the original case used when adding them
to the configuration.  If a new configuration is store with a different case of an existing name the new name case is
used.


Configuration Ownership
=======================

Each configuration belongs to one agent and one agent only.  When an agent refers to a configuration file via it's path
it does not need to supply any information about its identity to the platform in the file path.  The only configurations
an agent has direct access to are it's own.  The platform will only inform the owning agent configuration changes.


Configuration File Types
========================

Configurations files come in three types: `json`, `csv`, and `raw`.  The type of a configuration file is declared when
it is added to or changed in the store.

The parser assumes the first row of every CSV file is a header.

Invalid JSON or CSV files are rejected at the time they are added to the store.

Raw files are unparsed and accepted as is.

Other parsed types may be added in the future.


Configuration File Representation to Agents
===========================================

JSON
----

A JSON file is parsed and represented as appropriate data types to the requester.

Consider a file with the following contents:

.. code-block:: json

    {
        "result": "PREEMPTED",
        "info": null,
        "data": {
                    "agentID": "my_agent",
                    "taskID": "my_task"
                }
    }

The file will be parsed and presented as a dictionary with 3 values to the requester.


CSV
---

A CSV file is represented as a list of objects. Each object represents a row in the CSV file.

For instance this (simplified) CSV file:

.. csv-table:: Example CSV
    :header: Volttron Point Name,Modbus Register,Writable,Point Address

    ReturnAirCO2,>f,FALSE,1001
    ReturnAirCO2Stpt,>f,TRUE,1011
    
will be represented like this:

.. code-block:: json

    [
        {
            "Volttron Point Name": "ReturnAirCO2",
            "Modbus Register": ">f",
            "Writable": "FALSE",
            "Point Address": "1001"
        },
        {
            "Volttron Point Name": "ReturnAirCO2Stpt",
            "Modbus Register": ">f",
            "Writable": "TRUE",
            "Point Address": "1011"
        }
    ]


Raw
---

Raw files are represented as a string containing the contents of the file.


File references
===============

The `Platform Configuration Store` supports referencing one configuration file from another.  If a referenced file
exists the contents of that file will replace the file reference when the file is sent to the owning agent.  Otherwise
the reference will be replaced with None.

Only configurations that are parsed by the platform (currently "json" or "csv") will be examined for references.  If the
file referenced is another parsed file type (JSON or CSV, currently) then the replacement will be the parsed contents of
the file.

In a JSON object the name of a value will never be considered a reference.

A file reference is any value string that starts with ``config://``.  The rest of the string is the path in the config
store to that configuration.  The config store path is converted to lower case for comparison purposes.

Consider the following configuration files named `devices/vav1.config` and `registries/vav.csv`, respectively:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},

        "driver_type": "bacnet",
        "registry_config":"config://registries/vav.csv",
        "campus": "pnnl",
        "building": "isb1",
        "unit": "vav1"
    }

.. csv-table:: vav.csv
    :header: Volttron Point Name,Modbus Register,Writable,Point Address

    ReturnAirCO2,>f,FALSE,1001
    ReturnAirCO2Stpt,>f,TRUE,1011

The resulting configuration returns when an agent asks for `devices/vav1.config`.  The Python object will have the
following configuration:

.. code-block:: python

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},

        "driver_type": "bacnet",
        "registry_config":[
                               {
                                   "Volttron Point Name": "ReturnAirCO2",
                                   "Modbus Register": ">f",
                                   "Writable": "FALSE",
                                   "Point Address": "1001"
                               },
                               {
                                   "Volttron Point Name": "ReturnAirCO2Stpt",
                                   "Modbus Register": ">f",
                                   "Writable": "TRUE",
                                   "Point Address": "1011"
                               }
                          ],
        "campus": "pnnl",
        "building": "isb1",
        "unit": "vav1"
    }

Circular references are not allowed.  Adding a file that creates a circular reference will cause that file to be
rejected by the platform.

If a file is changed in anyway (`NEW`, `UPDATE`, or `DELETE`) and that file is referred to by another file then the
platform considers the referring configuration as changed.  The configuration subsystem on the Agent will call every
callback listening to a file or any file referring to that file either directly or indirectly.


Agent Configuration Sub System
==============================

The configuration store shall be implemented on the Agent(client) side in the form of a new subsystem called config.

The subsystem caches configurations as the platform updates the state to the agent.  Changes to the cache triggered by
an RPC call from the platform will trigger callbacks in the agent.

No callback methods are called until the `onconfig` phase of agent startup.  A new phase to agent startup called
`onconfig` will be added to the `Core `class.  Originally it was planned to have this run after the `onstart` phase has
completed but that is currently not possible.  Ideally if an agent is using the config store feature it will not need
any `onstart` methods.

When the `onconfig` phase is triggered the subsystem will retrieve the current configuration state from the platform and
call all callbacks registered to a configuration in the store to the `NEW` action.  No callbacks are called before this
point in agent startup.

The first time callbacks are called at agent startup any callbacks subscribed to a configuration called `config` are
called first.


Configuration Subsystem Agent Methods
-------------------------------------

These methods are part of the interface available to the Agent.

    **config.get( config_name="config")** - Get the contents of a configuration.
    If no name is provided the contents of the main agent configuration "config" is returned.  This may not be called
    before `onstart` methods are called.  If called during the `onstart` phase it will trigger the subsystem to
    initialize early but will not trigger any callbacks.

    **config.subscribe(callback, action=("NEW", "UPDATE", "DELETE"), pattern="*")** - Sets up a callback for handling a
    configuration change. The platform will automatically update the agent when a configuration changes ultimately
    triggering all callbacks that match the pattern specified.  The action argument describes the types of configuration
    change action that will trigger the callback.  Possible actions are `NEW`, `UPDATE`, and `DELETE` or a tuple of any
    combination of actions.  If no action is supplied the callback happens for all changes.  A list of actions can be
    supplied if desired.  If no file name pattern is supplied then the callback is called for all configurations.  The
    pattern is an regex used match the configuration name.

    The callback will also be called if any file referenced by a configuration file is changed.

    The signature of the callback method is ``callback(config_name, action, contents)`` where `file_name` is the file
    that triggered the callback, action is the action that triggered the callback, and contents are the new contents of
    the configuration.  Contents will be ``None`` on a `DELETE` action.  All callbacks registered for `NEW` events will
    be called at agent startup after all `osntart` methods have been called.  Unlike pubsub subscriptions, this may be
    called at any point in an agent's lifetime.

    **config.unsubscribe(callback=None, config_name_pattern=None)** - Unsubscribe from configuration changes.
    Specifying a callback only will unsubscribe that callback from all config name patterns they have been bound to.
    If a pattern only is specified then all callbacks bound to that pattern will be removed.  Specifying both will
    remove that callback from that pattern.  Calling with no arguments will remove all subscriptions.

    **config.unsubscribe_all()** - Unsubscribe from all configuration changes.

    **config.set( config_name, contents, trigger_callback=False )** - Set the contents of a configuration.  This may not
    be called before `onstart` methods are called.  This can be used by an agent to store agent state across agent
    installations.  This will *NOT* trigger any callbacks unless `trigger_callback` is set to `True`.  To prevent
    deadlock with the platform this method may not be called from a configuration callback function.  Doing so will
    raise a `RuntimeError` exception.

    This will not modify the local configuration cache the Agent maintains.  It will send the configuration change to
    the platform and rely on the subsequent `update_config` call.

    **config.delete( config_name, trigger_callback=False)** - Remove the configuration from the store.  This will *NOT*
    trigger any callbacks unless trigger_callback is `True`.  To prevent deadlock with the platform this method may not
    be called from a configuration callback function.  Doing so will raise a `RuntimeError` exception.

    **config.list( )** - Returns a list of configuration names.

    **config.set_default(config_name, contents, trigger_callback=False)** - Set a default value for a configuration.
    *DOES NOT* modify the platform's configuration store but creates a default configuration that is used for agent
    configuration callbacks if the configuration does not exist in the store or the configuration is deleted from the
    store.  The callback will only be triggered if `trigger_callback` is true and the configuration store subsystem on
    the agent is not aware of a configuration with that name from the platform store.

    Typically this will be called in the `__init__` method of an agent with the parsed contents of the packaged
    configuration file.  This may not be called from a configuration callback.  Doing so will raise a `RuntimeError`.

    **config.delete_default(config_name, trigger_callback=False)** - Delete a default value for a configuration.  This
    method is included for for completeness and is unlikely to be used in agent code.  This may not be called from a
    configuration callback.  Doing so will raise a `RuntimeError`.


Configuration Sub System RPC Methods
------------------------------------

These methods are made available on each agent to allow the platform to communicate changes to a configuration to the
affected agent.  As these methods are not part of the exposed interface they are subject to change.

**config.update( config_name, action, contents=None, trigger_callback=True)** - called by the platform when a
configuration was changed by some method other than the Agent changing the configuration itself.  Trigger callback tells
the agent whether or not to call any callbacks associate with the configuration.


Notes on trigger_callback
-------------------------

As the configuration subsystem calls all callbacks in the `onconfig` phase and none are called beforehand the
`trigger_callback` setting is effectively ignored if an agent sets a configuration or default configuration before the
end of the `onstart` phase.


Platform Configuration Store
============================

The platform configuration store handles the storage and maintenance of configuration states on the platform.

As these methods are not part of the exposed interface they are subject to change.


Platform RPC Methods
--------------------


Methods for Agents
^^^^^^^^^^^^^^^^^^

Agent methods that change configurations do not trigger any callbacks unless trigger_callback is True.

**set_config(config_name, contents, trigger_callback=False)** - Change/create a configuration file on the platform.

**get_configs()** - Get all of the configurations for an Agent.

**delete_config(config_name, trigger_callback=False)** - Delete a configuration.


Methods for Management
^^^^^^^^^^^^^^^^^^^^^^

**manage_store_config(identity, config_name, contents, config_type="raw")** - Change/create a configuration on the
platform for an agent with the specified identity

**manage_delete_config(identity, config_name)** - Delete a configuration for an agent with the specified identity.
Calls the agent's update_config with the action `DELETE_ALL` and no configuration name.

**manage_delete_store(identity)** - Delete all configurations for a VIP IDENTITY.

**manage_list_config(identity)** - Get a list of configurations for an agent with the specified identity.

**manage_get_config(identity, config_name, raw=True)** - Get the contents of a configuration file.  If raw is set to
`True` this function will return the original file, otherwise it will return the parsed representation of the file.

**manage_list_stores()** - Get a list of all the agents with configurations.


Direct Call Methods
^^^^^^^^^^^^^^^^^^^

Services local to the platform who wish to use the configuration store may use two helper methods on the agent class
created for this purpose.  This allows the auth service to use the config store before the router is started.

**delete(self, identity, config_name, trigger_callback=False)** - Same as functionality as `delete_config`, but the
caller must specify the identity of the config store.

**store(self, identity, config_name, contents, trigger_callback=False)** - Same functionality as set_config, but the
caller must specify the identity of the config store.


Command Line Interface
^^^^^^^^^^^^^^^^^^^^^^

The command line interface will consist of a new commands for the `volttron-ctl` program called `config` with four
sub-commands called `store`, `delete`, `list`, `get`.  These commands will map directly to the management RPC functions
in the previous section.


Disabling the Configuration Store
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Agents may optionally disable support for the configuration store by passing ``enable_store=False`` to the `__init__`
method of the Agent class.  This allows temporary agents to not spin up the subsystem when it is not needed.  Platform
service agents that do not yet support the configuration store and the temporary agents used by `volttron-ctl` will set
this value.
