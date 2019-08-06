.. _Running Agents as as Volttron Agent User:
========================================
Running Agents as as Volttron Agent User
========================================

This Volttron feature will cause the platform to create a new, unique unix user
on the host machine for each agent installed on the platform. This user will
have restricted permissions for the file system, and will be used to run the
agent process.

To Run Agents as Their Own Users:
---------------------------------

    1. **Run scripts/security_users_permissions.sh** - This script will ask the
    Volttron user to provide a name for the their Volttron instance
    (volttron_<instance_name>). The instance name must be a 23 shorter string
    featuring only characters valid as unix user names. This name should not be
    shared with any existing Volttron instances. The script will create
    necessary entries in /etc/sudoers to allow the Volttron user to create agent
    users, the appropriate Volttron agent group, to delete these users, and to
    run any non-sudo command as these users.

    2. **Run vcfg** - This step must come after running the security users
    permissions script. Enter the Volttron instance name provided in when the
    the security script was run. When prompted with 'Should agents run with
    their own users' enter 'Y' or 'y' to set the configuration option.

At this point Volttron should run normally, as long as the Volttron agent
users, agent user files, and agent user permissions are not tampered with. Each
agent will now create a USER_ID file in the agent-data directory in addition to
any files created during a non-secure instance's normal operation.