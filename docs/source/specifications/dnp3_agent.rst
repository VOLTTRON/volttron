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

VOLTTRON DNP3Agent
------------------

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

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
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

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """

    def set_points(self, point_list):
        """
            Set point values for a list of points.

        @param point_list: An array of (point_name, value) for a list of DNP3 points to set.
        """

    def config_points(self, point_map):
        """
            For each of the agent's points, map its VOLTTRON point name to its DNP3 group and index.

        @param point_map: A dictionary that maps a point's VOLTTRON point name to its DNP3 group and index.
        """

Pub/Sub Calls
~~~~~~~~~~~~~

As DNP3Agent receives point values from the Master, it publishes them on the VOLTTRON message bus.
The pub/sub message's topic is the value of "point_topic" as specified in the agent's configuration,
defaulting to "dnp3/point" if the DNP3Agent config file fails to specify a topic.

Data Dictionary of Point Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DNP3Agent loads and uses a data dictionary of point definitions, which are maintained by
agreement between the (DNP3Agent) Outstation and the DNP3 Master.
The data dictionary is loaded from a JSON file of point definitions. This file's path
is specified in the DNP3Agent configuration.

The following is an example of two point definitions in the JSON file, a definition of
an "input" point (data sent to the Master) and an "output" point (data received from the Master).

.. code-block:: json

    {
        "name": "DCHD.WTgt (out)",
        "group": 41,                        # Analog Output
        "variation": 1,                     # 32-bit integer command
        "index": 65,
        "description": "Charge/Discharge Active Power Target (output)",
        "scaling_multiplier": 1,
        "units": "%",
        "fcodes": ["direct_operate"],
        "echo": {
            "group": 30,
            "variation": 1,
            "index": 90
        }
    },
    {
        "name": "DCHD.WTgt (in)",           # Echo of group 41 variation 1 index 65
        "group": 30,                        # Analog Input
        "variation": 1,                     # 32-bit integer with flag
        "index": 90,
        "description": "Charge/Discharge Active Power Target (input)",
        "scaling_multiplier": 1,
        "units": "%",
        "event_class": 2,
        "event_group": 32,
        "event_variation": 3                # 32-bit integer with time
    },

Current Point Values
~~~~~~~~~~~~~~~~~~~~

DNP3Agent tracks the most-recently-received value for each point definition in its
data dictionary, regardless of whether the point value's source is a VOLTTRON RPC call or
a message from the DNP3 Master.

Agent Configuration
~~~~~~~~~~~~~~~~~~~

The DNP3Agent configuration file specifies the following fields:

    - **point_definitions_path** - (string, required) Pathname of the JSON file containing DNP3 point definitions.
    - **point_topic** - (string) VOLTTRON message bus topic to use when publishing DNP3 point values. Default: dnp3/point.
    - **outstation_config** - (dictionary) Optional parameters influencing the Outstation's configuration. See below.
    - **local_ip** - (string) IP address of the DNP3 Master. Default: 0.0.0.0.
    - **port** - (integer) Port number of the DNP3 Master. Default: 20000.

The outstation_config dictionary of optional parameters can specify the following:

    - **database_sizes** - (integer) Size of each DNP3 database buffer. Default: 10.
    - **event_buffers** - (integer) Size of the database event buffers. Default: 10.
    - **allow_unsolicited** - (boolean) Whether to allow unsolicited requests. Default: True.
    - **link_local_addr** - (integer) Link layer local address. Default: 10.
    - **link_remote_addr** - (integer) Link layer remote address. Default: 1.
    - **log_levels** - List of bit field names (OR'd together) that filter what gets logged by DNP3. Default: NORMAL. Possible values: ALL, ALL_APP_COMMS, ALL_COMMS, NORMAL, NOTHING.
    - **threads_to_allocate** - (integer) Threads to allocate in the manager's thread pool. Default: 1.

A typical DNP3Agent configuration file might look like the following:

.. code-block:: json

    {
        "point_definitions_path": "~/repos/volttron/services/core/DNP3Agent/opendnp3_data.config",
        "point_topic": "dnp3/point",
        "outstation_config": {
            "log_levels": 0
        },
        "local_ip": "0.0.0.0",
        "port": 20000
    }

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

To install DNP3Agent, please consult the installation advice in `services/core/DNP3Agent/README.md`,
which includes advice on installing `pydnp3`, a library upon which DNP3Agent depends.

For Further Information
-----------------------

Questions? Please contact:

    -   Rob Calvert (rob@kisensum.com)
