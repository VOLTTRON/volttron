.. _DDS-Agent:

=========
DDS Agent
=========

The DDS example agent demonstrates VOLTTRON's capacity to be extended with tools and libraries not used in the core
codebase. DDS is a messaging platform that implements a publish-subscribe system for well defined data types.

This agent example is meant to be run the command line, as opposed to installing it like other agents.  From the
`examples/DDSAgent` directory, the command to start it is:

.. code-block:: shell

   $ AGENT_CONFIG=config python -m ddsagent.agent

The `rticonnextdds-connector` library needs to be installed for this example to function properly.  We'll retrieve it
from GitHub since it is not available through Pip. Download the source with:

.. code-block:: shell

   $ wget https://github.com/rticommunity/rticonnextdds-connector/archive/master.zip

and unpack it in `examples/DDSAgent/ddsagent` with:

.. code-block:: shell

   $ unzip master.zip

The ``demo_publish()`` output can be viewed with the `rtishapesdemo` available from RTI.


Configuration
-------------

Each data type that this agent will have access to needs to have an XML document defining its structure.  The XML will
include a participant name, publisher name, and a subscriber name.  These are recorded in the configuration with the
location on disk of the XML file.

.. code-block:: json

   {
       "square": {
           "participant_name": "MyParticipantLibrary::Zero",
           "xml_config_path": "./ddsagent/rticonnextdds-connector-master/examples/python/ShapeExample.xml",
           "publisher_name": "MyPublisher::MySquareWriter",
           "subscriber_name": "MySubscriber::MySquareReader"
       }
   }
