.. _AgentManagement:

Agent Lifecyle Management
~~~~~~~~~~~~~~~~~~~~~~~~~

The VOLTTRON platform has several commands for controlling the lifecycle
of agents. This page discusses how to use them, for details of operation
please see :ref:`PlatformConfiguration <PlatformConfiguration>`

.. note::

    These examples assume the VOLTTRON environment has been activated.

    ``source env/bin/activate``

Agent Packaging
===============

The "volttron-pkg" command is used for packaging and configuring agents.
It is not necessary to have the platform running to use this command.
The platform uses `Python Wheel <https://pypi.python.org/pypi/wheel>`__
for its packaging and follows the Wheel naming
`convention <http://legacy.python.org/dev/peps/pep-0427/#file-name-convention>`__.

To create an agent package, call ``volttron-pkg <Agent Dir>``.

.. note::

    The agent directory must contain a properly formatted setup.py file.

For instance: ``volttron-pkg package examples/ListenerAgent``

The ``package`` command uses the setup.py in the agent directory to
create the package. The name and version number portion of the Wheel
filename come from this. The resulting wheels are created at
"~/.volttron/packaged".

For example:
``~/.volttron/packaged/listeneragent-3.0-py2-none-any.whl``.

Agent Configuration
===================

Agent packages are configured with the
``volttron-pkg configure <AgentPackage> <ConfigFile>`` command. It is
suggested that this file use either yaml or json formatting but the agent can be
written to interpret any format it requires. The configuration of a
particular agent is opaque to the VOLTTRON platform. The location of the
agent config file is passed as an environmental variable "AGENT\_CONFIG"
which the provided utilities read in and pass to the agent.

An example config file passing in some parameters:

.. code:: YAML

    # YAML based configuration file
    agentId: listener1
    message: hello


.. code:: JSON

    # JSON based configuration file
    {

        "agentid": "listener1",
        "message": "hello"    
    }

Agent Installation and Removal
==============================

| Agents are installed into the platform using:
``volttron-ctl install <package>``.
| When agents are installed onto a platform, it creates a uuid for that
instance of an agent. This allows multiple instances of the same agent
package to be installed on the platform.

Agents can also be installed with a :ref:`tag <AgentTag>` by using:

``volttron-ctl install <TAG>=<PACKAGE>``

This allows the user to refer to the agent with "--tag " instead of the
uuid when issuing commands. This tag can also distinguish instances of
an agent from each other.

A stopped agent can be removed with:

-  ``volttron-ctl remove <AGENT_UUID>``
-  ``volttron-ctl remove --tag <AGENT_TAG>``
-  ``volttron-ctl remove --name <AGENT_NAME>``

Removal by tag and name potentially allows multiple agents to be removed
at once and should be used with caution. A "-f" option is required to
delete more than one agent at a time.

Agent Control
=============

Starting and Stopping an Agent
------------------------------

Agent that are installed in the platform can be launched with the
"start" command. By default this operates off the agent's UUID but can
be used with "--tag" or "--name" to launch agents by those attributes.
This can allow multiple agents to be started at once. For instance:
``volttron-ctl start --name myagent-0.1`` would start all instances of
that agent regardless of their uuid, tag, or configuration information.
After an agent is started, it will show up in
:ref:`AgentStatus <AgentStatus>` as "running" with a process id.

Similarly, ``volttron-ctl stop <UUID>`` can also operate off the tag and
name of agent(s). After an agent is stopped, it will show an exit code
of 0 in :ref:`AgentStatus <AgentStatus>`

Agent Status
============

| ``volttron-ctl list`` lists the agents installed on the platform and
their priority
| The ``volttron-ctl status`` shows the list of installed agents and
whether they are running or have exited.
| See :ref:`AgentStatus <AgentStatus>` for more details.
