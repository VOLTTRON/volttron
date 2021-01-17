.. _Configuration-Store:

===================
Configuration Store
===================

The Platform Configuration Store is a mechanism provided by the platform to facilitate the dynamic configuration
of agents.  The Platform Configuration Store works by informing agents of changes to their configuration store and
the agent responding to those changes by updating any settings, subscriptions, or processes that are affected by
the configuration of the Agent.


Configurations and Agents
=========================

Each agent has it's own configuration store (or just store). Agents are not given access to any other agent's store.

The existence of a store is not dependent on the existence of an agent installed on the platform.

Each store has a unique identity.  Stores are matched to agents at agent runtime via the agent's :term:`VIP Identity`.
Therefore the store for an agent is the store with the same identity as the agent's VIP IDENTITY.

When a user updates a configuration in the store the platform immediately informs the agent of the change.  The platform
will not send another update until the Agent finishes processing the first.  The platform will send updates to the
agent, one file at a time, in the order the changes were received.


Configuration Names
===================

Every configuration in an agent's store has a unique name.  When a configuration is added to an agent's store
with the same name as an existing configuration it will replace the existing configuration.  The store will
remove any leading or trailing whitespace, "/", and "\\" from the name.


Configuration File Types
========================

The configuration store will automatically parse configuration files before presenting them to an agent.  Additionally,
the configuration store does support storing raw data and giving to the agent unparsed.  Most Agents will require the
configuration to be parsed.  Any Agent that requires raw data will specifically mention the requirement in its
documentation.

This system removes the requirement that configuration files for an agent be in a specific format.  For instance
a registry configuration for a driver may be JSON instead of CSV if that is more convenient for the user.  This
will work as long as the JSON parses into an equivalent set of objects as an appropriate CSV file.

Currently the store supports parsing JSON and CSV files with support for more files types to come.


JSON
----

The store uses the same JSON parser that agents use to parse their configuration files. Therefore it supports
Python style comments and must create an object or list when parsed.

::

    {
        "result": "PREEMPTED", #This is a comment.
        "info": null,
        "data": {
                    "agentID": "my_agent", #This is another comment.
                    "taskID": "my_task"
                }
    }

CSV
---

A CSV file is represented as a list of objects. Each object represents a row in the CSV file.

For instance this simple CSV file:

.. csv-table:: Example CSV
    :header: Volttron Point Name,Modbus Register,Writable,Point Address

    ReturnAirCO2,>f,FALSE,1001
    ReturnAirCO2Stpt,>f,TRUE,1011

Is the equivalent to this JSON file:

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


File references
===============

The Platform Configuration Store supports referencing one configuration file from another.  If a referenced file exists
the contents of that file will replace the file reference when the file is processed by the agent. Otherwise the
reference will be replaced with null (or in Python, ``None``).

Only configurations that are parsed by the platform (currently JSON or CSV) will be examined for references.  If the
file referenced is another parsed file type (JSON or CSV, currently) then the replacement will be the parsed contents of
the file, otherwise it will be the raw contents of the file.

In a JSON object the name of a value will never be considered a reference.

A file reference is any value string that starts with ``config://``.  The rest of the string is the name of another
configuration.  The configuration name is converted to lower case for comparison purposes.

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

The resulting configuration returns when an agent asks for `devices/vav1.config`.

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

Circular references are not allowed. Adding a file that creates a circular reference will cause that file to be rejected
by the platform.

If a configuration is changed in any way and that configuration is referred to by another configuration then
the agent considers the referring configuration as changed.  Thus a set of configurations with references
can be considered one large configuration broken into pieces for the users convenience.

Multiple configurations may all reference a single configuration.  For instance, when configuring drivers
in the Platform Driver you may have multiple drivers reference the same registry if appropriate.


Modifying the Configuration Store
=================================

Currently the configuration store must be modified through the command line. See
:ref:`Commandline Interface <Commandline-Interface>`.

.. toctree::

   commandline-interface
   agent-configuration-store
