.. _VIP-Authentication:

==================
VIP Authentication
==================

:ref:`VIP <VIP-Overview>` (VOLTTRON Interconnect Protocol) authentication is
implemented in the :py:mod:`auth module<volttron.platform.auth>` and extends
the ZeroMQ Authentication Protocol
`ZAP <http://rfc.zeromq.org/spec:27>`__ to VIP by including the ZAP
User-Id in the VIP payload, thus allowing peers to authorize access
based on ZAP credentials. This document does not cover ZAP in any
detail, but its understanding is fundamental to securely configuring
ZeroMQ. While this document will attempt to instruct on securely
configuring VOLTTRON for use on the Internet, it is recommended that the
ZAP documentation also be consulted.

Default Encryption
------------------

By default, ZeroMQ operates in plain-text mode, without any sort of
encryption. While this is okay for in-process and interprocess
communications, via UNIX domain sockets, it is insecure for any kind of
inter-network communications, especially when traffic must traverse the
Internet. Therefore, VOLTTRON automatically generates an encryption key
and enables `CurveMQ <http://rfc.zeromq.org/spec:26>`__ by default on
all TCP connections.

To see VOLTTRON's public key run the ``vctl auth serverkey`` command.
For example::

    (volttron)[user@home]$ volttron-ctl auth serverkey
    FSG7LHhy3v8tdNz3gK35G6-oxUcyln54pYRKu5fBJzU

Peer Authentication
-------------------

ZAP defines a method for verifying credentials exchanged when a
connection is initially established. The authentication mechanism
provides three main pieces of information useful for authentication:

-  domain: a name assigned to a locally bound address (to which peers
   connect)
-  address: the remote address of the peer
-  credentials: includes the authentication method and any associated
   credentials

During authentication, VOLTTRON checks these pieces against a list of
accepted peers defined in a file, called the "auth file" in this
document. This JSON-formatted file is located at
``$VOLTTRON_HOME/auth.json`` and must have a matching entry in the allow
list for remote connections to be accepted.

The auth file should not be modified directly. 
To change the auth file, use ``vctl auth`` subcommands: ``add``,
``list``, ``remove``, and ``update``. (Run ``vctl auth --help``
for more details and see the 
:ref:`authentication commands documentation <Agent-Authentication-Commands>`.)

Here are some example entries::

    (volttron)[user@home]$ vctl auth list

    INDEX: 0
    {
      "domain": null, 
      "user_id": "platform", 
      "roles": [], 
      "enabled": true, 
      "mechanism": "CURVE", 
      "capabilities": [], 
      "groups": [], 
      "address": null, 
      "credentials": "k1C9-FPRAVjL-cH1iQqAJaCHUNVXaAlkVc7EqK0u9mI", 
      "comments": "Automatically added by platform on start"
    }
    
    INDEX: 2
    {
      "domain": null, 
      "user_id": "platform.sysmon", 
      "roles": [], 
      "enabled": true, 
      "mechanism": "CURVE", 
      "capabilities": [], 
      "groups": [], 
      "address": null, 
      "credentials": "5UD_GTk5dM2g4pk8d1-wM-BYgt4RAKiHf4SnT_YU6jY", 
      "comments": "Automatically added on agent install"
    }

**Note:**
If using regular expressions in the "address" portion, denote this
with "/". Backslashes must be escaped "\\".

This is a valid regular expression: ``"/192\\.168\\.1\\..*/"``

These are invalid:
``"/192\.168\.1\..*/", "/192\.168\.1\..*", "192\\.168\\.1\\..*"``

When authenticating, the credentials are checked. If
they don't exist or don't match, authentication fails. Otherwise, if
domain and address are not present (or are null), authentication
succeeds. If address and/or domain exist, they must match as well for
authentication to succeed.

*CURVE*
credentials include the remote peer's public key. Watching the **INFO**
level log output of the auth module can help determine the required
values for a specific peer.

Configuring Agents
------------------

A remote agent must know the platform's public key (also called the
server key) to successfully authenticate. This server key can be
passed to the agent's ``__init__`` method in the ``serverkey``
parameter, but in most scenarios it is preferable to add the server key
to the :ref:`known-hosts file<Known-Hosts-File>`.


URL-style Parameters
~~~~~~~~~~~~~~~~~~~~

VOLTTRON extends ZeroMQ's address scheme by
supporting URL-style parameters for configuration. The following
parameters are supported when connecting:

-  serverkey: encoded public key of remote server
-  secretkey: agent's own private/secret key
-  publickey: agent's own public key
-  ipv6: instructs ZeroMQ to attempt to use IPv6

  **Note:**
  Although these parameters are still supported they should rarely
  need to be specified in the VIP-address URL.
  Agent 
  :ref:`key stores<Key-Stores>` and the 
  :ref:`known-hosts file<Known-Hosts-File>` are automatically
  used when possible.

Platform Configuration
----------------------

By default, the platform only listens on the local IPC VIP socket.
Additional addresses may be bound using the ``--vip-address`` option,
which can be provided multiple times to bind multiple addresses. Each
VIP address should follow the standard ZeroMQ convention of prefixing
with the socket type (*ipc://* or *tcp://*) and may include any of the
following additional URL parameters:

-  domain: domain name to associate with this endpoint (defaults to
   "vip")
-  secretkey: alternate private/secret key (defaults to generated key
   for *tcp://*)
-  ipv6: instructs ZeroMQ to attempt to use IPv6

Example Setup
-------------

Suppose agent ``A`` needs to connect to a remote platform ``B``.
First, agent ``A`` must know platform ``B``'s public key 
(the *server key*) and platform ``B``'s IP address (including port).
Also, platform ``B`` needs to know agent ``A``'s public key
(let's say it is ``HOVXfTspZWcpHQcYT_xGcqypBHzQHTgqEzVb4iXrcDg``).

Given these values, a user on agent ``A``'s platform adds platform
``B``'s information to the :ref:`known-hosts file<Known-Hosts-File>`.

At this point agent ``A`` has all the infomration needed to connect to 
platform ``B``, but platform ``B`` still needs to add an authentication entry
for agent ``A``.

If agent ``A`` tried to connect to platform ``B`` at this point both parties
would see an error. Agent ``A`` would see an error similar to:

::

    No response to hello message after 10 seconds.
    A common reason for this is a conflicting VIP IDENTITY.
    Shutting down agent.

Platform ``B`` (if started with `-v` or `-vv`) will show an error:

::

    2016-10-19 14:21:20,934 () volttron.platform.auth INFO: authentication failure: domain='vip', address='127.0.0.1', mechanism='CURVE', credentials=['HOVXfTspZWcpHQcYT_xGcqypBHzQHTgqEzVb4iXrcDg']

Agent ``A`` failed to authenticat to platform ``B`` because the platform
didn't have agent ``A``'s public in the authentication list.

To add agent ``A``'s public key, a user on platform ``B`` runs::

    (volttron)[user@platform-b]$ volttron-ctl auth add
    domain []: 
    address []: 
    user_id []: Agent-A
    capabilities (delimit multiple entries with comma) []: 
    roles (delimit multiple entries with comma) []: 
    groups (delimit multiple entries with comma) []: 
    mechanism [CURVE]: 
    credentials []: HOVXfTspZWcpHQcYT_xGcqypBHzQHTgqEzVb4iXrcDg
    comments []: 
    enabled [True]:

Now if agent ``A`` can successfully connect to platform ``B``, and platform
``B``'s log will show:

::

    2016-10-19 14:26:16,446 () volttron.platform.auth INFO: authentication success: domain='vip', address='127.0.0.1', mechanism='CURVE', credentials=['HOVXfTspZWcpHQcYT_xGcqypBHzQHTgqEzVb4iXrcDg'], user_id='Agent-A'

For a more details see the :ref:`authentication walk-through <Agent-Authentication>`.
