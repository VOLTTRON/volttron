.. _Scripts:

Scripts
=======

In order to make repetitive tasks less repetitive the VOLTTRON team has
create several scripts in order to help. These tasks are available in
the scripts directory. Before using these scripts you should become
familiar with the :ref:`Agent Development <Agent-Development>` process.

In addition to the scripts directory, the VOLTTRON team has added the
config directory to the .gitignore file. By convention this is where we
store customized scripts and configuration that will not be made public.
Please feel free to use this convention in your own processes.

The scripts/core directory is laid out in such a way that we can build
scripts on top of a base core. For example the scripts in sub-folders
such as the historian-scripts and demo-comms use the scripts that are
present in the core directory.

The most widely used script is scripts/install-agent.py. The
install_agent.py script will remove an agent if the tag is already
present, create a new agent package, and install the agent to
VOLTTRON\_HOME. This script has three required arguments and has the
following signature:

::

    # Agent to Package must have a setup.py in the root of the directory.
    scripts/install_agent.py <Agent to Package> <Config file> <Tag>

The install_agent.py script will respect the VOLTTRON\_HOME specified on
the command line or set in the global environment. An example of setting
VOLTTRON\_HOME is as follows.

::

    # Sets VOLTTRON_HOME to /tmp/v1home 
    VOLTTRON_HOME=/tmp/v1home scripts/core/pack_install.sh <Agent to Package> <Config file> <Tag>
