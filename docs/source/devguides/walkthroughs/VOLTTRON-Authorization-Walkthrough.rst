.. _VOLTTRONAuthorization:
VOLTTRON™ Authorization:
========================

This walkthrough guide describes how to use VOLTTRON™ authorization feature to allow an exported RPC method to be called only by authorized agents.

Exported RPC method with Authorization:
--------------------------------------

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

Allowing authorization capabilities:
--------------------------------------
:ref:`AuthenticationCommands`

In order to allow an agent to call an exported RPC method with authorization capability, that capability needs to be added to the
calling agent's authentication record. This can be done by using VOLTTRON Authentication commands.

::

    volttron-vtl auth add




