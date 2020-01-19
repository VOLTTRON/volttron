.. _ProcessAgent:

Process Agent
=============

This agent can be used to launch non-Python agents in the VOLTTRON
platform. The agent handles keeping track of the process so that it can
be started and stopped with platform commands. Edit the configuration
file to specify how to launch your process.

This agent was originally created for launching sMAP along with the
platform, but can be used for any process.

Note: Currently this agent does not respond to a blanket "shutdown"
request and must be stopped with the "stop" command.
