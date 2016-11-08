Ping Pong Agent
===============


The PingPongAgent demonstrates how to use the mobility feature within
VOLTTRON. This simple agent moves back and forth between two VOLTTRON
platforms. The agent will update a "count" file each time it moves to
demonstrate the carrying of data along the agents journey. This agent
code is available in:

examples/PingPongAgent directory of the VOLTTRON platform.

**NOTE: In order for this agent to be successfully used the
VOLTTRON-Restricted package must be installed and enabled. For
information on this package see `VOLTTRON™
Restricted <Volttron-Restricted>`__.**

Configuration for the PingPongAgent
-----------------------------------

The PingPongAgent requires that the VOLTTRON-Restricted module be
installed and that the mobility feature has been enabled (creation of
keys to verify authorization for communication between platforms). For
instructions on enabling the mobility feature, creating security keys,
and adding these keys for communication with other authorized platforms,
please see `Agent Mobility <Agent%20Mobility>`__ section.

The ping pong agent requires hosts and how often a request to move
should be sent. Within the host list add the IP for the two VOLTTRON
platforms and how often to move the agent from one platform to the
other. The configuration file should appear similar to this example:

Typical file location: ~/volttron/examples/PingPongAgent/config.json

::

    {
    "hosts": ["1xx.x.x.1", "1yy.y.y.1"],
    "period": 30
    }

Packaging and launching the PingPongAgent
-----------------------------------------

The following steps will show how to sign (VOLTTRON-Restricted agent
verification feature) the PingPongAgent and launch the PingPongAgent.
From a terminal, in the volttron directory, enter the following
commands:

#. Ensure the platform is active:

   ``. env/bin/activate``

#. Ensure that VOLTTRON is running on both platforms. Issue the
   following command on both platforms to start VOLTTRON:

   ``volttron -vv -l volttron.log&``

#. Package the agent:

   ``volttron-pkg package Agents/PingPongAgent``

#. Sign the agent as creator (resource\_contract is a text file
   containing the hardware and software requirements for the agent, see
   `Resource Monitor <Resource%20Monitor>`__):

   ``volttron-pkg sign --creator --contract resource_contract ~/.volttron/packaged/pingpongagent-0.1-py2-none-any.whl``

#. Sign the agent as admin:

   ``volttron-pkg sign --admin ~/.volttron/packaged/pingpongagent-0.1-py2-none-any.whl``

#. Sign the agent as initiator:

   ``volttron-pkg sign --initiator --config-file examples/PingPongAgent/config.json ~/.volttron/packaged/pingpongagent-0.1-py2-none-any.whl``

#. Set the configuration file:

   ``volttron-pkg configure ~/.volttron/packaged/pingpongagent-0.1-py2-none-any.whl examples/PingPongAgent/config.json``

#. Install agent into platform (with the platform running):

   ``volttron-ctl install ~/.volttron/packaged/listeneragent-3.0-py2-none-any.whl``

#. Check volttron status to verify agent is ready to start:

   ``volttron-ctl status``

#. The terminal will have output that looks similar to:

   ::

       AGENT                       TAG STATUS
       1f  pingpongagent-0.1

#. Start the agent (1f is the window above is the unique agent
   identifier. This identifier will only be as long as necessary to
   ensure uniqueness on the running platform):

   ``volttron-ctl start 1f``

#. Verify that agent is running:

   ``volttron-ctl status``

   ::

       AGENT                       TAG STATUS
       1f  pingpongagent-0.1           running [pid]

In the run directory (VOLTTRON\_HOME/run) one will see the incremented
file appear and disappear as the PingPongAgent jumps back and forth
between the two platforms.

PingPongAgent Code Rundown
~~~~~~~~~~~~~~~~~~~~~~~~~~

For completeness the PingPongAgent code is detailed and explained below:

::

    import errno
    import logging
    import os
    import sys

    from volttron.platform.agent import BaseAgent, PublishMixin, periodic
    from volttron.platform.agent import utils, matching

    utils.setup_logging()
    _log = logging.getLogger(__name__)

    def PingPongAgent(config_path, **kwargs):
        '''Agent to demonstrate agent-initiated mobility.

        The agent periodically calculates the next host to visit from the
        hosts list specified in the config file and requests a move.
        '''
            
        config = utils.load_config(config_path)
        period = config.get('period', 30)
        hosts = config['hosts']
        uuid = os.environ['AGENT_UUID']
        
        class Agent(PublishMixin, BaseAgent):

Handle failed move requests from the service bus

::

            @matching.match_glob('platform/move/reply/' + uuid)
            def on_move_fail(self, topic, headers, message, match):
                error, = message
                _log.error('attempt to move %s failed: %s', uuid, error)

Uses a handy periodic decorator to specify that this method should be
called over and over again. Each time the 'move' function is called the
'count' file is updated and a request to go to a different host is sent.
If the request is accepted and the agent is moved then the agent will be
shutdown and removed from the current platform.

::

            @periodic(period)
            def move(self):
                count = 0
                try:
                    file = open('count', 'r')
                except IOError as exc:
                    if exc.errno != errno.ENOENT:
                        _log.error('error opening count file: %s', exc)
                        return
                else:
                    try:
                        count = int(file.read().strip())
                    except ValueError:
                        count = 0
                host = hosts[count % len(hosts)]
                with open('count', 'w') as file:
                    file.write(str(count + 1))

This is where the agent requests the platform to move if this move is
successful the agent.

::

        self.publish('platform/move/request/' + uuid, {}, host)
        Agent.__name__ = 'PingPongAgent'
        return Agent(**kwargs)

Describe the agent to the platform.

::

    def main(argv=sys.argv):
        '''Main method called by the eggsecutable.'''
        try:
            utils.default_main(PingPongAgent,
                               description='Example VOLTTRON™ mobility agent',
                               argv=argv)
        except Exception as e:
            _log.exception('unhandled exception')

    if __name__ == '__main__':
        # Entry point for script
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            pass

