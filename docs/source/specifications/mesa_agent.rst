.. _MESA:

MesaAgent
---------

MesaAgent is a VOLTTRON agent that handles MESA-ESS DNP3 outstation communications.
It subclasses and extends the functionality of VOLTTRON's DNP3Agent. Like DNP3Agent,
MesaAgent models a DNP3 outstation, communicating with a DNP3 master.

`DNP3 <https://en.wikipedia.org/wiki/DNP3>`_ (Distributed Network Protocol) is
a set of communications protocols that are widely used by utilities such as
electric power companies, primarily for `SCADA <https://en.wikipedia.org/wiki/SCADA>`_ purposes.
It was adopted in 2010
as `IEEE Std 1815-2010 <http://ieeexplore.ieee.org/document/5518537/?reload=true>`_,
later updated to `1815-2012 <https://standards.ieee.org/findstds/standard/1815-2012.html>`_.

VOLTTRON's MesaAgent and DNP3Agent are implementations of a DNP3 Outstation as specified in
IEEE Std 1815-2012. They engage in bidirectional network communications with a DNP3 Master,
which might be located at a power utility.

MESA-ESS is an extension and enhancement to DNP3. It builds on the basic DNP3 communications
protocol, adding support for more complex structures, including functions, arrays, curves and schedules.
The draft specification for MESA-ESS, as well as a spreadsheet of point definitions, can be
found at **http://mesastandards.org/mesa-ess-2016/**.

VOLTTRON's DNP3Agent and MesaAgents implementations of an Outstation are built on pydnp3,
an open-source library from Kisensum containing Python language
bindings for Automatak's C++ `opendnp3 <https://www.automatak.com/opendnp3/>`_
library, the de facto reference implementation of DNP3.

MesaAgent exposes DNP3 application-layer functionality, creating an extensible
base from which specific custom behavior can be designed and supported, including support
for MESA functions, arrays and selector blocks. By default, MesaAgent
acts as a simple transfer agent, publishing data received from the Master on
the VOLTTRON Message Bus, and responding to RPCs from other VOLTTRON agents
by sending data to the Master. Properties of the point and function definitions also enable
the use of more complex controls for point data capture and publication.

MesaAgent was developed by Kisensum for use by 8minutenergy, which provided generous
financial support for the open-source contribution to the VOLTTRON platform, along with
valuable feedback based on experience with the agent in a production context.

RPC Calls
~~~~~~~~~

MesaAgent exposes the following VOLTTRON RPC calls:

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

        @return: A dictionary of point values, indexed by their point names.
        """

    def set_point(self, point_name, value):
        """
            Set the value of a given input point.

        @param point_name: The point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """

    def set_points(self, point_dict):
        """
            Set point values for a dictionary of points.

        @param point_dict: A dictionary of {point_name: value} for a list of DNP3 points to set.
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

    def get_selector_block(self, point_name, edit_selector):
        """
            Return a dictionary of point values for a given selector block.

        :param point_name: Name of the first point in the selector block.
        :param edit_selector: The index (edit selector) of the block.
        :return: A dictionary of point values.
        """

Pub/Sub Calls
~~~~~~~~~~~~~

MesaAgent uses three topics when publishing data to the VOLTTRON message bus:

 *  **Point Values (default topic: mesa/point)**: As MesaAgent communicates with the Master,
    it publishes received point values on the VOLTTRON message bus.

 * **Functions (default topic: mesa/function)**: When MesaAgent receives a function step
   with a "publish" action value, it publishes the current state of the function (all
   steps received to date) on the VOLTTRON message bus.

 * **Outstation status (default topic: mesa/status)**: If the status of the MesaAgent outstation
   changes, for example if it is restarted, it publishes its new status on the VOLTTRON message bus.

Data Dictionaries of Point and Function Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MesaAgent loads and uses data dictionaries of point and function definitions,
which are maintained by agreement between the (MesaAgent) Outstation and the DNP3 Master.
The data dictionaries are stored in the agent's registry.

Current Point Values
~~~~~~~~~~~~~~~~~~~~

MesaAgent tracks the most-recently-received value for each point definition in its
data dictionary, regardless of whether the point value's source is a VOLTTRON RPC call or
a message from the DNP3 Master.

Agent Configuration
~~~~~~~~~~~~~~~~~~~

The MesaAgent configuration specifies the following fields:

 - **local_ip**: (string)
   Outstation's host address (DNS resolved).
   Default: 0.0.0.0.
 - **port**: (integer)
   Outstation's port number - the port that the remote endpoint (Master) is listening on.
   Default: 20000.
 - **point_topic**: (string)
   VOLTTRON message bus topic to use when publishing DNP3 point values.
   Default: dnp3/point.
 - **function_topic**: (string)
   Message bus topic to use when publishing MESA-ESS functions.
   Default: mesa/function.
 - **outstation_status_topic**: (string)
   Message bus topic to use when publishing outstation status.
   Default: mesa/outstation_status.
 - **all_functions_supported_by_default**: (boolean)
   When deciding whether to reject points for unsupported
   functions, ignore the values of their 'supported' points: simply treat all functions as
   supported. Used primarily during testing.
   Default: False.
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

A sample MesaAgent configuration file is available in **services/core/DNP3Agent/mesaagent.config**.

Installing MesaAgent
--------------------

To install MesaAgent, please consult the installation advice in **services/core/DNP3Agent/README.md**,
which includes advice on installing **pydnp3**, a library upon which DNP3Agent depends.

After installing libraries as described in README.md,
the agent can be installed from a command-line shell as follows:

.. code-block:: python

    $ export VOLTTRON_ROOT=<volttron github install directory>
    $ cd $VOLTTRON_ROOT
    $ source services/core/DNP3Agent/install_mesa_agent.sh

README.md specifies a default agent configuration, which can be overridden as needed.

Here are some things to note when installing MesaAgent:

 - MesaAgent source code resides in, and is installed from, a dnp3 subdirectory, thus allowing it
   to be implemented as a subclass of the base DNP3 agent class.
   When installing MesaAgent, inform the install script that it should build from the
   mesa subdirectory by exporting the following environment variable:

    -- $ export AGENT_MODULE=dnp3.mesa.agent

 - The agent's point and function definitions must be loaded into the agent's config store. See the
   install_mesa_agent.sh script for an example of how to load them.

For Further Information
-----------------------

Questions? Please contact:

    -   Rob Calvert at Kisensum (rob@kisensum.com)
