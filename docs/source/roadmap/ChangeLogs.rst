Change Logs
===========


1/31/2014
---------

The VOLTTRON(tm) 1.0 release includes the following features:

-  Scheduler 2.0: The new ActuatorAgent scheduler allows applications to
   reserve devices ahead of time
-  SchedulerExample: This simple agent provides an example of publishing
   a schedule request.

VOLTTRON v1.0 also includes features in a beta stage. These features are
slated for release in v1.1 but are included in 1.0 for those who wish to
begin investigating them. These features are:

-  Multi-node communication: Enables platforms to publish and subscribe
   to each other
-  BACNet Driver: Enables reading/writing to devices using the BACNet
   protocol

Included are PNNL developed applications: AFDD and DR which are in the
process of being modified to work with the new scheduler.DR will not
currently function with Scheduler 2.0.

11/7/2013
---------

-  Renamed Catalyst driver to Modbus driver to reflect the generic
   nature of the driver.
-  Changed the configuration for the driver to fully take advantage of
   the Python struct module.

9/9/2013
--------

-  Catalyst registry file update for 372s
-  catalystreg.csv.371 contains the points for the 371

9/4/2013
--------

-  `Scheduling <ActuatorAgent>`__ implemented
-  Logging implemented

8/21/2013
---------

-  Added libevent-dev to required software

8/6/2013
--------

WeatherAgent updated and back into the repository.

7/22/2017
---------

The agent module was split into multiple pieces.

-  The BaseAgent and PublishMixin classes and the periodic decorator
   remain in the agent package.
-  The matching module was moved under the agent package and is now
   available as volttron.lite.agent.matching.
-  The utility functions, like run\_agent (which is deprecated) and the
   base agent ArgumentParser, were moved to volttron.lite.agent.utils.

All low-level messaging that is not agent-specific was moved to
volttron.lite.messaging and includes the following new submodules:

-  headers: contains common messaging headers, like CONTENT\_TYPE, and
   values as constants
-  topics: provides topic templates; see the module documentation for
   details
-  utils: includes the Topic class and other messaging/topic utilities

The listener, control, archiver, and actuator agents were updated to use
and demonstrate the changes above. Some of them also show how to use
agent factories to perform dynamic matching. Using mercurial to show the
diffs between revisions is a good technique for others to use to
investigate how to migrate their agents.

6/24/2013
---------

-  Initial version of ExampleControllerAgent committed. This agent
   monitors outdoor air temp and randomly sets the coolsuppy fan if temp
   has risen since the last reading. Wiki explanation for agent coming
   soon.
-  Updates to ActuatorAgent
-  ListenerAgent updated to reflect latest BaseAgent
-  Use -config option instead of -config\_path when starting agents

6/21/2013
---------

-  Updated ArchiverAgent checked in.
-  ActuatorAgent for sending commands to the controller checked in.

6/19/2013
---------

-  Fixed a command line arg problem in ListenerAgent and updated wiki.

Version 1.0
-----------

This is the initial release of the Volttron Lite platform. The features
contained in it are:

-  Scripts for building the platform from scratch as well as updating
-  A BaseAgent which expresses the basic functionality for an agent in
   the platform as well as hooks for adding functionality
-  Example agents which utilize the BaseAgent to illustrate more complex
   behavior

In addition, this wiki will be constantly updated with documentation for
working with the platform and developing agents in it. We intend to
document as much as possible but please submit TRAC tickets in cases
where documentation does not exist yet or there is difficulty locating
it. Also, this is a living document so feel free to add your own content
to this wiki and even make changes to the documentation if you can
improve on its clarity and usefulness.

Please subscribe to this page to receive notification when new
changelogs are posted for future releases.
