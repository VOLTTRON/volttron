# VOLTTRON 2030.5 Agent

The VOLTTRON 2030.5 agent communicates with a 2030.5 server using the IEEE 2030.5(2018) protocol.  The primary concern of
this agent is to handle the communication between the platform.driver and the 2030.5 server.  The 2030.5 protocol uses a
REQUEST/RESPONSE pattern meaning that all communication with the 2030.5 server will start with a REQUEST being sent
from the client.

##

```mermaid
  graph TD;
      A-->B;
      A-->C;
      B-->D;
      C-->D;
```
