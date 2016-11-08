.. _AgentAuthentication:

How to authenticate an agent to communicate with VOLTTRON platform:
======================================================================

An administrator can allow an agent to communicate with VOLTTRON platform by creating an authentication record for that agent.
An authentication record is created by using :code:`volttron-ctl auth add` command and entering values to asked arguments.

::

    volttron-ctl auth add

        domain []:
        address []:
        user_id []:
        capabilities (delimit multiple entries with comma) []:
        roles (delimit multiple entries with comma) []:
        groups (delimit multiple entries with comma) []:
        mechanism [CURVE]:
        credentials []:
        comments []:
        enabled [True]:

The simplest way of creating an authentication record is by entering the user_id and credential values.
User_id is a arbitrary string for VOLTTRON to identify the agent. Credential is the encoded public key string
for the agent. Create a public/private key pair for the agent and enter encoded public key for credential parameter.

::

    volttron-ctl auth add

        domain []:
        address []:
        user_id []: my-test-agent
        capabilities (delimit multiple entries with comma) []:
        roles (delimit multiple entries with comma) []:
        groups (delimit multiple entries with comma) []:
        mechanism [CURVE]:
        credentials []: encoded-public-key-for-my-test-agent
        comments []:
        enabled [True]:


In next sections, we will discuss each parameter, its purpose and what all values it can take.

Domain:
-------
Domain is the name assigned to locally bound address. Domain parameter is currently not being used in VOLTTRON and is placeholder for future implementation.

Address:
---------
By specifying address, administrator can allow an agent to connect with VOLTTRON only if that agent is running on that address.
Address parameter can take a string representing an IP addresses.
It can also take a regular expression representing a range of IP addresses.

::

    address []: 192.168.111.1
    address []: /192.168.*/

User_id:
---------
User_id can be any arbitrary string that is used to identify the agent by the platform.
If a regular expression is used for address or credential to combine agents in an authentication record then all
those agents will be identified by this user_id. It is primarily used for identifying agents during logging.

Capabilities:
-------------
Capability is an arbitrary string used by an agent to describe its exported RPC method. It is used to limit the access
to that RPC method to only those agents who have that capailbity listed in their authentication record.


If administrator wants to authorize an agent to access an exported RPC method with capability of another agent,
he/she can list that capability string in this parameter. Capability parameter takes an string or an array of strings
listing all the capabilities this agent is authorized to access. Listing capabilities here will allow this agent to
access corresponding exported RPC methods of other agents.

For example, if there is an AgentA with capability enables exported RPC method and AgentB needs to access that method then
AgentA's code and AgentB's authentication record would be as follow:


AgentA's capability enabled exported RPC method:

::

   @RPC.export
   @RPC.allow('can_call_bar')
   def bar(self):
      return 'If you can see this, then you have the required capabilities'


AgentB's authentication record to access bar method:

::

    volttron-ctl auth add

        domain []:
        address []:
        user_id []: agent-b
        capabilities (delimit multiple entries with comma) []: can_call_bar
        roles (delimit multiple entries with comma) []:
        groups (delimit multiple entries with comma) []:
        mechanism [NULL]: CURVE
        credentials []: encoded-public-key-for-agent-b
        comments []:
        enabled [True]:


Similarly, capability parameter can take an array of string:

::

    capabilities (delimit multiple entries with comma) []: can_call_bar
    capabilities (delimit multiple entries with comma) []: can_call_method1, can_call_method2


Roles:
-------
These are authorized roles for this agent.
Roles parameter is currently not being used in VOLTTRON and is placeholder for future implementation.

Groups:
-------
These are authorized groups for this agent. Groups parameter is currently not being used in VOLTTRON and is placeholder for future implementation.

Mechanism:
-----------
Mechanism is the authentication method by which the agent will communicate with VOLTTRON platform. Currently VOLTTRON uses only CURVE mechanism to authenticate agents.

Credentials:
-------------

The credentials field must be an CURVE encoded public key (see `volttron.platform.vip.socket.encode_key` for method to encode public key).

::

    credentials []: encoded-public-key-for-agent


Comments:
----------
Comments is arbitrary string to associate with authentication record


Enabled:
---------
TRUE of FALSE value to enable or disable the authentication record.
Record will only be used if this value is True




