.. _DNP3:

DNP3
====

`DNP3 <https://en.wikipedia.org/wiki/DNP3>`_ (Distributed Network Protocol) is
a set of communications protocols that are widely used by utilities such as
electric power companies, primarily for `SCADA <https://en.wikipedia.org/wiki/SCADA>`_ purposes.
It was adopted in 2010
as `IEEE Std 1815-2010 <http://ieeexplore.ieee.org/document/5518537/?reload=true>`_,
later updated to `1815-2012 <https://standards.ieee.org/findstds/standard/1815-2012.html>`_.

VOLTTRON's DNP3Agent is an implementation of a DNP3 Outstation as specified in
IEEE Std 1815-2012. It engages in bidirectional network communications with a DNP3 Master,
which might be located at a power utility.

Like some other VOLTTRON protocol agents (e.g. SEP2Agent), DNP3Agent can optionally be
front-ended by a DNP3 device driver running under VOLTTRON's MasterDriverAgent. This
allows a DNP3 Master to be treated like any other device in VOLTTRON's ecosystem.

The VOLTTRON DNP3Agent implementation of an Outstation is built on pydnp3,
an open-source library from Kisensum containing Python language
bindings for Automatak's C++ `opendnp3 <https://www.automatak.com/opendnp3/>`_
library, the de facto reference implementation of DNP3.

DNP3Agent exposes DNP3 application-layer functionality, creating an extensible
base from which specific custom behavior can be designed and supported. By default, DNP3Agent
acts as a simple transfer agent, publishing data received from the Master on
the VOLTTRON Message Bus, and responding to RPCs from other VOLTTRON agents
by sending data to the Master.

RPC Calls
~~~~~~~~~

DNP3Agent exposes the following VOLTTRON RPC calls:

.. code-block:: python

    def get_point(self, point_name):
        """
            Look up the most-recently-received value for a given output point.

        @param point_name: The point name of a DNP3 PointDefinition.
        @return: The (unwrapped) value of a received point.
        """

    def get_point_by_index(self, group, index):
        """
            Look up the most-recently-received value for a given point.

        @param group: The group number of a DNP3 point.
        @param index: The index of a DNP3 point.
        @return: The (unwrapped) value of a received point.
        """

    def get_points(self):
        """
            Look up the most-recently-received value of each configured output point.

        @return: A dictionary of point values, indexed by their VOLTTRON point names.
        """

    def set_point(self, point_name, value):
        """
            Set the value of a given input point.

        @param point_name: The point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """

    def set_points(self, point_list):
        """
            Set point values for a dictionary of points.

        @param point_list: A dictionary of {point_name: value} for a list of DNP3 points to set.
        """

    def config_points(self, point_map):
        """
            For each of the agent's points, map its VOLTTRON point name to its DNP3 group and index.

        @param point_map: A dictionary that maps a point's VOLTTRON point name to its DNP3 group and index.
        """

    def get_point_definitions(self, point_name_list):
        """
            For each DNP3 point name in point_name_list, return a dictionary with each of the point definitions.

            The returned dictionary looks like this:

            {
                "point_name1": {
                    "property1": "property1_value",
                    "property2": "property2_value",
                    ...
                },
                "point_name2": {
                    "property1": "property1_value",
                    "property2": "property2_value",
                    ...
                }
            }

            If a definition cannot be found for a point name, it is omitted from the returned dictionary.

        :param point_name_list: A list of point names.
        :return: A dictionary of point definitions.
        """

Pub/Sub Calls
~~~~~~~~~~~~~

DNP3Agent uses two topics when publishing data to the VOLTTRON message bus:

 *  **Point Values (default topic: dnp3/point)**: As DNP3Agent communicates with the Master,
    it publishes received point values on the VOLTTRON message bus.

 * **Outstation status (default topic: dnp3/status)**: If the status of the DNP3Agent outstation
   changes, for example if it is restarted, it publishes its new status on the VOLTTRON message bus.

Data Dictionary of Point Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DNP3Agent loads and uses a data dictionary of point definitions, which are maintained by
agreement between the (DNP3Agent) Outstation and the DNP3 Master.
The data dictionary is stored in the agent's registry.

Current Point Values
~~~~~~~~~~~~~~~~~~~~

DNP3Agent tracks the most-recently-received value for each point definition in its
data dictionary, regardless of whether the point value's source is a VOLTTRON RPC call or
a message from the DNP3 Master.

Agent Configuration
~~~~~~~~~~~~~~~~~~~

The DNP3Agent configuration file specifies the following fields:

 - **local_ip**: (string)
   Outstation's host address (DNS resolved).
   Default: 0.0.0.0.
 - **port**: (integer)
   Outstation's port number - the port that the remote endpoint (Master) is listening on.
   Default: 20000.
 - **point_topic**: (string)
   VOLTTRON message bus topic to use when publishing DNP3 point values.
   Default: dnp3/point.
 - **outstation_status_topic**: (string)
   Message bus topic to use when publishing outstation status.
   Default: dnp3/outstation_status.
 - **outstation_config**: (dictionary)
   Outstation configuration parameters. All are optional. Parameters include:

   -- **database_sizes**: (integer)
      Size of each outstation database buffer.
      Default: 10.
   -- **event_buffers**: (integer)
      Size of the database event buffers.
      Default: 10.
   -- **allow_unsolicited**: (boolean)
      Whether to allow unsolicited requests.
      Default: True.
   -- **link_local_addr**: (integer)
      Link layer local address.
      Default: 10.
   -- **link_remote_addr**: (integer)
      Link layer remote address.
      Default: 1.
   -- **log_levels**: (list)
      List of bit field names (OR'd together) that filter what gets logged by DNP3.
      Default: [NORMAL]. Possible values: ALL, ALL_APP_COMMS, ALL_COMMS, NORMAL, NOTHING.
   -- **threads_to_allocate**: (integer)
      Threads to allocate in the manager's thread pool.
      Default: 1.

A sample DNP3Agent configuration file is available in `services/core/DNP3Agent/dnp3agent.config`.

VOLTTRON DNP3 Device Driver
---------------------------

VOLTTRON's DNP3 device driver exposes get_point/set_point calls, and scrapes, for DNP3 points.

The driver periodically issues DNP3Agent RPC calls to refresh its cached
representation of DNP3 data. It issues RPC calls to DNP3Agent as needed when
responding to get_point, set_point and scrape_all calls.

For information about the DNP3 driver, see :ref:`DNP3 Driver Configuration <DNP3-Driver-Config>`.

Installing DNP3Agent
--------------------

To install DNP3Agent, please consult the installation advice in `services/core/DNP3Agent/README.md`.
README.md specifies a default agent configuration, which can be overridden as needed.

An agent installation script is available:

.. code-block:: python

    $ export VOLTTRON_ROOT=<volttron github install directory>
    $ cd $VOLTTRON_ROOT
    $ source services/core/DNP3Agent/install_dnp3_agent.sh

When installing MesaAgent, please note that the agent's point definitions must be
loaded into the agent's config store. See install_dnp3_agent.sh for
an example of how to load them.

For Further Information
-----------------------

Questions? Please contact:

    -   Rob Calvert (rob@kisensum.com)
