Remote Procedure Calls
======================

Remote procedure calls (RPC) is a new feature added with VOLTTRON 3.0.
The new VOLTTRON Interconnect Protocol `VIP <VIP>`__ introduced the
ability to create new point-to-point protocols, called subsystems,
enabling the implementation of `JSON-RPC
2.0 <http://www.jsonrpc.org/specification>`__. This provides a simple
method for agent authors to write methods and expose or export them to
other agents, making request-reply or notify communications patterns as
simple as writing and calling methods.

Exporting Methods
-----------------

The *export()* method, defined on the RPC subsystem class, is used to
mark a method as remotely accessible. This *export()* method has a dual
use. The class method can be used as a decorator to statically mark
methods when the agent class is defined. The instance method dynamically
exports methods, and can be used with methods not defined on the agent
class. Each take an optional export name argument, which defaults to the
method name. Here are the two export method signatures:

Instance method:

.. code:: python

    RPC.export(method, name=None)

Class method:

::

    RPC.export(name=None)

And here is an example agent definition using both methods:

.. code:: python

    from volttron.platform.vip import Agent, Core, RPC

    def add(a, b):
        '''Add two numbers and return the result'''
        return a + b


    class ExampleAgent(Agent):
        @RPC.export
        def say_hello(self, name):
            '''Build and return a hello string'''
            return 'Hello, %s!' % (name,)

        @RPC.export('say_bye')
        def bye(self, name):
            '''Build and return a goodbye string'''
            return 'Goodbye, %s.' % (name,)

        @Core.receiver('setup')
        def onsetup(self, sender, **kwargs):
            self.vip.rpc.export('add')

Calling exported methods
------------------------

The RPC subsystem provides three methods for calling exported RPC
methods.

.. code:: python

    RPC.call(peer, method, *args, **kwargs)

Call the remote *method* exported by *peer* with the given arguments.
Returns a gevent *AsyncResult* object.

.. code:: python

    RPC.batch(peer, requests)

Batch call remote methods exported by *peer*. *requests* must be an
iterable of 4-tuples *(notify, method, args, kwargs)*, where *notify* is
a boolean indicating whether this is a notification or standard call,
*method* is the method name, *args* is a list and *kwargs* is a
dictionary. Returns a list of *AsyncResult* objects for any standard
calls. Returns *None* if all requests were notifications.

.. code:: python

    RPC.notify(peer, method, *args, **kwargs)

Send a one-way notification message to *peer* by calling *method*
without without returning a result.

Here are some examples:

.. code:: python

    self.vip.rpc.call(peer, 'say_hello', 'Bob').get()
    results = self.vip.rpc.batch(peer, [(False, 'say_bye', 'Alice', {}), (True, 'later', [], {})])
    self.vip.rpc.notify(peer, 'ready')

Inspection
----------

A list of methods is available by calling the *inspect* method.
Additional information can be returned for any method by appending
'.inspect' to the method name. Here are a couple examples:

.. code:: python

    self.vip.rpc.call(peer, 'inspect')   # Returns a list of exported methods
    self.vip.rpc.call(peer, 'say_hello.inspect')   # Return metadata on say_hello method

Implementation
--------------

See the
`rpc </VOLTTRON/volttron/blob/3.x/volttron/platform/vip/agent/subsystems/rpc.py>`__
module for implementation details.

Also see `RPC by example <RPC-by-example>`__ for additional examples.
