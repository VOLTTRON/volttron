Forward Historian Walkthrough
=============================

This guide describes a simple setup where one Volttron instance collects
data from a dummy driver and sends it to another instance where it can
be recorded.

I'm doing this example on a single machine. If you're doing the same I
recommend the following:

-  Set your Volttrons' vip addresses to use tcp. It's not needed but is
   closer to what a real deployment would have. If you're looking for
   open ports then ``$ netstat -ln --tcp`` will be helpful.
-  Be careful with your terminal windows' environment variables. At
   least one of your Volttron instances won't be able to live in
   ``~/.volttron``
-  If you run into trouble it can be helpful to run each agent in the
   foreground of its own terminal. This can be accomplished with the
   following:

   -  Go to the agent's source directory
   -  Locate the agent's configuration file and the python file with a
      main function (frequently called agent.py)
   -  For the forwarding historian, the default config file is in the
      ``services/core/ForwardHistorian`` directory and its ``agent.py``
      file is at ``services/core/ForwardHistorian/forwarder/agent.py``
   -  Use ``$ AGENT_CONFIG=config python -m forwarder.agent`` (no
      ``.py``!) to run the forwarding historian in the foreground.

Configuration
-------------

#. Set up two Volttron instances as described in :ref:`Deployment Walkthrough <Deployment-Walkthrough>`
#. In each Volttron's ``auth.json`` file add the public key and location
   of the **other** Volttron instance to the ``"allow"`` array.
#. Now the Volttron instances should be able to communicate. To avoid
   having to worry about authentication for the remainder of the
   walkthrough you can use ``--developer-mode`` when starting Volttron.

Forwarding Volttron
~~~~~~~~~~~~~~~~~~~

This Volttron will have a fake driver provided by the `Master
Driver <Master-Driver-Agent>`__ and a `Forwarding
Historian <Forward-Historian>`__. You may have to edit these
configuration files before starting them:

::

    services/core/ForwardHistorian/config
    services/core/MasterDriverAgent/fake-msater-driver.agent
    services/core/MasterDriverAgent/master_driver/test_fakedriver.config

Remote Volttron
~~~~~~~~~~~~~~~

This Volttron will receive the history sent from the Volttron instance
we've already set up. Having a `Listener Agent <ListenerAgent>`__
running in the foreground (``scripts/launch_listener.sh``) will make it
easy to verify that the data has been successfully received.
