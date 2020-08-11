.. _Agent-Status:

Agent List Display
~~~~~~~~~~~~~~~~~~

::

      AGENT             IDENTITY     TAG      PRI

    d listeneragent-3.0 listeneragent-3.0_1   30
    2 testeragent-0.1   testeragent-0.1_1

``vctl list`` shows the agents which have been installed on the
platform along with their uuid, associated `tag <AgentTag>`__, and
`priority <AgentAutostart>`__.

-  uuid is the first column of the display and is displayed as the
   shorted unique portion. Using this portion, agents can be started,
   stopped, removed, etc.
-  AGENT is the "name" of this agent based on the name of the wheel file
   which was installed. Agents can be controlled with this using "--name
   ". Note, if multiple instances of a wheel are installed they will all
   have the same name and can be controlled as a group.
-  `TAG <AgentTag>`__ is a user-provided tag which makes it simpler to
   track and refer to agents. Agents can be controlled by using "--tag".
-  PRI is the priority for agents which have been "enabled" using the
   ``vctl enable`` command. When enabled, agents will be
   automatically started in priority order along with the platform.

Agent Status Display
====================

::

      AGENT             TAG      STATUS

    d listeneragent-3.0 listener running [3813]
    2 testeragent-0.1                 0

``vctl status`` shows a list of all agents installed on the
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

