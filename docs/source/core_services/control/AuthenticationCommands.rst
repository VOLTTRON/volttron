.. _AuthenticationCommands:
Authentication Commands
=================

All authentication sub-commands can be viewed by entering following command.

.. code-block:: console

    volttron-ctl auth --help

.. code-block:: console

    optional arguments:
    -h, --help            show this help message and exit
    -c FILE, --config FILE
                            read configuration from FILE
    --debug               	show tracbacks for errors rather than a brief message
    -t SECS, --timeout SECS
                            timeout in seconds for remote calls (default: 30)
    --vip-address ZMQADDR
                            ZeroMQ URL to bind for VIP connections
    --keystore-file FILE  	use keystore from FILE
    --known-hosts-file FILE
                            get known-host server keys from FILE

    subcommands:
        add                 add new authentication record
        add-group           associate a group name with a set of roles
        add-known-host      add server public key to known-hosts file
        add-role            associate a role name with a set of capabilities
        keypair             generate CurveMQ keys for encrypting VIP connections
        list                list authentication records
        list-groups         show list of group names and their sets of roles
        list-known-hosts    list entries from known-hosts file
        list-roles          show list of role names and their sets of capabilities
        publickey           show public key for each agent
        remove              removes one or more authentication records by indices
        remove-group        disassociate a group name from a set of roles
        remove-known-host   remove entry from known-hosts file
        remove-role         disassociate a role name from a set of capabilities
        serverkey           show the serverkey for the instance
        update              updates one authentication record by index
        update-group        update group to include (or remove) given roles
        update-role         update role to include (or remove) given capabilities

Authentication record
---------------------

An authentication record consist of following parameters

.. code-block:: console

    domain []:
    address []: Either a single agent identity or an array of agents identities
    user_id []: Arbitrary string to identify the agent
    capabilities (delimit multiple entries with comma) []: Array of strings referring to authorized capabilities defined by exported RPC methods
    roles (delimit multiple entries with comma) []:
    groups (delimit multiple entries with comma) []:
    mechanism [CURVE]:
    credentials []: Public key string for the agent
    comments []:
    enabled [True]:

For more details on how to create authentication record, please see section :ref:`Agent Authentication<AgentAuthentication>`






