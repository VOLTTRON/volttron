.. _Agent-Control-Commands:

======================
Agent Control Commands
======================

The VOLTTRON platform has several commands for controlling the lifecycle of agents.  This page discusses how to use
them, for details of operation please see :ref:`Platform Configuration <Platform-Configuration>`

.. note::

    These examples assume the VOLTTRON environment has been activated

    .. code-block:: bash

        . env/bin/activate

    If not activating the VOLTTRON virtual environment, add "bin/" to all commands


Agent Packaging
===============

The `vpkg` command is used for packaging and configuring agents.  It is not necessary to have the platform running to
use this command.  The platform uses `Python Wheel <https://pypi.python.org/pypi/wheel>`__ for its packaging and follows
the Wheel naming `convention <http://legacy.python.org/dev/peps/pep-0427/#file-name-convention>`__.

To create an agent package, call:

.. code-block:: bash

    vpkg <Agent Dir>

For instance: ``vpkg package examples/ListenerAgent``

The ``package`` command uses the `setup.py` in the agent directory to create the package.  The name and version number
portion of the Wheel filename come from this. The resulting wheels are created at `~/.volttron/packaged`. For example:
``~/.volttron/packaged/listeneragent-3.0-py2-none-any.whl``.


Agent Configuration
===================

Agent packages are configured with:

.. code-block:: bash

    vpkg configure <AgentPackage> <ConfigFile>

It is suggested that this file use JSON formatting but the agent can be written to interpret any format it requires.
The configuration of a particular agent is opaque to the VOLTTRON platform.  The location of the agent config file is
passed as an environmental variable `AGENT_CONFIG` which the provided utilities read in and pass to the agent.

An example config file passing in some parameters:

.. code-block:: json

    {

        "agentid": "listener1",
        "message": "hello"    
    }


Agent Installation and Removal
==============================

Agents are installed into the platform using:

.. code-block:: bash

    vctl install <package>

When agents are installed onto a platform, it creates a uuid for that instance of an agent.  This allows multiple
instances of the same agent package to be installed on the platform.

This allows the user to refer to the agent with ``--tag <tag>`` instead of the uuid when issuing commands.  This tag can
also distinguish instances of an agent from each other.

A stopped agent can be removed with:

-  ``vctl remove <AGENT_UUID>``
-  ``vctl remove --tag <AGENT_TAG>``
-  ``vctl remove --name <AGENT_NAME>``


.. _Agent-Tag:

Tagging Agents
--------------

Agents can be tagged as they are installed with:

``vctl install <TAG>=<AGENT_PACKAGE>``

Agents can be tagged after installation with:

``vctl tag <AGENT_UUID> <TAG>``

Agents can be "tagged" to provide a meaningful user defined way to reference the agent instead of the uuid or the name.
This allows users to differentiate between instances of agents which use the same codebase but are configured
differently.


Example
^^^^^^^

A user installs two instances of the Listener Agent, tagged with `listen1` and `listen2` respectively:

.. code-block:: bash

    python scripts/install-agent.py -s examples/ListenerAgent --tag listener1
    python scripts/install-agent.py -s examples/ListenerAgent --tag listener2

``vctl status`` displays:

.. code-block:: console

      AGENT             IDENTITY            TAG       STATUS          HEALTH
    a listeneragent-3.3 listeneragent-3.3_2 listener2
    6 listeneragent-3.3 listeneragent-3.3_1 listener1

Commands which operate off an agent's UUID can optionally operate off the tag by using "--tag ".  This can use wildcards
to catch multiple agents at once.  For example, ``vctl start --tag listener*`` will start both `listener1` and
`listener2`.

.. warning::

    Removal by tag and name potentially allows multiple agents to be removed at once and should be used with caution.  A
    "-f" option is required to delete more than one agent at a time.


Agent Control
=============

Starting and Stopping an Agent
------------------------------

Agent that are installed in the platform can be launched with the `start` command.  By default this operates off the
agent's UUID but can be used with ``--tag`` or ``--name`` to launch agents by those attributes.

This can allow multiple agents to be started at once. For instance: ``vctl start --name myagent-0.1`` would start all
instances of that agent regardless of their uuid, tag, or configuration information.

After an agent is started, it will show up in :ref:`Agent Status <Agent-Status>` as "running" with a process id.

Similarly, ``volttron-ctl stop <UUID>`` can also operate off the tag and name of agent(s).  After an agent is stopped,
it will show an exit code of 0 in :ref:`Agent Status <Agent-Status>`

Running an agent
----------------

For testing purposes, an agent package not installed in the platform can
be run by using:

.. code-block:: bash

    vctl run <PACKAGE>


.. _Agent-Status:

Agent Status
============

``vctl list`` shows the agents which have been installed on the platform along with their uuid, associated
:ref:`tag <Agent-Tag>` and :ref:`priority <Agent-Autostart>`.

-  `uuid` is the first column of the display and is displayed as the shorted unique portion.  Using this portion, agents
   can be started, stopped, removed, etc.
-  `AGENT` is the "name" of this agent based on the name of the wheel file which was installed.  Agents can be
   controlled with this using ``--name``.

   .. note::

      If multiple instances of a wheel are installed they will all have the same name and can be controlled as a group.

-  IDENTITY is the VIP platform identity assigned to the agent which can be used to make RPC calls, etc. with the
   platform
-  :ref:`TAG <Agent-Tag>` is a user provided tag which makes it simpler to track and refer to agents.  ``--tag <tag>``
   can used in most agent control commands instead of the UUID to control that agent or multiple agents with a pattern.
-  PRI is the priority for agents which have been "enabled" using the ``vctl enable`` command.  When enabled, agents
   will be automatically started in priority order along with the platform.


.. code-block:: console

      AGENT             IDENTITY            TAG          PRI
    a listeneragent-3.3 listeneragent-3.3_2 listener2
    6 listeneragent-3.3 listeneragent-3.3_1 listener1


The ``vctl status`` command shows the list of installed agents and whether they are running or have exited.

.. code-block:: console

      AGENT             IDENTITY            TAG       STATUS          HEALTH
    a listeneragent-3.3 listeneragent-3.3_2 listener2 running [12872] GOOD
    6 listeneragent-3.3 listeneragent-3.3_1 listener1 running [12873] GOOD

- `AGENT`, `IDENTITY` and `TAG` are the same as in the ``vctl list`` command
- `STATUS` is the current condition of the agent.  If the agent is currently executing, it has "running" and the process
  id of the agent.  If the agent is not running, the exit code is shown.
- `HEALTH` represents the current state of the agent.  `GOOD` health is displayed while the agent is operating as
  expected.  If an agent enters an error state the health will display as `BAD`


.. _Agent-Autostart:

Agent Autostart
===============

An agent can be setup to start when the platform is started with the `enable` command.  This command also allows a
priority to be set (0-100, default 50) so that agents can be started after any dependencies. This command can also be
used with the ``--tag`` or ``--name`` options.

.. code-block:: bash

    vctl enable <AGENT_UUID> <PRIORITY>

