.. _Upgrading-Versions:

==============================
Upgrading Existing Deployments
==============================

It is often recommended that users upgrade to the latest stable release of VOLTTRON for their deployments.  Major
releases include helpful new features, bug fixes, and other improvements.  Please see the guides below for upgrading
your existing deployment to the latest version.


VOLTTRON 7
==========

VOLTTRON 7 includes a migration from Python 2.7 to Python 3.6, as well as security features, new agents, and more.

From 6.x
--------

From version 6.x to 7.x important changes have been made to the virtual environment as well as `VOLTTRON_HOME`.  Take
the following steps to upgrade:

.. note::

    The following instructions are for debian based Linux distributions (including Ubuntu and Linux Mint).  For Red Hat,
    Arch or other distributions, please use the corresponding package manager and commands.

#.  Install the VOLTTRON dependencies using the following command:

    .. code-block:: bash

        sudo apt install python3-dev python3-venv libffi-dev

    .. note::

        This assumes you have existing 6.x dependencies installed.  If you're unsure, refer to the
        :ref:`platform installation <Platform-Installation>` instructions.

#.  Remove your existing virtual environment and run the bootstrap process.

    To remove the virtual environment, change directory to the VOLTTRON project root and run the `rm` command with the
    ``-r`` option.

    .. code-block:: bash

        cd $VOLTTRON_ROOT/
        rm -r env

    Now you can use the included `bootstrap.py` script to set up the new virtual environment.  For information on how
    to install dependencies for VOLTTRON integrations, run the script with the ``--help`` option.

    .. code-block:: bash

        python3 bootstrap.py <options>

    .. note::

        Because the new environment uses a different version of Python, using the ``--force`` option with bootstrap will
        throw errors.  Please follow the above instructions when upgrading.

#.  Make necessary VOLTTRON_HOME changes

    A.  Reinstall Agents

    It is recommended to reinstall all agents that exist on the platform to ensure the agent wheel is compatible with
    Python3 VOLTTRON.  In many cases, the configurations for version 7.x are backwards compatible with 6.x, requiring no
    additional changes from the user.  For information on individual agent configs, please read through that agent's
    documentation.

    B.  Modify Agent Directories

    To satisfy the security requirements of the secure agents feature included with VOLTTRON 7, changes have been made
    to the agent directory structure.

        1. Keystore.json

        The agent keystore file has been moved from the agent's `agent-data` directory to the agent's `dist-info`
        directory.  To move the file, change directory to the agents install directory and use the `mv` command.

        .. code-block:: bash

            cd $VOLTTRON_HOME/agents/<agent uuid>/<agent dir>
            mv <agent>agent.agent-data/keystore.json <agent>agent.dist-info/

        2. Historian Database

        Historians with a local database file have had their default location change do the `data` directory inside of
        the agent's install directory.  It is recommended to relocate the file from $VOLTTRON_HOME/data to the agent's
        data directory.  Alternatively, a path can be used if the user the agent is run as (the VOLTTRON user for
        deployments not using the secure agents feature) has read-write permissions for the file.

        .. code-block:: bash

            mv $VOLTTRON_HOME/data/historian.sqlite $VOLTTRON_HOME/agents/<agent uuid>/<agent>/data

#.  Forward Historian

    For deployments which are passing data from 6.x VOLTTRON to the latest 7.x release, some users will experience
    timeout issues with the Forward Historian.  By updating the 6.x deployment to the latest from the releases/6.x
    branch, and restarting the platform and forwarder, this issue can be resolved.

    .. code-block:: bash

        . env/bin/activate
        ./stop-volttron
        git pull
        git checkout releases/6.x
        ./start-volttron
        vctl start <forward id or tag>
