.. _VIP-Authorization:

=================
VIP Authorization
=================

VIP :ref:`authentication <VIP-Authentication>` and authorization go hand in hand.  When an agent authenticates to a
VOLTTRON platform that agent proves its identity to the platform.  Once authenticated, an agent is allowed to connect to
the :ref:`message bus <Message-Bus>`.  VIP authorization is about giving a platform owner the ability to limit
the capabilities of authenticated agents.

Authorization Implementation
----------------------------

Authorization has client and server implementations. On the client side, 
authorization is used to connect the auth subsystem to the auth service.
This provides the connection needed to manage capabilites and protected topics.
The server authorization is used to manage pending credentials and certificates that
are handled by authentication, as well as managing capabilties and protected topics.

BaseServerAuthorization:
* approve_authorization
* deny_authorization
* delete_authorization
* get_authorization
* get_authorization_status
* get_pending_authorizations
* get_approved_authorizations
* get_denied_authorizations
* update_user_capabilites
* load_protected_topics
* update_protected_topics

BaseClientAuthorization
* connect_remote_platform

There are two parts to authorization:

#. Required capabilities (specified in agent's code)
#. Authorization entries (specified via ``volttron-ctl auth`` commands)

The following example will walk through how to specify required capabilities and grant those capabilities in
authorization entries.


Single Capability
-----------------
For this example suppose there is a temperature agent that can read and set the temperature of a particular room.  The
agent author anticipates that building managers will want to limit which agents can set the temperature.

In the temperature agent, a required capability is specified by using the ``RPC.allow`` decorator:

.. code:: Python

    @RPC.export
    def get_temperature():
       ...

    @RPC.allow('CAP_SET_TEMP')
    @RPC.export
    def set_temperature(temp):
       ...

In the code above, any agent can call the ``get_temperature`` method, but only agents with the ``CAP_SET_TEMP``
capability can call ``set_temperature``.

.. Note::

    Capabilities are arbitrary strings.  This example follows the general style used for Linux capabilities, but it is
    up to the agent author.

Now that a required capability has been specified, suppose a VOLTTRON platform owner wants to allow a specific agent,
say `Alice Agent`, to set the temperature.

The platform owner runs ``vctl auth add`` to add new authorization entries or ``vctl auth update`` to update an existing
entry.  If `Alice Agent` is installed on the platform, then it already has an authorization entry.  Running
``vctl auth list`` shows the existing entries:

::

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

Currently AliceAgent cannot set the temperature because it does not have the ``CAP_SET_TEMP`` capability.  To grant this
capability the platform owner runs ``vctl auth update 3``:

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


Now `Alice Agent` can call ``set_temperature`` via RPC.  If other agents try to call that method they will get the
following exception:

.. code-block:: console

    error: method "set_temperature" requires capabilities set(['CAP_SET_TEMP']),
    but capability list [] was provided


Multiple Capabilities
---------------------

Expanding on the temperature-agent example, the ``set_temperature`` method can require agents to have multiple
capabilities:

.. code:: Python

    @RPC.allow(['CAP_SET_TEMP', 'CAP_FOO_BAR'])
    @RPC.export
    def set_temperature():
       ...

This requires an agent to have both the ``CAP_SET_TEMP`` and the ``CAP_FOO_BAR`` capabilities. Multiple capabilities can
also be specified by using multiple ``RPC.allow`` decorators:

.. code:: Python

    @RPC.allow('CAP_SET_TEMP')
    @RPC.allow('CAN_FOO_BAR')
    @RPC.export
    def temperature():
       ...


Capability with parameter restriction
-------------------------------------

Capabilities can also be used to restrict access to a rpc method only with certain parameter values.  For example, if
`Agent A` exposes a method bar which accepts parameter `x`.

AgentA's capability enabled exported RPC method:

.. code-block:: python

   @RPC.export
   @RPC.allow('can_call_bar')
   def bar(self, x):
      return 'If you can see this, then you have the required capabilities'

You can restrict access to `Agent A`'s `bar` method to `Agent B` with ``x=1``.  To add this auth entry use the
``vctl auth add`` command as show below:

.. code-block:: bash

   vctl auth add --capabilities '{"test1_cap2":{"x":1}}' --user_id AgentB --credential vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0


The auth.json file entry for the above command would be:

.. code-block:: json

    {
      "domain": null,
      "user_id": "AgentB",
      "roles": [],
      "enabled": true,
      "mechanism": "CURVE",
      "capabilities": {
        "test1_cap2": {
          "x": 1
        }
      },
      "groups": [],
      "address": null,
      "credentials": "vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0",
      "comments": null
    }


Parameter values can also be regular expressions:

.. code-block:: console

    (volttron)volttron@volttron1:~/git/myvolttron$ vctl auth add
    domain []:
    address []:
    user_id []:
    capabilities (delimit multiple entries with comma) []: {'test1_cap2':{'x':'/.*'}}
    roles (delimit multiple entries with comma) []:
    groups (delimit multiple entries with comma) []:
    mechanism [CURVE]:
    credentials []: vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0
    comments []:
    enabled [True]:
    added entry domain=None, address=None, mechanism='CURVE', credentials=u'vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0', user_id='b22e041d-ec21-4f78-b32e-ab7138c22373'


The auth.json file entry for the above command would be:

.. code-block:: json

    {
      "domain": null,
      "user_id": "90f8ef35-4407-49d8-8863-4220e95974c7",
      "roles": [],
      "enabled": true,
      "mechanism": "CURVE",
      "capabilities": {
        "test1_cap2": {
          "x": "/.*"
        }
      },
      "groups": [],
      "address": null,
      "credentials": "vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0",
      "comments": null
    }


.. _Protected-Topics:

Protecting Pub/Sub Topics
=========================

VIP :ref:`authorization <VIP-Authorization>` enables VOLTTRON platform owners to protect pub/sub topics.  More
specifically, a platform owner can limit who can publish to a given topic.  This protects subscribers on that platform
from receiving messages (on the protected topic) from unauthorized agents.


Example
-------

To protect a topic, add the topic name to ``$VOLTTRON_HOME/protected_topics.json``.  For example, the following
protected-topics file declares that the topic ``foo`` is protected:

.. code:: JSON

    {
       "write-protect": [
          {"topic": "foo", "capabilities": ["can_publish_to_foo"]}
       ]
    }

.. note::

    The capability name ``can_publish_to_foo`` is not special;  It can be any string, but it is easier to manage
    capabilities with meaningful names.

Now only agents with the capability ``can_publish_to_foo`` can publish to the topic ``foo``.  To add this capability to
authenticated agents, run ``vctl auth update`` (or ``volttron-ctl auth add`` for new authentication entries), and enter
``can_publish_to_foo`` in the capabilities field:

.. code:: Bash

    capabilities (delimit multiple entries with comma) []: can_publish_to_foo

Agents that have the ``can_publish_to_foo`` capabilities can publish to topic ``foo``.  That is, such agents can call:

.. code:: Python

    self.vip.pubsub.publish('pubsub', 'foo', message='Here is a message')

If unauthorized agents try to publish to topic ``foo`` they will get an exception:

.. code-block:: console

    to publish to topic "foo" requires capabilities ['can_publish_to_foo'], but capability list [] was provided


Regular Expressions
-------------------

Topic names in ``$VOLTTRON_HOME/protected_topics.json`` can be specified as regular expressions.  In order to use a
regular expression, the topic name must begin and end with a "/". For example:

.. code:: JSON

    {
       "write-protect": [
          {"topic": "/foo/*.*/", "capabilities": ["can_publish_to_foo"]}
       ]
    }

This protects topics such as ``foo/bar`` and ``foo/anything``.
