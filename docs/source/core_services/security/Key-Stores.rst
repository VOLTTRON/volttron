.. _Key-Stores:

==========
Key Stores
==========

*Note: most VOLTTRON users should not need to directly interact with
agent key stores. These are notes for VOLTTRON platform developers.
This is not a stable interface and the implementation details are 
subject to change.*

Each agent has its own encryption key-pair that is used to
:ref:`authenticate<VIP-Authentication>` itself to the VOLTTRON
platform. A key-pair comprises a public key and a private (secret) key.
These keys are saved in a key store, which is implemented by the
:py:class:`KeyStore class<volttron.platform.keystore.KeyStore>`.
Each agent has its own key store.

Key Store Locations
-------------------

There are two main locations key stores will be saved. Installed agents'
key stores are in the the agent's data directory::

    $VOLTTRON_HOME/agents/<AGENT_UUID>/<AGENT_NAME>/keystore.json

Agents that are not installed, such as platform services and stand-alone
agents, store their key stores here::

    $VOLTTRON_HOME/keystores/<VIP_IDENTITY>/keystore.json

Generating a Key Store
----------------------

Agents automatically retrieve keys from their key store unless
both the ``publickey`` and ``secretkey`` parameters are specified
when the agent is initialized. If an agent's key store does not exist
it will automatically be generated upon access.

Users can generate a key pair by running the
``vctl auth keypair`` command.
