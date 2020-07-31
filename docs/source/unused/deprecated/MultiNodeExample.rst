Multinode Example
=================

The MultiNode example agent demonstrates how to setup and make use of
the [[MultiBuildingMessaging]] agent.

For convenience, this example is setup to be run from a single machine
but could be easily modified to run off multiple systems. Multiple
instances of VOLTTRON can be run on a single machine with the proper
configuration. For this example, two separate VOLTTRON homes are setup
and the MultiBuilding service binds to different local addresses.
[[PlatformConfiguration]] shows how the VOLTTRON\_HOME is used for
platform directories.

The example agent directory contains the config files for the example
agents and the multibuilding agents. Each is setup to know about the
other platform instance and contains its own pub and sub addresses.
Please see [[MultiBuildingMessaging]] for details on the configuration
file.

MultiBuilding config:

::

    {
        "building-publish-address": "tcp://127.0.0.1:12201",
        "building-subscribe-address": "tcp://127.0.0.1:12202",
        "uuid": "MultiBuildingService",
        "hosts": {
            "campus/platform1": {
                "pub": "tcp://127.0.0.1:12201",
                "sub": "tcp://127.0.0.1:12202"
            },
            "campus/platform2": {
                "pub": "tcp://127.0.1.1:12201",
                "sub": "tcp://127.0.1.1:12202"
            }
        }
    }

Each GreeterAgent is setup with the other hosts it will be publishing to
in the publish\_heartbeat method.

GreeterAgent config:

::

    {
         "agentid": "Greeter1",
         "receiving_platforms": ["platform2"]
    }

In order to run this example:

-  First activate the platform:

   ::

       . env/bin/activate

-  Then, create the directories which will be used by each platform as
   its VOLTTRON\_HOME:

   ::

       mkdir ~/.platform1
       mkdir ~/.platform2

-  Start the first platform:

   ::

       VOLTTRON_HOME=~/.platform1 volttron -vv -l platform1.log&

-  Build, configure, and install the multibuilding platform agent. The
   Agent is installed with "multinode=" to tag the agent at the same
   time it is installed. This is a convenient way to refer to the agent
   later.

   ::

       VOLTTRON_HOME=~/.platform1 volttron-pkg package Agents/MultiBuilding
       VOLTTRON_HOME=~/.platform1 volttron-pkg configure ~/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl Agents/MultiNodeExample/multicomm.service
       VOLTTRON_HOME=~/.platform1 volttron-ctl install multinode=~/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl

-  Build, configure, and install the GreeterAgent

   ::

       VOLTTRON_HOME=~/.platform1 volttron-pkg package Agents/MultiNodeExample
       VOLTTRON_HOME=~/.platform1 volttron-pkg configure ~/.volttron/packaged/greeteragent-0.1-py2-none-any.whl Agents/MultiNodeExample/agent1.config
       VOLTTRON_HOME=~/.platform1 volttron-ctl install greeter=~/.volttron/packaged/greeteragent-0.1-py2-none-any.whl

-  Start the second platform:

   ::

       VOLTTRON_HOME=~/.platform2 volttron -vv -l platform2.log&

-  Build, configure, and install the MultiBuilding service for the
   second platform

   ::

       VOLTTRON_HOME=~/.platform2 volttron-pkg package Agents/MultiBuilding
       VOLTTRON_HOME=~/.platform2 volttron-pkg configure ~/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl Agents/MultiNodeExample/multicomm2.service
       VOLTTRON_HOME=~/.platform2 volttron-ctl install multinode=~/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl

-  Build, configure, and install the GreeterAgent for the second
   platform

   ::

       VOLTTRON_HOME=~/.platform2 volttron-pkg package Agents/MultiNodeExample
       VOLTTRON_HOME=~/.platform2 volttron-pkg configure ~/.volttron/packaged/greeteragent-0.1-py2-none-any.whl Agents/MultiNodeExample/agent2.config
       VOLTTRON_HOME=~/.platform2 volttron-ctl install greeter=~/.volttron/packaged/greeteragent-0.1-py2-none-any.whl

-  Start up the agents on both platforms by referring to them by the tag
   they were installed with

   ::

       VOLTTRON_HOME=~/.platform1 volttron-ctl start --tag multinode
       VOLTTRON_HOME=~/.platform1 volttron-ctl start --tag greeter
       VOLTTRON_HOME=~/.platform2 volttron-ctl start --tag multinode
       VOLTTRON_HOME=~/.platform2 volttron-ctl start --tag greeter

-  Check the logs for each platform for the presence of messages from
   the other platform's GreeterAgent

   ::

       grep Greeter2 platform1.log -a

   ``2014-09-30 17:13:41,840 (greeteragent-0.1 13878) greeter.agent DEBUG: Topic: greetings/hello, Headers: Headers({u'Date': u'2014-10-01 00:13:41.831539Z', u'Cookie': u'Greeter2', u'AgentID': u'Greeter2', u'Content-Type': [u'application/json']}), Message: ['{"message":"HELLO from Greeter2!"}']``

   ::

       grep Greeter1 platform2.log -a


