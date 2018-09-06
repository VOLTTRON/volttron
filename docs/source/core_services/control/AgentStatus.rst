.. _AgentStatus:

Agent List Display
~~~~~~~~~~~~~~~~~~

::

      AGENT             IDENTITY     TAG      PRI

    d listeneragent-3.0 listeneragent-3.0_1   30
    2 testeragent-0.1   testeragent-0.1_1

``volttron-ctl list`` shows the agents which have been installed on the
platform along with their uuid, associated `tag <AgentTag>`__, and
`priority <AgentAutostart>`__.

-  uuid is the first column of the display and is displayed as the
   shorted unique portion. Using this portion, agents can be started,
   stopped, removed, etc.
-  AGENT is the "name" of this agent based on the name of the wheel file
   which was installed. Agents can be controlled with this using "--name
   ". Note, if multiple instances of a wheel are installed they will all
   have the same name and can be controlled as a group.
-  `TAG <AgentTag>`__ is a user provided tag which makes it simpler to
   track and refer to agents. Using "--tag " agents can be controlled
   using this
-  PRI is the priority for agents which have been "enabled" using the
   ``volttron-ctl enable`` command. When enabled, agents will be
   automatically started in priority order along with the platform.

Agent Status Display
====================

::

      AGENT                   IDENTITY            TAG                STATUS          HEALTH
    4 listeneragent-3.2       listeneragent-3.2_1 listener           running [2923]  GOOD
    0 master_driveragent-3.2  platform.driver     master_driver      running [2925]  GOOD
    1 sqlhistorianagent-3.6.1 platform.historian  platform_historian running [2924]  GOOD


``volttron-ctl status`` shows a list of all agents installed on the
platform and their current status.

-  uuid is the first column of the display and is displayed as the
   shorted unique portion. Using this portion, agents can be started,
   stopped, removed, etc.
-  AGENT is the "name" of this agent based on the name of the wheel file
   which was installed. Agents can be controlled with this using "--name
   ". Note, if multiple instances of a wheel are installed they will all
   have the same name and can be controlled as a group.
-  `TAG <AgentTag>`__ is a user provided tag which makes it simpler to
   track and refer to agents. Using "--tag " agents can be controlled
   using this
-  STATUS is the current condition of the agent. If the agent is
   currently executing, it has "running" and the process id of the
   agent. If the agent is not running, the exit code is shown.
-  HEALTH indicates the availability of agent functionality. An agent
   will display either "GOOD", "BAD", "STARTING" or "UNKNOWN" given
   its corresponding capacity to perform its specified functions on
   the platform (an agent which is working as expected should display
   "GOOD", and so forth). The various agent types will choose to update
   health differently, and therefore exact display behaviors will vary.

Agent Health Display
====================

::

    {
        "status": "GOOD",
        "last_updated": "2018-09-06T17:44:36.900229+00:00",
        "context": {
            "cache_count": 0,
            "cache_full": false,
            "backlogged": false,
            "publishing": true
        }
    }

``volttron-ctl health [uuid]`` displays the given agent's health object
as in JSON format.

-  "status" is the current condition of the agent. This status is
   identical to the status given by the "volttron-ctl status" command.
-  "last_updated" is an ISO formatted date-time string which represents
   the time at which the agent last updated its health object via the
   health subsystem.
-  "context" refers to the context provided by the agent to the health
   subsystem for managing agent health. Agents are responsible for the
   specification of their context object (the above example output
   features the context object of the platform historian).