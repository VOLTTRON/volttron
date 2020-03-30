.. _SysMon_Agent:

=======================
System Monitoring Agent
=======================

The System Monitoring Agent (colloquially "SysMon") can be installed on the platform to monitor
various system resource metrics, including percent CPU utilization, percent system memory (RAM)
utilization, and percent storage (disk) utilization based on disk path.

Configuration
-------------

The SysMon agent configuration includes options for setting the base publish topic as well as
intervals in seconds for checking the various system resource utilization levels.

::

        {
            "base_topic": "datalogger/log/platform",
            "cpu_check_interval": 5,
            "memory_check_interval": 5,
            "disk_check_interval": 5,
            "disk_path": "/"
        }

The base topic will be formatted with the name of the function call used to determine the
utilization percentage for the resource. For example, using the configuration above, the topic
for cpu utilization would be "datalogger/log/platform/cpu_percent".

The disk path string can be set to specify the full path to a specific system data storage "disk".
Currently the SysMon agent supports configuration for only a single disk at a time.

Periodic Publish
----------------

At the interval specified by the configuration option for each resource, the agent will automatically
query the system for the resource utilization statistics and publish it to the message bus using the
topic as previously described. The message content for each publish will contain only a single numeric
value for that specific topic. Currently "scrape_all" style publishes are not supported.


Example Publishes:

::

    2020-03-10 11:20:33,755 (listeneragent-3.3 7993) listener.agent INFO: Peer: pubsub, Sender: platform.sysmon:, Bus: , Topic: datalogger/log/platform/cpu_percent, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
    4.8
    2020-03-10 11:20:33,804 (listeneragent-3.3 7993) listener.agent INFO: Peer: pubsub, Sender: platform.sysmon:, Bus: , Topic: datalogger/log/platform/memory_percent, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
    35.6
    2020-03-10 11:20:33,809 (listeneragent-3.3 7993) listener.agent INFO: Peer: pubsub, Sender: platform.sysmon:, Bus: , Topic: datalogger/log/platform/disk_percent, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:



JSON RPC Methods
----------------

The VIP subsystem developed for the VOLTTRON message bus supports remote procedure calls (RPC), which
can be used to more directly fetch data from the SysMon agent. Examples are provided below for each
RPC call.

::

    # Get Percent CPU Utilization
    self.vip.rpc.call(PLATFORM.SYSMON, "cpu_percent).get()

    # Get Percent System Memory Utilization
    self.vip.rpc.call(PLATFORM.SYSMON, "memory_percent).get()

    # Get Percent Storage "disk" Utilization
    self.vip.rpc.call(PLATFORM.SYSMON, "disk_percent).get()
