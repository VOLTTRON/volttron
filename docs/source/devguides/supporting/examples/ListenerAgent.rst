.. _ListenerAgent:

ListenerAgent
-------------

The ListenerAgent subscribes to all topics and is useful for testing
that agents being developed are publishing correctly. It also provides a
template for building other agents as it expresses the requirements of a
platform agent.

Explanation of ListenerAgent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :code:`utils` to setup logging, which we’ll use later.

.. code-block:: python

    utils.setup_logging()
    _log = logging.getLogger(__name__)


The Listener agent extends (inherits from) the Agent class for its
default functionality such as responding to platform commands:

.. code-block:: python

    class ListenerAgent(Agent):
        '''Listens to everything and publishes a heartbeat according to the
        heartbeat period specified in the settings module.
        '''

After the class definition, the Listener agent reads the configuration
file, extracts the configuration parameters, and initializes any
Listener agent instance variable. This is done through the agent's :code:`__init__`
method:

.. code-block:: python

    def __init__(self, config_path, **kwargs):
        super(ListenerAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config.get('agentid', DEFAULT_AGENTID)
        log_level = self.config.get('log-level', 'INFO')
        if log_level == 'ERROR':
            self._logfn = _log.error
        elif log_level == 'WARN':
            self._logfn = _log.warn
        elif log_level == 'DEBUG':
            self._logfn = _log.debug
        else:
            self._logfn = _log.info

Next, the Listener agent will run its setup method. This method is
tagged to run after the agent is initialized by the decorator
``@Core.receiver('onsetup')``. This method accesses the configuration
parameters, logs a message to the platform log, and sets the agent ID.

.. code-block:: python

    @Core.receiver('onsetup')
    def onsetup(self, sender, **kwargs):
        # Demonstrate accessing a value from the config file
        _log.info(self.config.get('message', DEFAULT_MESSAGE))
        self._agent_id = self.config.get('agentid')

The Listener agent subscribes to all topics published on the message
bus. Publish and subscribe interactions with the message bus are handled by
the PubSub module located at:

    ``~/volttron/volttron/platform/vip/agent/subsystems/pubsub.py``

The Listener agent uses an empty string to subscribe to all messages
published. This is done in a
`decorator <http://en.wikipedia.org/wiki/Python_syntax_and_semantics#Decorators>`__
for simplifying subscriptions.

It also checks for the sender being ``pubsub.compat`` in case there are
any VOLTTRON 2.0 agents running on the platform.

.. code-block:: python

    @PubSub.subscribe('pubsub', '')
    def on_match(self, peer, sender, bus,  topic, headers, message):
        '''Use match_all to receive all messages and print them out.'''
        if sender == 'pubsub.compat':
            message = compat.unpack_legacy_message(headers, message)
        self._logfn(
        "Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
        "Message: %r", peer, sender, bus, topic, headers, message)


