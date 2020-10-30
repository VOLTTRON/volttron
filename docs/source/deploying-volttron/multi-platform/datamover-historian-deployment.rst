.. _DataMover-Historian-Deployment:

===================
DataMover Historian
===================

This guide describes how a DataMover historian can be used to transfer data from one VOLTTRON instance to another. The
DataMover historian is different from Forward historian in the way it sends the data to the remote instance.  It first
batches the data and makes a RPC call to a remote historian instead of publishing data on the remote message bus
instance.  The remote historian then stores the data into it's database.

The walk-through below demonstrates how to setup DataMover historian to send data from one VOLTTRON instance to another.


VOLTTRON instance 1 sends data to platform historian on VOLTTRON instance 2
---------------------------------------------------------------------------

As an example two VOLTTRON instances will be created and to send data from one VOLTTRON instance running a fake driver
(subscribing to publishes from a fake device) and sending the values to a remote historian running on the second
VOLTTRON instance.


VOLTTRON instance 1 
^^^^^^^^^^^^^^^^^^^

-  ``vctl shutdown –platform`` (if the platform is already working)
-  ``volttron-cfg`` (this helps in configuring the volttron instance
   http://volttron.readthedocs.io/en/releases-4.1/core_services/control/VOLTTRON-Config.html

   - Specify the VIP address of the instance: ``tcp://127.0.0.1:22916``
   - Install Master Driver Agent with a fake driver for the instance.
   - Install a listener agent so see the topics that are coming from the diver agent
- Then run the volttron instance by using the following command: ``./start-volttron``


VOLTTRON instance 2
^^^^^^^^^^^^^^^^^^^

-  ``vctl shutdown –platform`` (if the platform is already working)
-  ``volttron-cfg`` (this helps in configuring the volttron instance)
   http://volttron.readthedocs.io/en/releases-4.1/core_services/control/VOLTTRON-Config.html

   -  Specify the VIP address of the instance : ``tcp://127.0.0.2:22916``
   -  Install a platform historian. ``volttron-cfg`` installs a default SQL historian.
-  Start the VOLTTRON instance by using following command: ``./start-volttron``


DataMover Configuration
^^^^^^^^^^^^^^^^^^^^^^^

An example config file is available in ``services/core/DataMover/config``.  We need to update the
`destination-vip`, `destination-serverkey`, and `destination-historian-identity` entries as per our setup.

.. note::

   Here the topics from the driver on VOLTTRON instance 1  will be sent to instance 2.

   - **destination-vip**: The VIP address of the volttron instance to which we need to send data. Example :
     ``tcp://127.0.0.2:22916``
   - **destination-serverkey**: The server key of remote VOLTTRON instance
     - Get the server key of VOLTTRON instance 2 and set `destination-serverkey` property with the server key

     .. code-block:: console

        vctl auth serverkey

   - destination-historian-identity: Identity of remote platform historian. Default is "platform.historian"


Running DataMover Historian
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Install the DataMover historian on the VOLTTRON instance 1

.. code-block:: console

    python scripts/install-agent.py -s services/core/DataMover -c services/core/DataMover/config -i datamover --start

- Add the public key of the DataMover historian on VOLTTRON instance 2 to enable authentication of the DataMover on
  VOLTTRON instance 2.

    - Get the public key of the DataMover. Run the below command on instance 1 terminal.

    .. code-block:: console

        vctl auth publickey --name datamoveragent-0.1

    - Add the credentials of the DataMover historian in VOLTTRON instance 2

    .. code-block:: console

        vctl auth add --credentials <public key of data mover>


Check data in SQLite database
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To check if data is transferred and stored in the database of remote platform historian, we need to check the
entries in the database.  The default location of SQL database (if not explicitly specified in the config file) will be
in the `data` directory inside the platform historian's installed directory within it's `$VOLTTRON_HOME`.

- Get the uuid of the platform historian. This can be found by running the ``vctl status`` on the terminal of instance
  2.  The first column of the data mover historian entry in the status table gives the first alphabet/number of the
  uuid.

- Go the `data` directory of platform historian's install directory.  For example,
  `/home/ubuntu/.platform2/agents/6292302c-32cf-4744-bd13-27e78e96184f/sqlhistorianagent-3.7.0/data`

- Run the SQL command to see the data
    .. code-block:: console

        sqlite3 platform.historian.sqlite
        select * from data;

- You will see similar entries

    .. code-block:: console

        2020-10-27T15:07:55.006549+00:00|14|true
        2020-10-27T15:07:55.006549+00:00|15|10.0
        2020-10-27T15:07:55.006549+00:00|16|20
        2020-10-27T15:07:55.006549+00:00|17|true
        2020-10-27T15:07:55.006549+00:00|18|10.0
        2020-10-27T15:07:55.006549+00:00|19|20
        2020-10-27T15:07:55.006549+00:00|20|true
        2020-10-27T15:07:55.006549+00:00|21|0
        2020-10-27T15:07:55.006549+00:00|22|0

