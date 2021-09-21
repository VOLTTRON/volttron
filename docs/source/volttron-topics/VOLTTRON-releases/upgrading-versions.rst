.. _Upgrading-Versions:

==============================
Upgrading Existing Deployments
==============================

It is often recommended that users upgrade to the latest stable release of VOLTTRON for their deployments.  Major
releases include helpful new features, bug fixes, and other improvements.  Please see the guides below for upgrading
your existing deployment to the latest version.

VOLTTRON 8
==========

VOLTTRON 8 introduces three changes that require an explict upgrade step when upgrading from a earlier VOLTTRON version

    1. Dynamic RPC authorization feature - This requires a modification to the auth file. If you have a pre-existing
       instance of VOLTTRON running on an older version, the auth file will need to be updated.
    2. Historian agents now store the cache database (backup.sqlite file) in
       <volttron home>/agents/<agent uuid>/<agentname-version>/<agentname-version>.agent-data directory instead of
       <volttron home>/agents/<agent uuid>/<agentname-version> directory. In future all core agents will write data only
       to the <agentname-version>.agent-data subdirectory. This is because vctl install --force backs up and restores
       only the contents of this directory.
    3. SQLHistorians (historian version 4.0.0 and above) now use a new database schema where metadata is stored in
       topics table instead of separate metadata table. SQLHistorians with version >= 4.0.0 can work with existing
       database with older schema however the historian agent code should be upgraded to newer version (>=4.0.0) to run
       with VOLTTRON 8 core.

To begin the upgrade process, activate the volttron environment, and run ```python bootstrap.py --force```.

.. note::

    If you have any additional bootstrap options that you need (rabbitmq, web, drivers, etc.)
    include these in the above command.

After the bootstrap process is completed, run ```volttron-upgrade``` to update the auth file and move historian
cache files into agent-data directory. Note that the upgrade script will only move the backup.sqlite file and will not
move sqlite historian's db file if they are within the install directory. If using a SQLite historian, please backup
the database file of sqlite historian before upgrading to the latest historian version.

Once the volttron-upgrade script is complete, you can do a vctl install --force command to upgrade to the latest
historian version. vctl install --force will backup the cache in <agent-version>.agent-data folder, install the latest
version of the historian and restore the contents of <agent-version>.agent-data folder.

Upgrading aggregate historians
------------------------------

VOLTTRON 8 also comes with updated SQL aggregate historian schema. However, there is no automated upgrade path for
aggregate historian. To upgrade an existing aggregate historian please refer to the CHANGELOG.md within
SQLAggregateHistorian source directory

VOLTTRON 7
==========

VOLTTRON 7 includes a migration from Python 2.7 to Python 3.6, as well as security features, new agents, and more.

From 6.x
--------

From version 6.x to 7.x important changes have been made to the virtual environment as well as :term:`VOLTTRON_HOME`.
Take the following steps to upgrade:

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

#.  Make necessary `VOLTTRON_HOME` changes


    .. warning::

        It is possible that some existing agents may continue to operate after the platform upgrade, however this is not
        true for most agents, and it is recommended to reinstall the agent to ensure the agent wheel is compatible and
        that there are no side-effects.

    A.  Reinstall Agents

    It is recommended to reinstall all agents that exist on the platform to ensure the agent wheel is compatible with
    Python3 VOLTTRON.  In many cases, the configurations for version 7.x are backwards compatible with 6.x, requiring no
    additional changes from the user.  For information on individual agent configs, please read through that agent's
    documentation.

    B.  Modify Agent Directories

    .. note::

        Modifying the agent directories is only necessary if not reinstalling agents.

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

        .. warning::

            If not specifying a path to the database, the database will be created in the agent's data directory.  This
            is important if removing or uninstalling the historian as the database file will be removed when the agent
            dir is cleaned up.  Copy the database file to a temporary directory, reinstall the agent, and move the
            database file back to the agent's data directory

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
