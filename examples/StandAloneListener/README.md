## Stand Alone Listener Example Agent
This python script will listen to the defined vip address for specific
topics. This script prints all output to standard out rather than using the
logging facilities. This script will also publish a heart beat
(which will be returned if listening to the heartbeat topic).

Setup:
1. Make sure volttron instance is running using tcp address. Use vcfg
command to configure volttron instance address,.

2. Create a public and secret key pair for this agent using this command:
```
vctl auth keypair
```
Update settings.py with your public and secret keys

3. Create a public server key using this command: 
```
vctl auth serverkey
```
Update settings.py with this server key

4. Update settings.py with the topics you want to be watched by this agent and update the heartbeat period

3. Add this standalone agent to volttron auth entry using this command:
```
vctl auth add
```
Provide IP of the volttron instance when prompted for
address[]: and  provide public key of standalone agent when prompted
for credentials[]:
For more details, see [here](https://volttron.readthedocs.io/en/main/platform-features/control/authentication-commands.html?highlight=%22agent%20authentication%22#how-to-authenticate-an-agent-to-communicate-with-volttron-platform)

Example command:
```
(volttron)[vdev@cs_cbox myvolttron]$ vctl auth add
domain []:
address []: 127.0.0.1
user_id []:
capabilities (delimit multiple entries with comma) []:
roles (delimit multiple entries with comma) []:
groups (delimit multiple entries with comma) []:
mechanism [CURVE]:
credentials []: GsEq7mIsU6mJ31TN44lQJeGwkJlb6_zbWgRxVo2gUUU
comments []:
enabled [True]:
```

4. With a volttron activated shell this script can be run with:
```
python standalonelistener.py
```

Example output to standard out:
```
{"topic": "heartbeat/standalonelistener",
    "headers": {"Date": "2015-10-22 15:22:43.184351Z", "Content-Type": "text/plain"},
    "message": "2015-10-22 15:22:43.184351Z"}
{"topic": "devices/building/campus/hotwater/heater/resistive/information/power/part_realpwr_avg",
    "headers": {"Date": "2015-10-22 00:45:15.480339"},
    "message": [{"part_realpwr_avg": 0.0}, {"part_realpwr_avg": {"units": "percent", "tz": "US/Pacific", "type": "float"}}]}
```
The heartbeat message is a simple plain text message with just a date stamp

A "data" message contains an array of 2 elements. The first element 
contains a dictionary of (point_name: value) pairs. The second element
contains context around the point data and the "Date" header.