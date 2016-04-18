Basic requirements
------------------

-  Eggsecutable file launchable by platform
-  Subscribe and publish to ZMQ topics

   -  Shut down when shutdown message received on platform topic
   -  React to messages, send out commands

-  BaseAgent

   -  Handles subscribing and reacting to mandatory topics
   -  Provides a pattern to follow
   -  Provides hooks for logic reacting to messages

-  ExampleAgents

   -  Illustrates usage of platform services
   -  Can be modified for specific applications


