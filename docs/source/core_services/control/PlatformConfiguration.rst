.. _PlatformConfiguration:
VOLTTRON Environment
====================

By default, the VOLTTRON projects bases its files out of VOLTTRON\_HOME
which defaults to "~/.volttron".

-  ``$VOLTTRON_HOME/agents`` contains the agents installed on the
   platform
-  ``$VOLTTRON_HOME/certificates`` contains the certificates for use
   with the Licensed VOLTTRON code.
-  ``$VOLTTRON_HOME/run`` contains files create by the platform during
   execution. The main ones are the 0MQ files created for publish and
   subcribe.
-  ``$VOLTTRON_HOME/ssh`` keys used by agent mobility in the Licensed
   VOLTTRON code
-  ``$VOLTTRON_HOME/config`` Default location to place a config file to
   override any platform settings.
-  ``$VOLTTRON_HOME/packaged`` is where agent packages created with
   \`volttron-pkg package are created

