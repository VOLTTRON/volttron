.. _Single-Machine-Deployment:

==============
Single Machine
==============

The purpose of this demonstration is to show the process of setting up a simple VOLTTRON instance for use on a single
machine.

.. note::

   The simple deployment example below considers only the ZeroMQ deployment scenario.  For RabbitMQ deployments, read
   and perform the RabbitMQ installation steps from the :ref:`platform installation <Platform-Installation>`
   instructions and configuration steps from :ref:`VOLTTRON Config <VOLTTRON-Config>`.


Install and Build VOLTTRON
==========================

First, :ref:`install <Platform-Installation>` VOLTTRON:

For a quick reference for Ubuntu machines:

.. code-block:: console

        sudo apt-get update
        sudo apt-get install build-essential libffi-dev python3-dev python3-venv openssl libssl-dev libevent-dev git
        git clone https://github.com/VOLTTRON/volttron/
        cd volttron
        python3 bootstrap.py --drivers --databases

.. note::

    For additional detail and more information on installing in other environments, please see the
    :ref:`platform install <Platform-Installation>` section.  See the :ref:`bootstrap process <Bootstrap-Process>` docs
    for more information on its operation and available options.


Activate the Environment
------------------------

After the build is complete, activate the VOLTTRON environment.

.. code-block:: console

   source env/bin/activate


Run VOLTTRON Config
-------------------

The `volttron-cfg` or `vcfg` commands can be used to configure platform communication.  For an example single machine
deployment, most values can be left at their default values.  The following is a simple case example of running `vcfg`:

.. code-block:: console

   (volttron) user@volttron-pc:~/volttron$ vcfg

    Your VOLTTRON_HOME currently set to: /home/james/.volttron

    Is this the volttron you are attempting to setup? [Y]:
    What type of message bus (rmq/zmq)? [zmq]:
    What is the vip address? [tcp://127.0.0.1]:
    What is the port for the vip address? [22916]:
    Is this instance web enabled? [N]:
    Will this instance be controlled by volttron central? [Y]: N
    Would you like to install a platform historian? [N]:
    Would you like to install a master driver? [N]:
    Would you like to install a listener agent? [N]:
    Finished configuration!

    You can now start the volttron instance.

    If you need to change the instance configuration you can edit
    the config file is at /home/james/.volttron/config

To learn more, read the :ref:`volttron-config <VOLTTRON-Config>` section of the Platform Features docs.

.. note::

   Steps below highlight manually installing some example agents.  To skip manual install, supply `y` or `Y` for the
   ``platform historian``, ``master driver`` and ``listener agent`` installation options.


Start VOLTTRON
--------------

The most convenient way to start the platform is with the `.start-volttron` command (from the volttron root
directory).

.. code-block:: bash

   ./start-volttron

The output following the platform starting successfully will appear like this:

.. code-block:: console

    2020-10-27 11:34:33,593 () volttron.platform.agent.utils DEBUG: value from env None
    2020-10-27 11:34:33,593 () volttron.platform.agent.utils DEBUG: value from config False
    2020-10-27 11:34:35,656 () root DEBUG: Creating ZMQ Core config.store
    2020-10-27 11:34:35,672 () volttron.platform.store INFO: Initializing configuration store service.
    2020-10-27 11:34:35,717 () root DEBUG: Creating ZMQ Core platform.auth
    2020-10-27 11:34:35,728 () volttron.platform.auth INFO: loading auth file /home/james/.volttron/auth.json
    2020-10-27 11:34:35,731 () volttron.platform.auth INFO: auth file /home/james/.volttron/auth.json loaded
    2020-10-27 11:34:35,732 () volttron.platform.agent.utils INFO: Adding file watch for /home/james/.volttron/auth.json dirname=/home/james/.volttron, filename=auth.json
    2020-10-27 11:34:35,734 () volttron.platform.agent.utils INFO: Added file watch for /home/james/.volttron/auth.json
    2020-10-27 11:34:35,734 () volttron.platform.agent.utils INFO: Adding file watch for /home/james/.volttron/protected_topics.json dirname=/home/james/.volttron, filename=protected_topics.json
    2020-10-27 11:34:35,736 () volttron.platform.agent.utils INFO: Added file watch for /home/james/.volttron/protected_topics.json
    2020-10-27 11:34:35,737 () volttron.platform.vip.pubsubservice INFO: protected-topics loaded
    2020-10-27 11:34:35,739 () volttron.platform.vip.agent.core INFO: Connected to platform: router: fc054c9f-aa37-4842-a618-6e70d53530f0 version: 1.0 identity: config.store
    2020-10-27 11:34:35,743 () volttron.platform.vip.agent.core INFO: Connected to platform: router: fc054c9f-aa37-4842-a618-6e70d53530f0 version: 1.0 identity: platform.auth
    2020-10-27 11:34:35,746 () volttron.platform.vip.pubsubservice INFO: protected-topics loaded
    2020-10-27 11:34:35,750 () volttron.platform.vip.agent.subsystems.configstore DEBUG: Processing callbacks for affected files: {}
    2020-10-27 11:34:35,879 () root DEBUG: Creating ZMQ Core control
    2020-10-27 11:34:35,908 () root DEBUG: Creating ZMQ Core keydiscovery
    2020-10-27 11:34:35,913 () root DEBUG: Creating ZMQ Core pubsub
    2020-10-27 11:34:35,924 () volttron.platform.auth INFO: loading auth file /home/james/.volttron/auth.json
    2020-10-27 11:34:38,010 () volttron.platform.vip.agent.core INFO: Connected to platform: router: fc054c9f-aa37-4842-a618-6e70d53530f0 version: 1.0 identity: control
    2020-10-27 11:34:38,066 () volttron.platform.vip.agent.core INFO: Connected to platform: router: fc054c9f-aa37-4842-a618-6e70d53530f0 version: 1.0 identity: pubsub
    2020-10-27 11:34:38,069 () volttron.platform.vip.agent.core INFO: Connected to platform: router: fc054c9f-aa37-4842-a618-6e70d53530f0 version: 1.0 identity: keydiscovery
    2020-10-27 11:34:38,429 () volttron.platform.auth WARNING: Attempt 1 to get peerlist failed with exception 0.5 seconds
    2020-10-27 11:34:38,430 () volttron.platform.auth WARNING: Get list of peers from subsystem directly
    2020-10-27 11:34:38,433 () volttron.platform.auth INFO: auth file /home/james/.volttron/auth.json loaded
    2020-10-27 11:34:38,434 () volttron.platform.auth INFO: loading auth file /home/james/.volttron/auth.json
    2020-10-27 11:34:40,961 () volttron.platform.auth WARNING: Attempt 1 to get peerlist failed with exception 0.5 seconds
    2020-10-27 11:34:40,961 () volttron.platform.auth WARNING: Get list of peers from subsystem directly
    2020-10-27 11:34:40,969 () volttron.platform.auth INFO: auth file /home/james/.volttron/auth.json loaded


.. note::

   While running the platform with verbose logging enabled, the `volttron.log` file is useful for confirming successful
   platform operations or debugging. It is commonly recommended to open a new terminal window and run the following
   command to view the VOLTTRON logs as they are created:

   .. code-block:: bash

      tail -f volttron.log


Install Agents and Historian
============================

Out of the box, VOLTTRON includes a number of agents which may be useful for single machine deployments:

    * historians - Historians automatically record a data from a number of topics published to the bus.  For more
      information on the historian framework or one of the included concrete implementations, view the
      :ref:`docs <Historian-Framework>`
    * Listener - This example agent can be useful for debugging drivers or other agents publishing to the bus.
      :ref:`docs <Listener-Agent>`
    * Master Driver - The :ref:`Master-Driver` is responsible for managing device communication on a platform instance.
    * weather agents - weather agents can be used to collect weather data from sources like
      :ref:`Weather.gov <Weather-Dot-Gov>`

    .. note::

       The `services/core`, `services/ops`, and `examples` directories in the repository contain additional agents to
       use to fit individual use cases.

For a simple setup example, a Master Driver, SQLite Historian, and Listener are installed using the following steps:

#. Create a configuration file for the Master Driver and SQLite Historian (it is advised to create a `configs` directory
   in volttron root to keep configs for a deployment).  For information on how to create configurations for these
   agents, view their docs:

    * :ref:`Master Driver <Master-Driver-Configuration>`
    * :ref:`SQLite Historian <SQL-Historian>`
    * :ref:`Listener <Listener-Agent>`

   For a simple example, the configurations can be copied as-is to the `configs` directory:

   .. code-block:: bash

      cp services/core/MasterDriverAgent/master-driver.agent configs
      cp services/core/SQLHistorian/config.sqlite configs
      cp examples/ListenerAgent/config configs/listener.config

#. Use the `install-agent.py` script to install the agent on the platform:

.. code-block:: bash

   python scripts/install-agent.py -s services/core/SQLHistorian -c configs/config.sqlite --tag listener
   python scripts/install-agent.py -s services/core/MasterDriverAgent -c configs/master-driver.agent --tag master_driver
   python scripts/install-agent.py -s examples/ListenerAgent -c configs/listener.config --tag platform_historian

   .. note::

      The `volttron.log` file will contain logging indicating that the agent has installed successfully.

      .. code-block:: console

         2020-10-27 11:42:08,882 () volttron.platform.auth INFO: AUTH: After authenticate user id: control.connection, b'c61dff8e-f362-4906-964f-63c32b99b6d5'
         2020-10-27 11:42:08,882 () volttron.platform.auth INFO: authentication success: userid=b'c61dff8e-f362-4906-964f-63c32b99b6d5' domain='vip', address='localhost:1000:1000:3249', mechanism='CURVE', credentials=['ZrDvPG4JNLE26GoPUrTP22rV0PV8uGCnrXThrNFk_Ec'], user='control.connection'
         2020-10-27 11:42:08,898 () volttron.platform.aip DEBUG: Using name template "listeneragent-3.3_{n}" to generate VIP ID
         2020-10-27 11:42:08,899 () volttron.platform.aip INFO: Agent b3e7053c-28e8-414f-b685-8522eb230c7a setup to use VIP ID listeneragent-3.3_1
         2020-10-27 11:42:08,899 () volttron.platform.agent.utils DEBUG: missing file /home/james/.volttron/agents/b3e7053c-28e8-414f-b685-8522eb230c7a/listeneragent-3.3/listeneragent-3.3.dist-info/keystore.json
         2020-10-27 11:42:08,899 () volttron.platform.agent.utils INFO: creating file /home/james/.volttron/agents/b3e7053c-28e8-414f-b685-8522eb230c7a/listeneragent-3.3/listeneragent-3.3.dist-info/keystore.json
         2020-10-27 11:42:08,899 () volttron.platform.keystore DEBUG: calling generate from keystore
         2020-10-27 11:42:08,909 () volttron.platform.auth INFO: loading auth file /home/james/.volttron/auth.json
         2020-10-27 11:42:11,415 () volttron.platform.auth WARNING: Attempt 1 to get peerlist failed with exception 0.5 seconds
         2020-10-27 11:42:11,415 () volttron.platform.auth WARNING: Get list of peers from subsystem directly
         2020-10-27 11:42:11,419 () volttron.platform.auth INFO: auth file /home/james/.volttron/auth.json loaded

#. Use the `vctl status` command to ensure that the agents have been successfully installed:

.. code-block:: bash

   vctl status

.. code-block:: console

     (volttron)user@volttron-pc:~/volttron$ vctl status
       AGENT                    IDENTITY            TAG                STATUS          HEALTH
     8 listeneragent-3.2        listeneragent-3.2_1 listener
     0 master_driveragent-3.2   platform.driver     master_driver
     3 sqlhistorianagent-3.7.0  platform.historian  platform_historian

.. note::

   After installation, the `STATUS` and `HEALTH` columns of the `vctl status` command will be vacant, indicating that
   the agent is not running.  The `--start` option can be added to the `install-agent.py` script arguments to
   automatically start agents after they have been installed.


Install a Fake Driver
=====================

The following are the simplest steps for installing a fake driver for example use.  For more information on installing
concrete drivers such as the BACnet or Modbus drivers, view their respective documentation in the
:ref:`Driver framework <Driver-Framework>` section.

.. note::

   This section will assume the user has created a `configs` directory in the volttron root directory, activated
   the Python virtual environment, and started the platform as noted above.

.. code-block:: console

   cp examples/configurations/drivers/fake.config <VOLTTRON root>/configs
   cp examples/configurations/drivers/fake.csv <VOLTTRON root>/configs
   vctl config store platform.driver devices/campus/building/fake configs/fake.config
   vctl config store platform.driver fake.csv devices/fake.csv

.. note::

   For more information on the fake driver, or the configurations used in the above example, view the
   :ref:`docs <Fake-Driver>`


Testing the Deployment
======================

To test that the configuration was successful, start an instance of VOLTTRON in the background:

.. code-block:: console

        ./start-volttron

.. note::

        This command must be run from the root VOLTTRON directory.

Having following the examples above, the platform should be ready for demonstrating the example deployment.  Start
the Listener, SQLite historian and Master Driver.

.. code-block:: console

   vctl start --tag listener platform_historian master_driver

The output should look similar to this:

.. code-block:: console

        (volttron)user@volttron-pc:~/volttron$ vctl status
          AGENT                    IDENTITY            TAG                STATUS          HEALTH
        8 listeneragent-3.2        listeneragent-3.2_1 listener           running [2810]  GOOD
        0 master_driveragent-3.2   platform.driver     master_driver      running [2813]  GOOD
        3 sqlhistorianagent-3.7.0  platform.historian  platform_historian running [2811]  GOOD

.. note::

   The `STATUS` column indicates whether the agent is running.  The `HEALTH` column indicates whether the current state
   of the agent is within intended parameters (if the Master Driver is publishing, the platform historian has not been
   backlogged, etc.)

You can further verify that the agents are functioning correctly with ``tail -f volttron.log``.

ListenerAgent:

.. code-block:: console

  2020-10-27 11:43:33,997 (listeneragent-3.3 3294) __main__ INFO: Peer: pubsub, Sender: listeneragent-3.3_1:, Bus: , Topic: heartbeat/listeneragent-3.3_1, Headers: {'TimeStamp': '2020-10-27T18:43:33.988561+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
  'GOOD'

Master Driver with Fake Driver:

.. code-block:: console

   2020-10-27 11:47:50,037 (listeneragent-3.3 3294) __main__ INFO: Peer: pubsub, Sender: platform.driver:, Bus: , Topic: devices/campus/building/fake/all, Headers: {'Date': '2020-10-27T18:47:50.005349+00:00', 'TimeStamp': '2020-10-27T18:47:50.005349+00:00', 'SynchronizedTimeStamp': '2020-10-27T18:47:50.000000+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
    [{'EKG': -0.8660254037844386,
     'EKG_Cos': -0.8660254037844386,
     'EKG_Sin': -0.8660254037844386,
     'Heartbeat': True,
     'OutsideAirTemperature1': 50.0,
     'OutsideAirTemperature2': 50.0,
     'OutsideAirTemperature3': 50.0,
     'PowerState': 0,
     'SampleBool1': True,
     'SampleBool2': True,
     'SampleBool3': True,
     'SampleLong1': 50,
     ...

SQLite Historian:

.. code-block:: console

    2020-10-27 11:50:25,021 (master_driveragent-4.0 3535) master_driver.driver DEBUG: finish publishing: devices/campus/building/fake/all
    2020-10-27 11:50:25,052 (sqlhistorianagent-3.7.0 3551) volttron.platform.dbutils.sqlitefuncts DEBUG: Managing store - timestamp limit: None  GB size limit: None
