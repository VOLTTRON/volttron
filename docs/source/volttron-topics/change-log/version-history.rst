.. _Version-History:

===============
Version History
===============

VOLTTRON 1.0 – 1.2
==================

-  Agent execution platform
-  Message bus
-  Modbus and BACnet drivers
-  Historian
-  Data logger
-  Device scheduling
-  Device actuation
-  Multi-node communication
-  Weather service


VOLTTRON 2.0
============

-  Advanced Security Features
-  Guaranteed resource allocation to agents using execution contracts
-  Signing and verification of agent packaging
-  Agent mobility
-  Admin can send agents to another platform
-  Agent can request to move
-  Enhanced command framework


VOLTTRON 3.0
============

-  Modularize Data Historian
-  Modularize Device Drivers
-  Secure and accountable communication using the VIP
-  Web Console for Monitoring and Administering VOLTTRON Deployments


VOLTTRON 4.0
============

- Documentation moved to ReadTheDocs
- VOLTTRON Configuration Wizard
- Configuration store to dynamically configure agents
- Aggregator agent for aggregating topics
- More reliable remote install mechanism
- UI for device configuration
- Automatic registration of VOLTTRON instances with management agent


VOLTTRON 5.0
============

- Tagging service for attaching metadata to topics for simpler retrieval
- Message bus performance improvement
- Multi-platform publish/subscribe for simpler coordination across platforms
- Drivers contributed back for SEP 2.0 and ChargePoint EV


VOLTTRON 6.0
============

- Maintained backward compatibility with communication between zmq and rmq deployments.
- Added DarkSky Weather Agent
- Web Based Additions
- Added CSR support for multiplatform communication
- Added SSL support to the platform for secure communication
- Backported SSL support to zmq based deployments.
- Upgraded VC to use the platform login.
- Added docker support to the test environment for easier Rabbitmq testing.
- Updated volttron-config (vcfg) to support both RabbitMQ and ZMQ including https based instances.
- Added test support for RabbitMQ installations of all core agents.
- Added multiplatform (zmq and rmq based platform) testing.
- Integrated RabbitMQ documentation into the core documentation.


VOLTTRON 7.0rc1
===============


Python3 Upgrade
---------------

- Update libraries to appropriate and compatible versions
- String handling efficiency
- Encode/Decode of strings has been simplified and centralized
- Added additional test cases for frame serialization in ZMQ
- Syntax updates such difference in handling exceptions, dictionaries, sorting lists, pytest markers etc.
- Made bootstrap process simpler
- Resolved gevent monkey patch issues when using third party libraries


RabbitMQ Message Bus
--------------------

- Client code for integrating non-VOLTTRON applications with the message bus
   available at: https://github.com/VOLTTRON/external-clients-for-rabbitmq
- Includes support for MQTT, non-VOLTTRON Python, and Java-based RabbitMQ
  clients


Config store secured
--------------------

- Agents can prevent other agents from modifying their configuration store entry


Known Issues which will be dealt with for the final release:
------------------------------------------------------------

- Python 3.7 has conflicts with some libraries such as gevent
- The VOLTTRON Central agent is not fully integrated into Python3
- CFFI library has conflicts on the Raspian OS which interferes with bootstrapping


VOLTTRON 7.0 Full Release
=========================

This is a full release of the 7.0 version of VOLTTRON which has been refactored to work with Python3.  This release
incorporates community feedback from the release candidate as well as new contributions and features.
Major new features and highlights since the release candidate include:

* Added secure agent user feature which allows agents to be launched as a user separate from the platform.  This
  protects the platform against malformed or malicious agents accessing platform level files
* Added a driver to interface with the Ecobee smart thermostat and make data available to agents on the platform
* Updated VOLTTRON Central UI to work with Python3
* Added web support to authenticate remote VOLTTRON ZMQ message bus-based connections
* Updated ZMQ-based multiplatform RPC with Python 3
* To reduce installation size and complexity, fewer services are installed by default
* MasterDriver dependencies are not installed by default during bootstrap.  To use MasterDriver, please use the
  following command:

  .. code-block:: bash

     python3 bootstrap.py --driver

* Web dependencies are not installed by default during bootstrap.  To use the MasterWeb service, please use the
  following command:

  .. code-block:: bash

     python3 bootstrap.py --web

* Added initial version of test cases for `volttron-cfg` (`vcfg`) utility
* On all arm-based systems, `libffi` is now a required dependency, this is reflected in the installation instructions
* On arm-based systems, Raspbian >= 10 or Ubuntu >= 18.04 is required
* Updated examples and several contributed features to Python 3
* Inclusion of docker in test handling for databases
* A new `/gs` endpoint to access platform services without using Volttron Central through Json-RPC
* A new SCPAgent to transfer files between two remote systems

Known Issues
------------

* Continued documentation updates to ensure correctness
* Rainforest Eagle driver is not yet upgraded to Python3
* A bug in the Modbus TK library prevents creating connections from 2 different masters to a single slave.
* BACnet Proxy Agent and BACnet auto configuration scripts require the version of BACPypes installed in the virtual
  environment of VOLTTRON to be version 0.16.7.  We have pinned it to version 0.16.7 since it does not work properly in
  later versions of BACPypes.
* VOLTTRON 7.0 code base is not fully tested in Ubuntu 20.04 LTS so issues with this combination have not been addressed
