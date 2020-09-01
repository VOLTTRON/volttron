.. _Agent-Authentication-Commands:

=======================
Authentication Commands
=======================

All authentication sub-commands can be viewed by entering following command.

.. code-block:: console

    vctl auth --help

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

For more details on how to create authentication record, please see section
:ref:`Agent Authentication <Agent-Authentication>`


.. _Agent-Authentication:

==================================================================
How to authenticate an agent to communicate with VOLTTRON platform
==================================================================

An administrator can allow an agent to communicate with VOLTTRON platform by creating an authentication record for that
agent.  An authentication record is created by using :code:`vctl auth add` command and entering values to asked
arguments.

.. code-block:: console

    vctl auth add

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

The listed fields can also be specified on the command line:

.. code-block:: console

    vctl auth add --user_id bob --credentials ABCD...

If any field is specified on the command line, then the interactive menu
will not be used.

The simplest way of creating an authentication record is by entering the user_id and credential values.
User_id is a arbitrary string for VOLTTRON to identify the agent. Credential is the encoded public key string
for the agent. Create a public/private key pair for the agent and enter encoded public key for credential parameter.

.. code-block:: console

    vctl auth add

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

.. code-block:: console

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
the administrator can list that capability string in this parameter. Capability parameter takes an string or an array of strings or
a string representation of dictionary listing all the capabilities this agent is authorized to access.
Listing capabilities here will allow this agent to access corresponding exported RPC methods of other agents.

For example, if there is an AgentA with capability enables exported RPC method and AgentB needs to access that method then
AgentA's code and AgentB's authentication record would be as follow:


AgentA's capability enabled exported RPC method:

::

   @RPC.export
   @RPC.allow('can_call_bar')
   def bar(self):
      return 'If you can see this, then you have the required capabilities'


AgentB's authentication record to access bar method:

.. code-block:: console

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

.. code-block:: console

    capabilities (delimit multiple entries with comma) []: can_call_bar
    capabilities (delimit multiple entries with comma) []: can_call_method1, can_call_method2

Capabilities can also be used to restrict access to a rpc method only with certain parameter values. For example, if AgentA
exposes a method bar which accepts parameter x


AgentA's capability enabled exported RPC method:

::

   @RPC.export
   @RPC.allow('can_call_bar')
   def bar(self, x):
      return 'If you can see this, then you have the required capabilities'

You can restrict access to AgentA's bar method to AgentB with x=1. To add this auth entry use the vctl auth add command
as show below

::

   vctl auth add --capabilities '{"test1_cap2":{"x":1}}' --user_id AgentB --credential vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0

auth.json file entry for the above command would be

::

    {
      "domain": null,
      "user_id": "AgentB",
      "roles": [],
      "enabled": true,
      "mechanism": "CURVE",
      "capabilities": {
        "test1_cap2": {
          "x": 1
        }
      },
      "groups": [],
      "address": null,
      "credentials": "vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0",
      "comments": null
    }



Parameter values can also be regular expressions

::

    (volttron)volttron@volttron1:~/git/myvolttron$ vctl auth add
    domain []:
    address []:
    user_id []:
    capabilities (delimit multiple entries with comma) []: {'test1_cap2':{'x':'/.*'}}
    roles (delimit multiple entries with comma) []:
    groups (delimit multiple entries with comma) []:
    mechanism [CURVE]:
    credentials []: vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0
    comments []:
    enabled [True]:
    added entry domain=None, address=None, mechanism='CURVE', credentials=u'vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0', user_id='b22e041d-ec21-4f78-b32e-ab7138c22373'


auth.json file entry for the above command would be:

::

    {
      "domain": null,
      "user_id": "90f8ef35-4407-49d8-8863-4220e95974c7",
      "roles": [],
      "enabled": true,
      "mechanism": "CURVE",
      "capabilities": {
        "test1_cap2": {
          "x": "/.*"
        }
      },
      "groups": [],
      "address": null,
      "credentials": "vELQORgWOUcXo69DsSmHiCCLesJPa4-CtVfvoNHwIR0",
      "comments": null
    }


Roles:
-------
A role is a name for a set of capabilities. Roles can be used to grant an agent
multiple capabilities without listing each capability in the in the agent's
authorization entry. Capabilities can be fully utilized without roles. Roles
are purely for organizing sets of capabilities.

Roles can be viewed and edited with the following commands:

- ``vctl auth add-role``
- ``vctl auth list-roles``
- ``vctl auth remove-role``
- ``vctl auth updated-role``

For example, suppose agents protect certain methods with the following capabilites:
``READ_BUILDING_A_TEMP``, ``SET_BUILDING_A_TEMP``, ``READ_BUILDLING_B_TEMP``,
and ``SET_BUILDING_B_TEMP``.

These capabilities can be organized into various roles:

.. code-block:: console

    vctl auth add-role TEMP_READER READ_BUILDING_A_TEMP READ_BUILDLING_B_TEMP
    vctl auth add-role BUILDING_A_ADMIN READ_BUILDING_A_TEMP SET_BUILDING_A_TEMP
    vctl auth add-role BUILDING_B_ADMIN READ_BUILDING_B_TEMP SET_BUILDING_B_TEMP

To view these roles run ``vctl auth list-roles``:

.. code-block:: console

    ROLE              CAPABILITIES
    ----              ------------
    BUILDING_A_ADMIN  ['READ_BUILDING_A_TEMP', 'SET_BUILDING_A_TEMP']
    BUILDING_B_ADMIN  ['READ_BUILDING_B_TEMP', 'SET_BUILDING_B_TEMP']
    TEMP_READER       ['READ_BUILDING_A_TEMP', 'READ_BUILDLING_B_TEMP']

With this configuration, adding the ``BUILDING_A_ADMIN`` role to an agent's
authorization entry implicitly grants that agent the
``READ_BUILDING_A_TEMP`` and ``SET_BUILDING_A_TEMP`` capabilities.

To add a new capabilities to an existing role:

.. code-block:: console

   vctl auth update-role BUILDING_A_ADMIN CLEAR_ALARM TRIGGER_ALARM

To remove a capability from a role:

.. code-block:: console

   vctl auth update-role BUILDING_A_ADMIN TRIGGER_ALARM --remove


Groups:
-------
Groups provide one more layer of *grouping*. A group is a named set of roles.
Like roles, groups are optional and are meant to help with organization.

Groups can be viewed and edited with the following commands:

- ``vctl auth add-group``
- ``vctl auth list-groups``
- ``vctl auth remove-group``
- ``vctl auth updated-group``

These commands behave the same as the *role* commands. For example, to
further organize the capabilities in the previous section, one could create
create an ``ALL_BUILDING_ADMIN`` group:

.. code-block:: console

    vctl auth add-group ALL_BUILDING_ADMIN BUILDING_A_ADMIN BUILDING_B_ADMIN

With this configuration, agents in the ``ALL_BUILDING_ADMIN`` group would
implicity have the ``BUILDING_A_ADMIN`` and ``BUILDING_B_ADMIN`` roles. This means
such agents would implicity be granted the following capabilities:
``READ_BUILDING_A_TEMP``, ``SET_BUILDING_A_TEMP``, ``READ_BUILDLING_B_TEMP``,
and ``SET_BUILDING_B_TEMP``.


Mechanism:
-----------
Mechanism is the authentication method by which the agent will communicate with VOLTTRON platform. Currently VOLTTRON uses only CURVE mechanism to authenticate agents.


Credentials:
-------------

The credentials field must be an CURVE encoded public key (see `volttron.platform.vip.socket.encode_key` for method to encode public key).

.. code-block:: console

    credentials []: encoded-public-key-for-agent


Comments:
----------
Comments is arbitrary string to associate with authentication record


Enabled:
---------
TRUE of FALSE value to enable or disable the authentication record.
Record will only be used if this value is True
