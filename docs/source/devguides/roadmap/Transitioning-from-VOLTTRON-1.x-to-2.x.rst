Transitioning from 1.x to 2.x
=============================

VOLTTRON(tm) 2.0 introduces new features such as agent
packaging/verification, agent mobility, and agent resource monitoring.
In addition, some existing features from 1.2 have been refactored. These
changes are mostly confined to platform administration and should
require minimal changes to existing agents aside from fixing imports and
any hardcoded paths/topics in the code.

-  "lite" has been removed from the code tree. For packages, "lite" has
   been replaced by "platform".
-  The agents are no longer built as eggs but are instead built as
   Python wheels
-  There is a new package command instead of using a script to build an
   egg
-  Agents are no longer installed with a 2 step process of
   "install-executable" and "load-agent". Now the agent package is
   configured then installed.
-  Agents are no longer distinguished by their configuration files but
   by a platform provided uuid and/or a user supplied tag.
-  The base topic for publishing data from devices is no longer "RTU"
   but "devices"

The most visible changes have been to the platform commands for building
and managing agents. Please see [PlatformCommands] (PlatformCommands
"wikilink") for these changes.
