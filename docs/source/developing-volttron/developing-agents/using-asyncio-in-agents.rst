.. _Using-Asyncio-In-Agents:

=======================
Using Asyncio in Agents
=======================

The purpose of this section to is to show how to use Asyncio with Gevent within the Agent development framework.

Before we dive into the example, we establish the following concepts:

* An Event Loop is a software design pattern that handles events concurrently; it waits for and dispatches multiple events concurrently and gives the illusion of executing the events in "parallel". In Python, the `Event Loop <https://docs.python.org/3.10/library/asyncio-eventloop.html#event-loop>`_ contains a list of Tasks which controls when and how those Tasks are executed.

* A `Task <https://docs.python.org/3/library/asyncio-task.html#task-object>`_ is an object that runs a `coroutine <https://docs.python.org/3/library/asyncio-task.html#coroutine>`_ (i.e. asynchronous function). In Python, coroutines are written using the 'async' keyword.

* A `Greenlet <https://greenlet.readthedocs.io/en/latest/#instantiation>`_ is a "lightweight coroutine for in-process sequential concurrent programming. Greenlets can be used on their own, but they are frequently used with frameworks such as gevent to provide higher-level abstractions and asynchronous I/O.

* Asyncio is a built-in Python module that allows the developer to write concurrent code.

* Gevent is a "coroutine-based Python networking library that uses greenlet to provide a high-level synchronous API on top of the libev or libuv event loop".

* VOLTTRON predates the inclusion of asyncio in python and therefore uses gevent for its base.

The general steps to use Asyncio within the Volttron Agent framework are the following:

1. Create an async method.
2. Create a method which creates and starts the Asyncio Event Loop.
3. Use gevent.spawn (or spawn_later) to start a greenlet using the method in step 2.

Below are code examples of how to implement the steps within an agent. For demonstration purposes, we name this agent, ExampleAsyncioAgent.

Step 1: Create an async method.

.. code-block:: python

    class ExampleAsyncioAgent(Agent):

        # This is the async method.
        async def handle_event(self, event):
            ...
            # releases control so other coroutines can run.
            await asyncio.sleep(1)
            return "hello!"


Step 2. Create a method which creates and starts the Asyncio Event Loop.

.. code-block:: python

    class ExampleAsyncioAgent(Agent):

        # This is a wrapper method that is self contained for launching from gevent.
        def _start_asyncio_loop(self):
            loop = asyncio.get_event_loop()
            loop.create_task(self.handle_event)
            loop.run_forever()


Step 3. Create a method that will spawn a Greenlet and then run the Event Loop that was created in the previous step within the Greenlet.

.. code-block:: python

    class ExampleAsyncioAgent(Agent):

        @Core.receiver('onstart')
        def onstart(self, sender, **kwargs):

            # Spawn greenlet in 3 seconds, use self._start_asyncio_loop as a callback for executing
            # the greenlet
            gevent.spawn_later(3, self._start_asyncio_loop)


To review, below is the complete agent class with all the relevant and aforementioned codeblocks:

.. code-block:: python

    import gevent
    import asyncio

    class ExampleAsyncioAgent(Agent):

        @Core.receiver("onstart")
        def onstart(self, sender, **kwargs):
            gevent.spawn_later(3, self._start_asyncio_loop)

        def _start_asyncio_loop(self):
            loop = asyncio.get_event_loop()
            loop.create_task(self.ven_client.run())
            loop.run_forever()

        async def handle_event(self, event):
            # do things that include a blocking call
            ...

            await asyncio.sleep(1)
            return "hello!"


References

* `Python Asyncio Primer <https://builtin.com/data-science/asyncio-python>`_

* `Python Asyncio documentation <https://docs.python.org/3.10/library/asyncio.html>`_

* `Gevent documentation <http://www.gevent.org/>`_
