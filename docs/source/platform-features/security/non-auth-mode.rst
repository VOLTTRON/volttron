.. _non-auth-mode:

====================================
Disabling Authentication in VOLTTRON
====================================


There may be some use-cases, such as simulating deployments or agent development, where security is not a consideration.
In these cases, it is possible to disable VOLTTRON's authentication and authorization, stripping away the security
layer from the VIP messagebus and simplifying agent connection and RPC communication.

Since this is not ideal for any deployment, this can only be done by manually modifying the volttron configuration file.
Within the config file located within VOLTTRON_HOME, the allow-auth option must be added and set to False.

.. code-block:: console

  [volttron]
  message-bus = zmq
  vip-address = tcp://127.0.0.1:22916
  instance-name = volttron1
  allow-auth = False

In simulation environments where multiple volttron instances are used, it is important to ensure that auth settings are
the same across all the instances.

**Important things to consider:**

    1. This feature is recommended only for use with simulations and instances that are within a restrictive and
       secure network.
    2. When authentication is disabled, there will be no server-key generated for the server and hence the server would
       not have any access restrictions
    3. You can still use ssl (https) for your web access
    4. Non auth mode is currently available only for ZMQ
