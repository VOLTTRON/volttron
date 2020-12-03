.. _Running-Agents-as-Unix-User:

============================
Running Agents as Unix Users
============================

This VOLTTRON feature will cause the platform to create a new, unique Unix user(agent users) on the host machine for
each agent installed on the platform.  This user will have restricted permissions for the file system, and will be used
to run the agent process.

.. warning::

    The Unix user starting the VOLTTRON platform will be given limited sudo access to create and delete agent users.

Since this feature requires system level changes (e.g. sudo access, user creation, file permission changes), the initial
step needs to be run as root or user with `sudo` access.  This can be a user other than Unix user used to run the
VOLTTRON platform.

All files and folder created by the VOLTTRON process in this mode would not have any access to others by default.
Permission for Unix group others would be provided to specific files and folder based on VOLTTRON process requirement.

It is recommended that you use a new :term:`VOLTTRON_HOME` to run VOLTTRON in secure mode.  Converting a existing
VOLTTRON instance to secure mode is also possible but would involve some manual changes.  Please see the section
`Porting existing volttron home to secure mode`_.

.. note::

    VOLTTRON has to be bootstrapped as prerequisite to running agents as unique users.


Setup agents to run using unique users
======================================

1. **This feature requires acl to be installed.**

   Make sure the `acl` library is installed.  If you are running on a Docker image `acl` might not be installed by
   default.

   .. code-block:: bash

      apt-get install acl

2. Agents now run as a user different from VOLTTRON platform user.  Agent users should have `read` and `execute`
   permissions to all directories in the path to the Python executable used by VOLTTRON.  For example, if VOLTTRON is
   using a virtual environment, then agent users should have *read* permissions to `<ENV_DIR>/bin/python` and *read
   and execute* permission to all the directories in the path `<ENV_DIR>/bin`.  This can be achieved by running:

   .. code-block:: bash

      chmod -R o+rx <ENV_DIR>/bin

3. **Run scripts/secure_user_permissions.sh as root or using sudo**

   This script *MUST* be run as root or using `sudo`.  This script gives the VOLTTRON platform user limited `sudo`
   access to create a new Unix user for each agent.  All users created will be of the format `volttron_<timestamp>`.

   This script prompts for:

   a. **volttron platform user** - Unix user who would be running the VOLTTRON platform.  This should be an existing
      Unix user.  On a development machine this could be the Unix user you logged in as to check out VOLTTRON source

   b. **VOLTTRON_HOME directory** - The absolute path of the volttron home directory.

   c. **Volttron instance name if VOLTTRON_HOME/config does not exist** -
     
      If the `VOLTTRON_HOME/config` file exists then instance name is obtained from that config file.  If not, the user
      will be prompted for an instance name.  `volttron_<instance_name>` *MUST* be a 23 characters or shorter containing
      only characters valid as Unix user names.

   This script will create necessary entries in `/etc/sudoers.d/volttron` to allow the VOLTTRON platform user to create
   and delete agent users, the VOLTTRON agent group, and run any non-sudo command as the agent users.
   
   This script will also create `VOLTTRON_HOME` and the config file if given a new VOLTTRON home directory when
   prompted.

4. **Continue with VOLTTRON bootstrap and setup as normal** - point to the `VOLTTRON_HOME` that you provided in step 2.

5. **On agent install (or agent start for existing agents)** - a unique agent user(Unix user) is created and the agent
   is started as this user.  The agent user name is recorded in `USER_ID` file under the agent install directory
   (`VOLTTRON_HOME/agents/<agent-uuid>/USER_ID`).  Subsequent agent restarts will read the content of the `USER_ID` file
   and start the agent process as that user.

6. **On agent uninstall** - The agent user is deleted and the agent install directory is deleted.


Creating new Agents
===================

In this secure mode, agents will only have read write access to the agent-data directory under the agent install
directory - `VOLTTRON_HOME/agents/<agent_uuid>/<agent_name>/<agent_name>.agent-data`. Attempting to write in any other
folder under `VOLTTRON_HOME` **will result in permission errors**.


Changes to existing agents in secure mode
=========================================

Due to the above change, **SQL historian has been modified to create its database by default under its agent-data
directory** if no path is given in the config file.  If providing a path to the database in the config file, please
provide a directory where agent will have write access.  This can be an external directory for which agent user
(`recorded in VOLTTRON_HOME/agents/<agent-uuid>/USER_ID`) has *read, write, and execute* access.


Porting existing VOLTTRON home to secure mode
=============================================

When running `scripts/secure_users_permissions.sh` you will be prompted for a `VOLTTRON_HOME` directory.  If this
directory exists and contains a volttron config file, the script will update the file locations and permissions of
existing VOLTTRON files including installed directories.  However this step has the following limitations:

#. **You will NOT be able to revert to insecure mode once the changes are done.** - Once setup is complete, changing the
   config file manually to make parameter `secure-agent-users` to `False`, may result inconsistent VOLTTRON behavior
#. The VOLTTRON process and all agents have to be restarted to take effect
#. **Agents can only to write to its own agent-data dir.** - If your agents writes to any directory outside
   `$VOLTTRON_HOME/agents/<agent-uuid>/<agent-name>/agent-name.agent-data` move existing files and update the agent
   configuration such that the agent writes to the `agent-name.agent-data` dir.  For example, if you have a
   `SQLHistorian` which writes a `.sqlite` file to a subdirectory under `VOLTTRON_HOME` that is not
   `$VOLTTRON_HOME/agents/<agent-uuid>/<agent-name>/agent-name.agent-data` this needs to be manually updated.

