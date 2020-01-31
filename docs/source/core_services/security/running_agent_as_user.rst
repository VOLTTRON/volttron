.. _Running Agents as unique Unix user:

==============================
Running Agents as unique users
==============================

This VOLTTRON feature will cause the platform to create a new, unique Unix user(agent users)
on the host machine for each agent installed on the platform. This user will
have restricted permissions for the file system, and will be used to run the
agent process. The Unix user starting the volttron platform will be given
limited sudo access to create and delete agent users.

Since this feature require system level changes (sudo access, user creation, file permission changes) the initial step needs to be run as root or user with sudo access. This can be a user other than Unix user used to run volttron platform. 
All files and folder created by volttron process in this mode would by default not have any access to others. Permission for Unix group others would be provided to specific files and folder based on VOLTTRON process requirement. It is recommended that you use a new volttron home to run volttron in secure mode. Converting a existing VOLTTRON instance to secure mode is also possible but would involve some manual changes. Please see section `Porting existing volttron home to secure mode`_.

Setup agents to run using unique users
---------------------------------------

1. **This feature requires acl to be installed.**

   Make sure acl library is installed. If you are running on docker image acl might not be installed by default

   **apt-get install acl**

2. **Run scripts/secure_users_permissions.sh as root or using sudo**

   This script should be run as root or using sudo. This script gives the volttron platform user limited sudo access to create a new unix user for each agent. All users created will be of the format volttron_<timestamp>.

   This script prompts for:

   a. **volttron platform user** - Unix user who would be running VOLTTRON platform

   b. **VOLTTRON_HOME directory** - The absolute path of volttron home directory.

   c. **Volttron instance name if VOLTTRON_HOME/config does not exist** -
     
      If VOLTTRON_HOME/config file exists instance name is got from config file. If not user will be prompted for instance name. volttron_<instance_name> must be a 23 characters or shorter containing only characters valid as Unix user names.

   This script will create necessary entries in /etc/sudoers.d/volttron to allow the volttron platform user to create and delete agent users, Volttron agent group, and run any non-sudo command as agent users. 
   
   This script will also create VOLTTRON_HOME and the config file if given a new volttron home directory when prompted.

3. **Continue with VOLTTRON bootstrap and setup as normal** - point to the VOLTTRON_HOME that you provided in step 2.

4. **On agent install (or agent start for existing agents)** - a unique agent user(Unix user) is created and the agent is started as this user. The agent user name is recorded in USER_ID file under the agent install directory (VOLTTRON_HOME/agents/<agent-uuid>/USER_ID). Subsequent agent restarts will read content of USER_ID file and start the agent process as that user. 

5. **On agent uninstall** - The agent user is deleted and the agent install directory is deleted. 

Creating new Agents
-------------------

In this secure mode, agents will only have read write access to agent-data directory under the agent install directory - VOLTTRON_HOME/agents/<agent_uuid>/<agent_name>/<agent_name>.agent-data. Attempting to write in any other folder under VOLTTRON_HOME will result in permission errors.

Changes to existing agents in secure mode
-----------------------------------------

Due to the above change, **SQL historian has been modified to create its database by default under its agent-data directory** if no path is given in the config file. If providing a path to the database in the config file, please provide a directory where agent will have write access. This can be an external directory for which agent user (recorded in VOLTTRON_HOME/agents/<agent-uuid>/USER_ID) has read, write, and execute access. 


Porting existing volttron home to secure mode
----------------------------------------------

When running scripts/secure_users_permissions.sh you will be prompted for a VOLTTRON_HOME directory. If this directory exists and contains a volttron config file. The script will update the file locations and permissions of existing volttron files including installed directories. However this step has the following limitations

#. **You will NOT be able to revert to insecure mode once the changes are done.**  Once setup is complete, changing the config file manually to make parameter "secure-agent-users" to False, may result inconsistent volttron behavior
#. Volttron process and all agents have to be restarted to take effect.
#. **Agents can only to write to its own agent-data dir.** So if your agents writes to any directory outside vhome/agents/<agent-uuid>/<agent-name>/agent-name.agent-data move existing files and update configuration such that agent writes to agent-name.agent-data dir. For example, if you have SQLHistorian in writing .sqlite file to a subdirectory under VOLTTRON_HOME that is not vhome/agents/<agent-uuid>/<agent-name>/agent-name.agent-data this needs to be manually updated.

