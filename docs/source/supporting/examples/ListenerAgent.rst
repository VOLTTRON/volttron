ListenerAgent
-------------

The ListenerAgent subscribes to all topics and is useful for testing
that agents being developed are publishing correctly. It also provides a
template for building other agents as it expresses the requirements of a
platform agent.

Explanation of ListenerAgent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ListenerAgent publishes a heartbeat message so it will use the
PublishMixin. It also extends BaseAgent to get the default
functionality. When creating agents, Mixins should be first in the class
definition.

::

    from __future__ import absolute_import
    from datetime import datetime
    import logging
    import sys

    from volttron.platform.vip.agent import Agent, Core, PubSub, compat
    from volttron.platform.agent import utils
    from volttron.platform.messaging import headers as headers_mod, topics
    from . import settings
    #If developing inside Eclipse, use pydev-launch.py
    # or change this to: import settings

| Use utils to setup logging which we’ll use later.
|  utils.setup\_logging()
|  \_log = logging.getLogger(\ **name**)

The Listener agent extends (inherits from) the Agent class for its
default functionality such as responding to platform commands:

::

    class ListenerAgent(Agent):
        '''Listens to everything and publishes a heartbeat according to the
        heartbeat period specified in the settings module.
        '''

After the class definition, the Listener agent reads the configuration
file, extracts the configuration parameters, and initializes any
Listener agent instance variable. This is done the agents **init**
method:

::

    def __init__(self, config_path, **kwargs):
        super(ListenerAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

Next, the Listener agent will run its setup method. This method is
tagged to run after the agent is initialized by the decorator
@Core.receiver('onsetup'). This method accesses the configuration
parameters, logs a message to the platform log, and sets the agent ID.

::

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        # Demonstrate accessing a value from the config file
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']

| The Listener agent subscribes to all topics published on the message
bus. Subscribe/publish interactions with the message bus are handled by
the PubSub module located at:
| ``~/volttron/volttron/platform/vip/agent/subsystems/pubsub.py``

The Listener agent uses an empty string to subscribe to all messages
published. This is done in a
`decorator <http://en.wikipedia.org/wiki/Python_syntax_and_semantics#Decorators>`__
for simplifying subscriptions.

It also checks for the sender being ``pubsub.compat`` in case there are
any VOLTTRON 2.0 agents running on the platform.

::

    @PubSub.subscribe('pubsub', '')
    def on_match(self, peer, sender, bus,  topic, headers, message):
        '''Use match_all to receive all messages and print them out.'''
        if sender == 'pubsub.compat':
        message = compat.unpack_legacy_message(headers, message)
        _log.debug(
        "Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
        "Message: %r", peer, sender, bus, topic, headers, message)

The Listener agent uses the @Core.periodic decorator to execute the
publish\_heartbeat method every HEARTBEAT\_PERIOD seconds where
HEARTBEAT\_PERIOD is specified in the settings.py file:

::

    @Core.periodic(settings.HEARTBEAT_PERIOD)
    def publish_heartbeat(self):
        '''Send heartbeat message every HEARTBEAT_PERIOD seconds.

        HEARTBEAT_PERIOD is set and can be adjusted in the settings module.
        '''
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
        'AgentID': self._agent_id,
        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
        headers_mod.DATE: now,
        }
        self.vip.pubsub.publish(
        'pubsub', 'heartbeat/listeneragent', headers, now)

vip.pubsub.publish is called with the following arguments:

-  ‘pubsub’ - Always the first argument to vip.pubsub.publish.
-  topic - Topic of message or data. In this example the Listener is
   publishing to the 'heartbeat/listeneragent' topic
-  headers - Contains information such as date published, content type
   (plain text, utf-8, asci, etc), and the agent ID for publishing
   agent.
-  message - Can be a single value (float, integer, or string), list of
   objects, or dictionary. Agents subscribing to the message should know
   the format of message so they can parse and use the information. In
   this example the Listener agent is publishing a string message
   containing the current time (“now”) in UTC ISO format (note: Python
   datetime objects should be converted to strings before passing to
   vip.pubsub.publish).

