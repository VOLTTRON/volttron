.. _VIP-Authorization:
=================
VIP Authorization
=================

VIP :ref:`authentication <VIP-Authentication>` and authorization go hand in
hand. When an agent authenticates to a VOLTTRON platform that agent proves its
identity to the platform. Once authenticated, an agent is allowed to
connect to the :ref:`message bus<_VOLTTRON-Message-Bus>`. VIP
authorization is about giving a platform owner the ability to limit the
capabilities of authenticated agents.

There are two parts to authorization:

#. Required capabilities (specified in agent's code)
#. Authorization entries (specified via ``volttron-ctl auth`` commands)

The following example will walk through how to specify required capabilities
and grant those capabilities in authorization entries.

Single Capability
-----------------
For this example suppose there is a temperature agent that can read and set the
temperature of a particular room. The agent author anticipates that building
managers will want to limit which agents can set the temperature.

In the temperature agent, a required capability is specified by
using the ``RPC.allow`` decorator:

.. code:: Python

    @RPC.export
    def get_temperature():
       ...

    @RPC.allow('CAP_SET_TEMP')
    @RPC.export
    def set_temperature(temp):
       ...

In the code above, any agent can call the ``get_temperature`` method, but only
agents with the ``CAP_SET_TEMP`` capability can call ``set_temperature``.
(Note: capabilities are arbitrary strings. This example follows the general
style used for Linux capabilities, but it is up to the agent author.)

Now that a required capability has been specified, suppose a VOLLTRON platform
owner wants to allow a specific agent, say AliceAgent, to set the temperature.

The platform owner runs ``volttron-ctl auth add`` to add new authorization
entries or ``volttron-ctl auth update`` to update an existing entry. 
If AliceAgent is installed on the platform, then it already has an
authorization entry. Running ``volttron-ctl auth list`` shows the existing
entries:

.. code:: JSON

    ...
    INDEX: 3
    {
      "domain": null, 
      "user_id": "AliceAgent", 
      "roles": [], 
      "enabled": true, 
      "mechanism": "CURVE", 
      "capabilities": [], 
      "groups": [], 
      "address": null, 
      "credentials": "JydrFRRv-kdSejL6Ldxy978pOf8HkWC9fRHUWKmJfxc", 
      "comments": null
    }
    ...

Currently AliceAgent cannot set the temperature because it does
not have the ``CAP_SET_TEMP`` capability. To grant this capability
the platform owner runs ``volttron-ctl auth update 3``:

.. code:: Bash

    (For any field type "clear" to clear the value.)
    domain []: 
    address []: 
    user_id [AliceAgent]: 
    capabilities (delimit multiple entries with comma) []: CAP_SET_TEMP
    roles (delimit multiple entries with comma) []: 
    groups (delimit multiple entries with comma) []: 
    mechanism [CURVE]: 
    credentials [JydrFRRv-kdSejL6Ldxy978pOf8HkWC9fRHUWKmJfxc]: 
    comments []: 
    enabled [True]: 
    updated entry at index 3


Now AliceAgent can call ``set_temperature`` via RPC.
If other agents try to call that method they will get the following
exception::

    error: method "set_temperature" requires capabilities set(['CAP_SET_TEMP']),
    but capability list [] was provided

Multiple Capabilities
---------------------

Expanding on the temperature-agent example, the ``set_temperature`` method can
require agents to have multiple capabilities:

.. code:: Python

    @RPC.allow(['CAP_SET_TEMP', 'CAP_FOO_BAR'])
    @RPC.export
    def set_temperature():
       ...

This requires an agent to have both the ``CAP_SET_TEMP`` and the
``CAP_FOO_BAR`` capabilities. Multiple capabilities can also
be specified by using multiple ``RPC.allow`` decorators:

.. code:: Python

    @RPC.allow('CAP_SET_TEMP')
    @RPC.allow('CAN_FOO_BAR')
    @RPC.export
    def temperature():
       ...

