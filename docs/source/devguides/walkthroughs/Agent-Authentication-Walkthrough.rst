.. _AgentAuthentication:

How to authenticate an agent to communicate with VOLTTRON platform:
======================================================================

An administrator can allow an agent to communicate with VOLTTRON platform by creating an authentication record for that agent.
Authentication record is created by using volttron-ctl auth add command and entering values to asked arguments.

::

    volttron-ctl auth add

        domain []:
        address []:
        user_id []:
        capabilities (delimit multiple entries with comma) []:
        roles (delimit multiple entries with comma) []:
        groups (delimit multiple entries with comma) []:
        mechanism [NULL]:
        credentials []:
        comments []:
        enabled [True]:

The simplest way of creating an authentication record is by entering the user_id and credential values.
User_id is a arbitrary string for VOLTTRON to identify the agent. Credential is the public key string
for the agent. Create a public/private key pair for the agent and enter public key for credential argument.

::

    volttron-ctl auth add

        domain []:
        address []:
        user_id []: "my-test-agent"
        capabilities (delimit multiple entries with comma) []:
        roles (delimit multiple entries with comma) []:
        groups (delimit multiple entries with comma) []:
        mechanism [NULL]:
        credentials []: "public-key-for-my-test-agent"
        comments []:
        enabled [True]:


I next sections, we will discuss each argument, its purpose and what all values it can take.

Domain:
-------
Domain argument is currently not being used in VOLTTRON and is placeholder for future implementation.

Address:
---------
By specifying address, administrator can allow an agent to connect with VOLTTRON only if that agent is running on that address.
Address argument can take either a string or an array of strings representing ip addresses.
It can also take regular expression representing a subnet address.

::

    address []: "192.168.111.1"
    address []: ["192.168.111.101","192.168.111.102"]
    address []: "/192.168.*/"

User_id:
---------
User_id can be any arbitrary string that is used to identify the agent by the platform.
If a regular expression is used for address or credential to combine agents in an authentication record then all
those agents will be identified by this user_id. It is primarily used for identifying agents during logging.

Capabilities:
-------------
Capability argument take is
