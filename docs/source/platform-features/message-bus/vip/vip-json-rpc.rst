.. _Remote-Procedure-Calls:

======================
Remote Procedure Calls
======================

Remote procedure calls (RPC) is a feature of VOLTTRON Interconnect Protocol :ref:`VIP <VIP-Overview>`.  VIP includes the
ability to create new point-to-point protocols, called subsystems, enabling the implementation of
`JSON-RPC 2.0 <http://www.jsonrpc.org/specification>`_.  This provides a simple method for agent authors to write
methods and expose or export them to other agents, making request-reply or notify communications patterns as
simple as writing and calling methods.


Exporting Methods
=================

The ``export()`` method, defined on the RPC subsystem class, is used to mark a method as remotely accessible. This
``export()`` method has a dual use:

* The class method can be used as a decorator to statically mark methods when the agent class is defined.
* The instance method dynamically exports methods, and can be used with methods not defined on the agent
  class.

Each take an optional export name argument, which defaults to the method name.  Here are the two export method
signatures:

Instance method:

.. code-block:: python

    RPC.export(method, name=None)

Class method:

.. code-block:: python

    RPC.export(name=None)

And here is an example agent definition using both methods:

.. code-block:: python

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
========================

The RPC subsystem provides three methods for calling exported RPC methods:

.. code-block:: python

    RPC.call(peer, method, *args, **kwargs)

Call the remote ``method`` exported by ``peer`` with the given arguments.  Returns a `gevent` `AsyncResult` object.

.. code-block:: python

    RPC.batch(peer, requests)

Batch call remote methods exported by `peer`. `requests` must be an iterable of 4-tuples
``(notify, method, args, kwargs)``, where ``notify`` is a boolean indicating whether this is a notification or standard
call, ``method`` is the method name, ``args`` is a list and ``kwargs`` is a dictionary.  Returns a list of `AsyncResult`
objects for any standard calls.  Returns ``None`` if all requests were notifications.

.. code-block:: python

    RPC.notify(peer, method, *args, **kwargs)

Send a one-way notification message to `peer` by calling `method` without returning a result.

Here are some examples:

.. code-block:: python

    self.vip.rpc.call(peer, 'say_hello', 'Bob').get()
    results = self.vip.rpc.batch(peer, [(False, 'say_bye', 'Alice', {}), (True, 'later', [], {})])
    self.vip.rpc.notify(peer, 'ready')


Inspection
----------

A list of methods is available by calling the `inspect` method.  Additional information can be returned for any method
by appending ``.inspect`` to the method name.  Here are a couple examples:

.. code-block:: python

    self.vip.rpc.call(peer, 'inspect')   # Returns a list of exported methods
    self.vip.rpc.call(peer, 'say_hello.inspect')   # Return metadata on say_hello method


VCTL RPC Commands
~~~~~~~~~~~~~~~~~

There are two rpc subcommands available through vctl, *list* and *code*.

The list subcommand displays all of the agents that have a peer
connection to the instance and which methods are available from
each of these agents.

.. code-block:: console

    vctl rpc list
        config.store
                delete_config
                get_configs
                manage_delete_config
                manage_delete_store
                manage_get
                manage_get_metadata
                manage_list_configs
                manage_list_stores
                manage_store
                set_config
        .
        .
        .

        platform.historian
                get_aggregate_topics
                get_topic_list
                get_topics_by_pattern
                get_topics_metadata
                get_version
                insert
                query
        volttron.central
                get_publickey
                is_registered

If a single agent is specified, it will list all methods available for that agent.

.. code-block:: console

    vctl rpc list platform.historian
        platform.historian
                get_aggregate_topics
                get_topic_list
                get_topics_by_pattern
                get_topics_metadata
                get_version
                insert
                query

If the -v option is selected, all agent subsystem rpc methods will be displayed
for each selected agent as well.

.. code-block:: console

    vctl rpc list -v platform.historian
        platform.historian
                get_aggregate_topics
                get_topic_list
                get_topics_by_pattern
                get_topics_metadata
                get_version
                insert
                query
                agent.version
                health.set_status
                health.get_status
                health.get_status_json
                health.send_alert
                heartbeat.start
                heartbeat.start_with_period
                heartbeat.stop
                heartbeat.restart
                heartbeat.set_period
                config.update
                config.initial_update
                auth.update

If an agent is specified, and then a method (or methods) are specified,
all parameters associated with the method(s) will be output.

.. code-block:: console

    vctl rpc list platform.historian get_version query
        platform.historian
            get_version
            Parameters:
            query
            Parameters:
                topic:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': None}
                start:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': None}
                end:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': None}
                agg_type:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': None}
                agg_period:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': None}
                skip:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': 0}
                count:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': None}
                order:
                        {'kind': 'POSITIONAL_OR_KEYWORD', 'default': 'FIRST_TO_LAST'}


By adding the '-v' option to this stage, the doc-string description
of the method will be displayed along with the method and parameters if available.

.. code-block:: console

    vctl rpc list -v platform.historian get_version
        platform.historian
            get_version
            Documentation:
                RPC call to get the version of the historian

                :return: version number of the historian used
                :rtype: string

            Parameters:

    vctl rpc code
    vctl rpc list <peer identity>
    vctl rpc list <peer identity> <method>
    vctl rpc list -v <peer identity>
    vctl rpc list -v <peer identity> <method>
    vctl rpc code -v
    vctl rpc code <peer identity>
    vctl rpc code <peer identity> <method>

The code subcommand functions similarly to list, except that it will output the code
to be used in an agent when writing an rpc call. Any available parameters are included
as a list in the line of code where the parameters will need to be provided. These will
need to be modified based on the use case.

.. code-block:: console

    vctl rpc code
        self.vip.rpc.call(config.store, delete_config, ['config_name', 'trigger_callback', 'send_update']).get()
        self.vip.rpc.call(config.store, get_configs).get()
        self.vip.rpc.call(config.store, manage_delete_config, ['args', 'kwargs']).get()
        self.vip.rpc.call(config.store, manage_delete_store, ['args', 'kwargs']).get()
        self.vip.rpc.call(config.store, manage_get, ['identity', 'config_name', 'raw']).get()
        self.vip.rpc.call(config.store, manage_get_metadata, ['identity', 'config_name']).get()
        self.vip.rpc.call(config.store, manage_list_configs, ['identity']).get()
        self.vip.rpc.call(config.store, manage_list_stores).get()
        self.vip.rpc.call(config.store, manage_store, ['args', 'kwargs']).get()
        self.vip.rpc.call(config.store, set_config, ['config_name', 'contents', 'trigger_callback', 'send_update']).get()
        .
        .
        .
        self.vip.rpc.call(platform.historian, get_aggregate_topics).get()
        self.vip.rpc.call(platform.historian, get_topic_list).get()
        self.vip.rpc.call(platform.historian, get_topics_by_pattern, ['topic_pattern']).get()
        self.vip.rpc.call(platform.historian, get_topics_metadata, ['topics']).get()
        self.vip.rpc.call(platform.historian, get_version).get()
        self.vip.rpc.call(platform.historian, insert, ['records']).get()
        self.vip.rpc.call(platform.historian, query, ['topic', 'start', 'end', 'agg_type', 'agg_period', 'skip', 'count', 'order']).get()
        self.vip.rpc.call(volttron.central, get_publickey).get()
        self.vip.rpc.call(volttron.central, is_registered, ['address_hash', 'address']).get()

As with rpc list, the code subcommand can be filtered based on the vip identity and/or the method(s).

.. code-block:: console

    vctl rpc code platform.historian
        self.vip.rpc.call(platform.historian, get_aggregate_topics).get()
        self.vip.rpc.call(platform.historian, get_topic_list).get()
        self.vip.rpc.call(platform.historian, get_topics_by_pattern, ['topic_pattern']).get()
        self.vip.rpc.call(platform.historian, get_topics_metadata, ['topics']).get()
        self.vip.rpc.call(platform.historian, get_version).get()
        self.vip.rpc.call(platform.historian, insert, ['records']).get()
        self.vip.rpc.call(platform.historian, query, ['topic', 'start', 'end', 'agg_type', 'agg_period', 'skip', 'count', 'order']).get()

.. code-block:: console

    vctl rpc code platform.historian query
        self.vip.rpc.call(platform.historian, query, ['topic', 'start', 'end', 'agg_type', 'agg_period', 'skip', 'count', 'order']).get()


Implementation
--------------

See the `RPC module <https://github.com/VOLTTRON/volttron/blob/develop/volttron/platform/vip/agent/subsystems/rpc.py>`_
for implementation details.

Also see :ref:`Multi-Platform RPC Communication <Multi-Platform-RPC>` and :ref:`RPC in RabbitMQ <RabbitMQ-VOLTTRON>` for
additional resources.
