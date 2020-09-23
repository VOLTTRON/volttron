.. _IEEE2030_5-Agent:

=====================
IEEE 2030.5 DER Agent
=====================

The IEEE 2030.5 Agent (IEEE2030_5 in the VOLTTRON repository) implements a IEEE 2030.5 server that receives HTTP
`POST`/`PUT` requests from IEEE 2030.5 devices.  The requests are routed to the IEEE 2030.5 Agent over the VOLTTRON
message bus by VOLTTRON's Master Web Service.  The IEEE 2030.5 Agent returns an appropriate HTTP response.  In some
cases (e.g., DERControl requests), this response includes a data payload.

The IEEE 2030.5 Agent maps IEEE 2030.5 resource data to a VOLTTRON IEEE 2030.5 data model based on SunSpec, using block
numbers and point names as defined in the SunSpec Information Model, which in turn is harmonized with 61850.  The data
model is given in detail below.

Each device's data is stored by the IEEE 2030.5 Agent in an `EndDevice` memory structure.  This structure is not
persisted to a database.  Each `EndDevice` retains only the most recently received value for each field.

The IEEE 2030.5 Agent exposes RPC calls for getting and setting EndDevice data.

View the :ref:`IEEE 2030.5 agent specification document <IEEE2030_5-Specification>` to learn more about IEEE 2030.5 and
the IEEE 2030.5 agent and driver.


.. toctree::

   ieee2030_5-specification
