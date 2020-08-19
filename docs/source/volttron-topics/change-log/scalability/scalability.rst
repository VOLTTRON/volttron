.. _Scalability:

Scalability Setup
~~~~~~~~~~~~~~~~~

Core Platform
-------------

-  VIP router - how many messages per second can the router pass
-  A single agent can connect and send messages to itself as quickly as
   possible
-  Repeat but with multiple agents
-  Maybe just increase the number of connected but inactive agents to
   test lookup times
-  Inject faults to test impact of error handling

-  Agents
-  How many can be started on a single platform?
-  How does it affect memory?
-  How is CPU affected?

Socket types
------------

-  inproc - lockless, copy-free, fast
-  ipc - local, reliable, fast
-  tcp - remote, less reliable, possibly much slower
-  test with different

   -  latency
   -  throughput
   -  jitter (packet delay variation)
   -  error rate

Subsystems
----------

-  ping - simple protocol which can provide baseline for other
   subsystems
-  RPC - requests per second
-  Pub/Sub - messages per second
-  How does it scale as subscribers are added

Core Services
-------------

-  historian
-  How many records can be processed per second?
-  drivers
-  BACnet drivers use a virtual BACnet device as a proxy to do device
   communication. Currently there is no known upper limit to the number
   of devices that can be handled at once. The BACnet proxy opens a
   single UDP port to do all communication. In theory the upper limit is
   the point when UDP packets begin to be lost due to network
   congestion. In practice we have communicated with ~190 devices at
   once without issue.
-  ModBUS opens up a TCP connection for each communication with a device
   and then closes it when finished. This has the potential to hit the
   limit for open file descriptors available to the master driver
   process. (Before, each driver would run in a separate process, but
   that quickly uses up sockets available to the platform.) To protect
   from this the master driver process raises the total allowed open
   sockets to the hard limit. The number of concurrently open sockets is
   throttled at 80% of the max sockets. On most Linux systems this is
   about 3200. Once that limit is hit additional device communications
   will have to wait in line for a socket to become available.

Tweaking tests
--------------

-  Configure message size
-  Perform with/without encryption
-  Perform with/without authentication

Hardware profiling
------------------

-  Perform tests on hardware of varying resources: Raspberry Pi, NUC,
   Desktop, etc.

Scenarios
---------

-  One platform controlling large numbers of devices
-  One platform managing large numbers of platforms
-  Peer communication (Hardware demo type setup)

Impact on Platform
------------------

What is the impact of a large number of devices being scraped on a
platform (and how does it scale with the hardware)?

-  Historians
-  At what point are historians unable to keep up with the traffic being
   generated?
-  Is the bottleneck the sqlite cache or the specific implementation
   (SQLite, MySQL)
-  Do historian queues grow so large we have a memory problem?
-  Large number of devices with small number of points vs small number
   of devices with large number of points
-  How does a large message flow affect the router?
-  Examine effects of the watermark (does increasing help)
-  Response time for vctl commands (for instance: status)
-  Affect on round trip times (Agent A sends message, Agent B replies,
   Agent A receives reply)
-  Do messages get lost at some point (EAgain error)?
-  What impact does security have? Are things significantly faster in
   developer-mode? (Option to turn off encryption, no longer available)

-  | Regulation Agent
   | Every 10 minutes there is an action the master node determines.
     Duty cycle cannot be faster than that but is set to 2 seconds for
     simulation.
   | Some clients miss duty cycle signal
   | Mathematically each node solves ODE.
   | Model notes accept switch on/off from master.
   | Bad to lose connection to clients in the field

Chaos router to introduce delays and dropped packets.

MasterNode needs to have vip address of clients.

Experiment capture historian - not listening to devices, just capturing
results

-  Go straight to db to see how far behind other historians


.. toctree::

   scalability-improvements
   testing-driver-scalability
