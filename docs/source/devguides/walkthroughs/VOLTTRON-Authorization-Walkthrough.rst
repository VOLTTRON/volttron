.. _VOLTTRONAuthentication:
VOLTTRON™ Authentication:
========================

This walkthrough guide describes how to use VOLTTRON™ Authentication features.
In the current version, VOLTTRON authenticates an agent before allowing it to call an exported RPC method that has authorization capabilities.

Before going into adding authentication record for an agent, lets look into exported RPC methods with authorization capabilties.

Exported RPC method with Authorization:
---------------------------------------

A normal exported RPC method that can be called by any agent is written with @RPC.export decorator.
In order to add authorization capability an exported RPC method would also have @RPC.allow decorator.

::

   @RPC.export
   def foo(self):
      return 'Anybody can call this function via RPC'

   @RPC.export
   @RPC.allow('can_call_bar')
   def bar(self):
      return 'If you can see this, then you have the required capabilities'

In the above code snippet foo method can called by any agent whereas bar method can be called by only those agents that have ‘can_call_bar’ capability.
'can_call_bar' in @RPC.allow decorator is an arbitrary string defining the capability.
A method can have multiple @RPC.allow decorators defining multiple capabilties.
A method can also have a single @RPC.allow decorator defining multiple capabilities in an array.

For more information on capabilties, please see :ref:`VIP Authorization Example<VIPAuthorization>`.

Adding agent authentication record to allow authorization capabilities:
------------------------------------------------------------------------

In order to allow an agent to call an exported RPC method with authorization capability, that capability needs to be added to the
calling agent's authentication record. This can be done by using VOLTTRON Authentication commands.

::

    volttron-vtl auth add

      "domain": null,
      "user_id": "platform.myagent",
      "roles": [],
      "enabled": true,
      "mechanism": "CURVE",
      "capabilities": ['can_call_foo'],
      "groups": [],
      "address": null,
      "credentials": "xMtfkj6LoCDW4fEN9fULPoZGUtEFwTfmhtjaXHBntxk",
      "comments": ""

This would allow an agent with identity 'platform.myagent' to be able to call foo method.
For more information on authentication commands, see :ref:`Authentication Commands<AuthenticationCommands>`



