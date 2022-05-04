## Stand Alone Listener Example Agent
This python script will listen to the defined vip address for specific
topics. This script prints all output to standard out rather than using the
logging facilities. This script will also publish a heart beat
(which will be returned if listening to the heartbeat topic).

Setup:
1. Make sure volttron instance is running using tcp address. Use vcfg
command to configure volttron instance address.

2. Create a public and secret key pair for this agent using this command:
```
vctl auth keypair
```
Update settings.py with the generated public and secret keys

3. Determine the public server key of the instance using this command: 
```
vctl auth serverkey
```
Update settings.py with this server key

4. Update settings.py with the topics this agent should watch and update the heartbeat period

5. Add this standalone agent to volttron auth entry by inserting the agent's identity (which can be found using `vctl status`)
and the generated public key to this command:
```
vctl auth add --user_id <agent_identity> --credentials <generated_publickey>
```

6. With a volttron activated shell this script can be run with:
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