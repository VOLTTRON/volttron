VIP Authorization Examples
==========================



*Note: authorization is a work in progress, and its implementation is in
`the develop
branch <https://github.com/VOLTTRON/volttron/tree/develop>`__.*

VIP `authentication <VIP-Authentication>`__ and authorization go hand in
hand. When a peer authenticates to a VOLTTRON platform that peer is
authorized to issue commands and run agents on that platform. VIP
authorization is about giving a platform owner the ability to limit the
capabilities of authenticated peers.


Single Capability
-----------------

Suppose a VOLLTRON platform owner wants to limit how peers can call a
weather agent on their platform. The owner specifies in
``$VOLTTRON_HOME/auth.json`` that two users (Alice and Bobby) can
authenticate to the platform, but only Alice is authorized to read the
temperature:

.. code:: JSON

    {
      "allow": [
        {"user_id": "Alice", "capabilities" : ["can_read_temp"], "credentials": "CURVE:abc...", },
        {"user_id": "Bobby", "credentials": "CURVE:xyz...", },
      ]
    }

(The credentials are abbreviated to simplify the example.)

In the weather agent, the authorization requirement is specified by
using the ``RPC.allow`` decorator:

.. code:: Python

    @RPC.allow('can_read_temp')
    @RPC.export
    def temperature():
       ...

Alice's agents (i.e., agents that have been authenticated using Alice's
credentials) can call ``temperature`` via `RPC <RPC-by-example>`__, but
if one of Bobby's agents tries to call ``temperature`` they will get an
exception:

``error: method "temperature" requires capabilities set(['can_read_temp']), but capability list [] was provided``

Multiple Capabilities
---------------------

Expanding on the weather-agent example, the ``temperature`` method can
require agents to have multiple capabilities:

.. code:: Python

    @RPC.allow(['can_read_temp', 'can_read_weather_data'])
    @RPC.export
    def temperature():
       ...

This requires an agent to have both the ``can_read_temp`` and the
``can_read_weather_data`` capabilities. Multiple capabilities can also
be specified by using multiple ``RPC.allow`` decorators:

.. code:: Python

    @RPC.allow('can_read_temp')
    @RPC.allow('can_read_weather_data')
    @RPC.export
    def temperature():
       ...

Full Example
------------

See the
`StandAloneWithAuth <https://github.com/VOLTTRON/volttron/tree/develop/examples/StandAloneWithAuth>`__
agent for a full example.

Ideas for Improvement
=====================

Utilizing Roles
---------------

Rather than requiring agent-authors to specify individual capabilities,
we should use *roles* to group multiple capabilities. To make this work
we would need to add a new decorator (e.g., ``RPC.allow_roles``). We
would also need to define a mapping of roles to sets of capabilities.

For example, somewhere we would define a role:

.. code:: JSON

    {
      "roles": [
        {"agent_control": ["install_agent", "remove_agent"]}, 
        {"admin": ["install_agent", "remove_agent", "start", "stop"]}
      ]
    }

Default Deny-All
----------------

Currently the default is to allow anyone to call RPC-exported methods
that are not decorated with ``RPC.allow``. A more secure default would
be to disallow everyone (at least remote users) from calling methods
that are not decorated with ``RPC.allow``.

Authorize at the Agent Level
----------------------------

Authorization is designed to work with user/peer authentication. So if
user Alice authenticates to a platform, then all of Alice's agents are
granted Alice's capabilities. It would be nice to be able to selectively
grant capabilities to individual agents.
