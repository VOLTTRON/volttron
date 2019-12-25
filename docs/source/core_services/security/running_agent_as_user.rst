.. _Running Agents as unique Unix user:

==============================
Running Agents as unique users
==============================

This Volttron feature will cause the platform to create a new, unique unix user
on the host machine for each agent installed on the platform. This user will
have restricted permissions for the file system, and will be used to run the
agent process. The unix user starting the volttron platform will be given
limited sudo access to create and delete agent users.

To Run Agents as Their Own Users:
---------------------------------

1. **This feature requires acl to be installed.**

   Make sure acl library is installed. If you are running on docker image acl might not be installed by default

   **apt-get install acl**

2. **Run scripts/secure_users_permissions.sh as root or using sudo**

   This script should be run as root or using sudo. This script gives the volttron platform user limited sudo access to create a new unix user for each agent. All users created will be of the format volttron_<timestamp>.

   This script prompts for:

   a. **volttron platform user** - Unix user who would be running VOLTTRON platform

   b. **VOLTTRON_HOME directory** - The absolute path of volttron home directory.

   c. **Volttron instance name if VOLTTRON_HOME/config does not exist** -
If VOLTTRON_HOME/config file exists instance name is got from config file. If not user will be prompted for instance name. volttron_<instance_name> must be a 23 characters or shorter containing only characters valid as unix user names.

This script will create necessary entries in /etc/sudoers.d/volttron to allow the volttron platform user to create and delete agent users, Volttron agent group, and run any non-sudo command as agent users. This script will also create VOLTTRON_HOME and the config file if given a new volttron home directory when prompted.

Each agent will now create a USER_ID file in the agent-data directory in addition to
any files created during a non-secure instance's normal operation.
