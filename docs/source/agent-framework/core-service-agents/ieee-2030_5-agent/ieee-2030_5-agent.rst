.. _IEEE-2030_5-Agent:

===========================
IEEE 2030.5 EndDevice Agent
===========================

The IEEE 2030.5 Agent (IEEE_2030_5 in the VOLTTRON repository) implements a IEEE 2030.5 EndDevice (client).  The agent
will securly connect to a TLS enabled 2030.5 server and discover it's capabilities.  The agent will verify that
correct server is being connected to based upon the Registration function set.  The agent will then use the
FunctionSetAssignments function set to determine the proper DERProgram to run.  The agent will poll for changes
in default controls and whether one or more DERControl is active and act accordingly.  The agent will listen to
one or more subscriptions to the VOLTTRON message bus for informatoion (points) to POST/PUT to the 2030.5 server.

The agent code, README and demo are available from `IEEE_2030_5 Agent <https://github.com/craig8/volttron/tree/2030_5_anew/services/core/IEEE_2030_5/>`_.

Configuration
-------------

There are two configuration files for the IEEE 2030.5 Agent: ``The point_map file``, which is loaded into the config store,
and the ``agent configuration file``, which is passed to the agent during installation.

The agent configuration file configures the type of DER that the agent is connecting as and any MirrorUsagePoints that
should be published to the server.  The mapping file is used to map the IEEE 2030.5 resource to a VOLTTRON point name.

.. note::
   The point_map file is used to translate from/to the platform.driver's all message and 2030.5 point types.

The following is an example of the agent configuration file:

.. code-block:: yaml
   # These are required in order for the agent to connect to the server.
   cacertfile: ~/tls/certs/ca.crt
   keyfile: ~/tls/private/dev1.pem
   certfile: ~/tls/certs/dev1.crt
   server_hostname: 127.0.0.1

   # the pin number is used to verify the server is the correct server
   pin: 111115

   # Log the request and responses from the server.
   log_req_resp: true

   # SSL defaults to 443
   server_ssl_port: 8443
   # http port defaults to none
   #server_http_port: 8080
   # Number of seconds to poll for new default der settings.
   default_der_control_poll: 60

   MirrorUsagePointList:
   # MirrorMeterReading based on Table E.2 IEEE Std 2030.5-18
   - device_point: INV_REAL_PWR
      mRID: 5509D69F8B3535950000000000009182
      description: DER Inverter Real Power
      roleFlags: 49
      serviceCategoryKind: 0
      status: 0
      MirrorMeterReading:
         mRID: 5509D69F8B3535950000000000009183
         description: Real Power(W) Set
         ReadingType:
         accumulationBehavior: 12
         commodity: 1
         dataQualifier: 2
         intervalLength: 300
         powerOfTenMultiplier: 0
         uom: 38
   - device_point: INV_REAC_PWR
      mRID: 5509D69F8B3535950000000000009184
      description: DER Inverter Reactive Power
      roleFlags: 49
      serviceCategoryKind: 0
      status: 0
      MirrorMeterReading:
         mRID: 5509D69F8B3535950000000000009185
         description: Reactive Power(VAr) Set
         ReadingType:
         accumulationBehavior: 12
         commodity: 1
         dataQualifier: 2
         intervalLength: 300
         powerOfTenMultiplier: 0
         uom: 38

   # publishes on the following subscriptions will
   # be available to create and POST readings to the
   # 2030.5 server.
   device_topic: devices/inverter1

   # Nameplate ratings for this der client will be put to the
   # server during startup of the system.
   DERCapability:
   # modesSupported is a HexBinary31 representation of DERControlType
   # See Figure B.34 DER info types for information
   # conversion in python is as follows
   #   "{0:08b}".format(int("500040", 16))
   #   '10100000000000001000000'  # This is a bitmask
   # to generate HexBinary
   #   hex(int('10100000000000001000000', 2))
   #   0x500040
   modesSupported: 500040
   rtgMaxW:
      multiplier: 0
      value: 0
   type: 0

   DERSettings:
   modesEnabled: 100000
   setGradW: 0
   setMaxW:
      multiplier: 0
      value: 0

   # Note this file MUST be in the config store or this agent will not run properly.
   point_map: config:///inverter_sample.csv


.. note::
   The ``point_map`` is configured through the config store at the location inverter_sample.csv.

The following is an example of the point_map file (inverter_sample.csv):

# TODO Include inverter_sample.csv
