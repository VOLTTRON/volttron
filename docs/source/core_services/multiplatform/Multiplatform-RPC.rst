.. _Multi-Platform-RPC:

================================
Multi-Platform RPC Communication
================================


Multi-Platform RPC communication allows an agent on one platform to make RPC call on an agent in another platform
without having to setup connection to the remote platform directly. The connection will be internally managed
by the VOLTTRON platform router module. Please refer here
:ref:`Multi-Platform Communication Setup <Multi-Platform-Communication>`) for more details regarding setting up of
Multi-Platform connections.

Calling External Platform RPC Method
************************************


If an agent in one platform wants to use an exported RPC method of an agent in another platform, it has to provide the
platform name of the remote platform when using RPC subsystem call/notify method.

Here is an example:

.. code:: python

    self.vip.rpc.call(peer, 'say_hello', 'Bob', external_platform='platform2').get()
    self.vip.rpc.notify(peer, 'ready', external_platform='platform2')

Here, 'platform2' is the platform name of the remote platform.
