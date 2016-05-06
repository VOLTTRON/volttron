VIP Authentication
==================


`VIP <VIP>`__ (VOLTTRON Interconnect Protocol) authentication is
implemented in the auth module (*volttron/platform/auth.py*) and extends
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

The key is stored in ``$VOLTTRON_HOME/curve.key``, where VOLTTRON\_HOME
defaults to ``$HOME/.volttron``. The base64-encode public key is printed
in the log output at the **INFO** level when VOLTTRON starts (with -v
option) and should be used when connecting remote peers. Look for output
like this:

::

    (volttron)[user@home]$ volttron -v
    2015-09-01 12:15:05,334 () volttron.platform.main INFO: public key: 9yHEnRB_ct3lwpZi05CKtklzpXw26ehjwH-GBmfguRM

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
list for remote connections to be accepted. The file is initially
generated automatically with a sample entry commented out. The file must
consist of a dictionary with an "allow" key. The "allow" key should be a
list of dictionaries containing auth entries. The only required key in
those entries is "credentials" which is the colon-separated (:)
concatenation of the auth mechanism (one of *NULL*, *CURVE*, or *PLAIN*)
and the credentials. Optional keys in the auth entry are "domain" and
"address". Here are some examples:

| **Note:**
| If using regular expressions in the "address" portion, denote this
with "/". Backslashes must be escaped "\\".

This is a valid regular expression: ``"/192\\.168\\.1\\..*/"``

These are invalid:
``"/192\.168\.1\..*/", "/192\.168\.1\..*", "192\\.168\\.1\\..*"``

.. code:: JSON

    {
        "allow": [
            {"credentials": "CURVE:wk2BXQdHkAlMIoXthOPhFOqWpapD1eWsBQYY7h4-bXw", "domain": "vip", "address": "/192\\.168\\.1\\..*/"},
            {"credentials": "/CURVE:.*/", "address": "127.0.0.1"},
            {"credentials": "NULL", "address": "/localhost:1000:1000:.*/"}
        ]
    }

Each entry can be a string or a list of strings. Strings beginning and
ending with forward slashes are considered regular expressions and match
that way. Backward slashes must be escaped within this regular
expression "\\". When authenticating, the credentials are checked. If
they don't exist or don't match, authentication fails. Otherwise, if
domain and address are not present (or are null), authentication
succeeds. If address and/or domain exist, they must match as well for
authentication to succeed.

The *NULL* mechanism includes no credentials and is useful for IPC
connections, which have an address like ``localhost:UID:GID:PID``, where
the latter parts are the peer's user, group, and process IDs. *CURVE*
credentials include the remote peer's public key. Watching the **INFO**
level log output of the auth module can help determine the required
values for a specific peer.

It is unnecessary to provide auth entries for local agents started by
the platform as long as the agent continues to run with the same process
ID it was assigned when launched. Child processes are not currently
tracked, but that may change in the future.

Configuring Agents
------------------

A remote agent must know the platform's public key (also called the
server key) to successfully authenticate. The public key can be passed
in via the remote address. VOLTTRON extends ZeroMQ's address scheme by
supporting URL-style parameters for configuration. The following
parameters are supported when connecting:

-  serverkey: encoded public key of remote server
-  secretkey: agent's own private/secret key
-  publickey: agent's own public key
-  ipv6: instructs ZeroMQ to attempt to use IPv6

If either secretkey or publickey are missing and serverkey is defined, a
temporary secret and public key will be automatically generated. This
will only work if the auth entry on the remote host is configured to
allow such broad authentication. More permanent keypairs may be
generated using the ``volttron-ctl keypair`` command.

::

    (volttron)[brandon@deluxe platform]$ volttron-ctl keypair
    public: EIBCsV7PUngWJDgj0-lxSEjh7YigL6sLI-lvFN8oYVc
    secret: mgCegyw6CauL7EGifCPfxHSppdlC75MeGZ7O0VGN8og

Given the agent keys above and the platform public key from the first
example log output above, the following address could be constructed to
connect an agent:

::

    tcp://some.remote.volttron.server:5432?serverkey=9yHEnRB_ct3lwpZi05CKtklzpXw26ehjwH-GBmfguRM&publickey=EIBCsV7PUngWJDgj0-lxSEjh7YigL6sLI-lvFN8oYVc&secretkey=mgCegyw6CauL7EGifCPfxHSppdlC75MeGZ7O0VGN8og

The remote platform would require an auth entry similar to the following
for the connection to succeed:

.. code:: JSON

    {"credentials": "CURVE:EIBCsV7PUngWJDgj0-lxSEjh7YigL6sLI-lvFN8oYVc"}

Platform Configuration
----------------------

By default, the platform only listens on the local IPC VIP socket.
Additional addresses may be bound using the ``--vip-address`` option,
which can be provided multiple times to bind multiple addresses. Each
VIP address should follow the standard ZeroMQ convention of prefixing
with the socket type (*ipc://* or *tcp://*) and may include any of the
following additional URL parameters:

-  server: ZAP mechanism; must be one of *NULL*, *CURVE*, or *PLAIN*
   (defaults to *NULL* for *ipc://* and *CURVE* for *tcp://*)
-  domain: domain name to associate with this endpoint (defaults to
   "vip")
-  secretkey: alternate private/secret key (defaults to generated key
   for *tcp://*)
-  ipv6: instructs ZeroMQ to attempt to use IPv6

If secretkey is provided without server, server is assumed to be CURVE.

Questions and Answers
---------------------

-  I really don't like security or encrypting my important data. Can I
   disable the default TCP encryption?

   Yes, but we strongly advise against it for production deployments.
   Simply truncate the key file to zero bytes
   (``truncate -s 0 $VOLTTRON_HOME/curve.key``).

-  Can I temporarily disable encryption and authentication for testing
   or development?

   Yes. Simply use the ``--developer-mode`` option when launching
   VOLTTRON.

-  I am binding to the loopback address. Can I disable CURVE
   authentication just for that address?

   Yes. Just use an address like ``tcp://127.0.0.1:5432?server=NULL``
   (*?server=NULL* being the key).


