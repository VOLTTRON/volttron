Example Agents Overview
=======================

Some example agents are included with the platform to help explore its
features.

-  :ref:`DataPublisher`
-  :ref:`ListenerAgent`
-  :ref:`ProcessAgent`
-  :ref:`SchedulerExampleAgent`
-  :ref:`CAgent`
-  :ref:`DDSAgent`
-  :ref:`CSVHistorian`

More complex agents contributed by other researchers can also be found
in the examples directory. It is recommended that developers new to
VOLTTRON understand the example agents first before diving into the
other agents.

Example Agent Conventions
-------------------------

Some of the example agent classes are defined inside a method, for
instance:

::

    def ScheduleExampleAgent(config_path, **kwargs):
        config = utils.load_config(config_path)
        campus= config['campus']

This allows configuration information to be extracted from an agent
config file for use in topics.

::

            @Pubsub.subscribe('pubsub', DEVICES_VALUE(campus=campus))
            def actuate(self, peer, sender, bus,  topic, headers, message):

