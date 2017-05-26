.. _planning-install:

===========================
Planning a VOLTTRON Install
===========================

The 3 major installation types for VOLTTRON are doing development, doing research using VOLTTRON, and 
collecting and managing physical devices.

Development and Research installation tend to be smaller footprint installations. For development, the 
data is usually synthetic or copied from another source. The existing documentation covers development 
installs in significant detail.

Other deployments will have a better installation experience if they consider certain kinds of questions
while they plan their installation.

Questions
=========

  * Do you want to send commands to the machines ?
  * Do you want to store the data centrally ?
  * How many machines do you expect to collect data from on each "collector" ?
  * How often will the machines collect data ?
  * Are all the devices visible to the same network ?
  * What types of VOLTTRON applications do you want to run ?


Commands 
--------

If you wish to send commands to the devices, you will want to install and configure the Volttron Central 
agent. If you are only using VOLTTRON to securely collect the data, you can turn off the extra agents
to reduce the footprint.

Storing Data
------------

VOLTTRON supports multiple historians. mySQL and MongoDB are the most commonly used. As you plan your 
installation, you should consider how quickly you need access to the data and where.  If you are looking 
at the health and well-being of an entire suite of devices, its likely that you want to do that from a 
central location.  Analytics can be performed at the edge by VOLTTRON applications or can be performed
across the data usually from a central data repository.  The latency that you can tolerate in your data 
being available will also determine choices in different agents (ForwardHistorian versus Data Mover)


How Many
--------

The ratio of how many devices-to-collector machine is based on several factors. These include:
   
      * how much memory and network bandwidth the collection machine has.  More = More devices
      * how fast the local storage is can affect how fast the data cache can be written.  Very slow 
        storage devices can fall behind
      
The second half of the "how many" question is how many collector paltforms are writing to a single 
VOLTTRON platform to store data - and whether that storage is local, remote, big enough, etc.

If you are storing more than moderate amount of data, you will probably benefit from installing 
your database on a different machine than your concreate historian machine.  Note:  This is 
contra-indicated if you have a slow network connection between you concrete historian and your database machine.

In synthetic testing up to 6 virtual machines hosting 500 devices each ( 18 points) were easily 
supported by a single centralized platform writing to a Mongo database - using a high speed network.
That central platform experienced very little CPU or memory load when the VOLTTRON Central agent was disabled.


How Often
---------

This question is closely related to the last. A higher sampling frequency will create more data.  This
wil place more work in the storage phase.  


Networks
--------

In many cases, there are constraints on how networks can interact with each other. In many cases, 
these include security considerations.  On some sites, the primary network will be protected from less 
secure networks and may require different installation considerations.  For example, if a data collector
machine and the database machine are on the same network with sufficient security, you may choose
to have the data collector write directly to the database.  If the collector is on an isolated building 
network then you will likely need to use the ForwardHistorian to bridge the two networks.


Other Considerations
--------------------

Physical location and maintenance of collector machines must be considered in all live deployments.
Although the number of data points may imply a heavy load on a data collection box, the physical constraints
may limit the practicality of having more than a single box.  The other side of that discussion is deploying 
many collector boxes may be simpler initially, but may create a maintenance challenge if you don't 
plan ahead on how you apply patches, etc.

Naming conventions should also be considered.  The ability to trace data through the system and identify 
the collector machine and device can be invaluable in debugging and analysis.


