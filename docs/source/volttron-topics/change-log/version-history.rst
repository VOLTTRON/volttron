.. _version-history:

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
