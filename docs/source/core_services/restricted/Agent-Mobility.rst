.. _Agent-Mobility:

Agent Mobility
==================

The mobility module can enable the deployment of agents within a site or
to other sites (possibly in different building, cities, etc.) remotely.
The mobility feature allows authorized VOLTTRON platforms to send and
deploy agents, allowing for greater management and deployment ease and
flexibility.

This feature requires that you have installed the `VOLTTRON™
Restricted <Volttron-Restricted>`__.

To create the required keys (minimum requirement to run VOLTTRON with
Restricted module installed) enter the following commands in a command
terminal:

#. Create ssh directory in VOLTTRON\_HOME (see
   `PlatformConfiguration <PlatformConfiguration>`__ for details on
   configuring the platform):

   ``mkdir -p ~/.volttron/ssh``

#. Generate ssh key and add to id\_rsa file:

   ``ssh-keygen -t rsa -N '' -f ~/.volttron/ssh/id_rsa``

#. Create empty file for authorized keys and know hosts:

   ``touch ~/.volttron/ssh/{authorized_keys,known_hosts}``

Then, for each host you wish to authorize, its public key must be added
to the authorized\_keys file on the host to which it needs to connect.
The public key has a .pub extension. The added hosts must have VOLTTRON
instances installed, with the Restricted code installed and enabled (the
authorized host has created the keys detailed in the steps above):

-  Copy host information securely:

   ``scp otherhost.example.com:~/.volttron/ssh/id_rsa.pub ./otherhost.pub``

-  Append host key(s) to authorized\_keys file in $VOLTTRON\_HOME/ssh:

   \`\`\`cat otherhost.pub >> ~/.volttron/ssh/authorized\_keys\`\`\`\`

See the `PingPongAgent example <PingPongAgent>`__ for information on how
to add this feature to your custom agents.
