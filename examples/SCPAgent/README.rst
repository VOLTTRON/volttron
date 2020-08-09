SCP Agent
=========

The purpose of this example agent is to demonstrate secure copy of files from/to
external resources.  SCP uses ssh protocol for creating an encrypted connection
between the agent and the resources.

Configuration
-------------

The SCP Agent requires a few configuration elements in order for the agent to run.

.. csv-table:: Configuration Table
    :header: "Parameter", "Example", "Description"
    :widths: 15, 15, 30

    "ssh_id", "~/.ssh/id_rsa", "Path to the identity file to allow connectivity from the host to remote communication"
    "remote_user", "user@remote.com", "The user and resolvable host for connecting to"

Interfaces
----------

The SCP Agent has both a pubsub and rpc base interfaces.

RPC Interface
~~~~~~~~~~~~~

There are two methods available for the rpc interface the difference between the two
is the direction of the file exchange.

.. code-block::python

    result = agent.vip.rpc.call("scp.agent", "trigger_download",
                                remote_path="/home/osboxes/Downloads/f2.txt",
                                local_path="/home/osboxes/Desktop/f6.txt").get(timeout=10)

    result = agent.vip.rpc.call("scp.agent", "trigger_upload",
                                remote_path="/home/osboxes/Downloads/f6.txt",
                                local_path="/home/osboxes/Desktop/f6.txt").get(timeout=10)

PubSub Interface
~~~~~~~~~~~~~~~~

The pubsub interface requires sending of path through the pubsub subsystem.  The pubsub requires either a
json string or dictionary be sent across the message bus to the agent on the transfer topic will start
the scp transfer.

.. code-block::python

    agent.vip.pubsub.publish(peer='pubsub', topic="transfer", message=dict(remote_path=remote_path,
                                                                           local_path=local_path,
                                                                           direction="SENDING")).get(timeout=5)

    agent.vip.pubsub.publish(peer='pubsub', topic="transfer", message=dict(remote_path=remote_path,
                                                                           local_path=local_path,
                                                                           direction="RECEIVING")).get(timeout=5)


Testing
-------

Within the agent directory there is a trigger_scp.py script.  By default the trigger will run through 4 different
tests.  The tests will exercise the sending and receiving for both the rpc and pubsub interfaces.  The trigger will
require user interaction so run it with a shell that can receive input.

.. code-block::shell

    (volttron) (base) osboxes@osboxes:~/repos/volttron$ python examples/SCPAgent/trigger_scp.py

