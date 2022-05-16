## Web RPC Example Agent

This example exposes the VOLTTRON web API through a python class that that does not depend on VOLTTRON proper. 
A VOLTTRON Central Agent must be running on the url passed to the constructor.

To set up the Volttron instance for this agent:
1. Start Volttron with this command:
```
./start-volttron --bind-web-address https://127.0.0.1:8443
```

2. Run `vcfg` and work through the questions following the example below:<br/>
**Be sure to allow volttron central to control the instance, install the platform historian, install the platform driver, 
and install a fake device on the platform driver.**
```
Is this the volttron you are attempting to setup? [Y]: y
Will this instance be controlled by volttron central? [Y]: y
Configuring /home/volttron/git/myvolttron/services/core/VolttronCentralPlatform.
What is the hostname for volttron central? [https://volttron1]: 127.0.0.1      
What is the port for volttron central? [8443]: 
Should the agent autostart? [N]: y
Would you like to install a platform historian? [N]: y
Configuring /home/volttron/git/myvolttron/services/core/SQLHistorian.
Should the agent autostart? [N]: y
Would you like to install a platform driver? [N]: y
Configuring /home/volttron/git/myvolttron/services/core/PlatformDriverAgent.
Would you like to install a fake device on the platform driver? [N]: y
Should the agent autostart? [N]: y
Would you like to install a listener agent? [N]: n
``` 

3. Install the VolttronCentral agent and start it up.

4. Make sure the platform driver, platform historian, volttron central platform, and volttron central agents are all running. 



