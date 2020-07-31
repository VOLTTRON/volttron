.. _Agent-Autostart:

Agent Autostart
===============

An agent can be setup to start when the platform is started with the
"enable" command. This command also allows a priority to be set (0-100,
default 50) so that agents can be started after any dependencies. This
command can also be used with the --tag or --name options.

``vctl enable <AGENT_UUID> <--priority PRIORITY>``
