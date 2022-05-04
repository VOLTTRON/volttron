## Stand Alone File Watcher example agent

This python script will listen to the specified files and publish updates to specific topics on a volttron instance.

Setup:
1. Make sure volttron instance is running using tcp address. Use vcfg command to configure the volttron instance address.

2. Create a public and secret key pair for this agent using this command:
```
vctl auth keypair
```
Update settings.py with the new public and secret keys

3. Determine the public server key of the instance using this command: 
```
vctl auth serverkey
```
Update settings.py with this server key

5. Update the config section of settings.py with the files you want this agent to watch for and
which topics it should publish on for each file.  

4. Add this standalone agent to volttron auth entry using this command:
```
vctl auth add
```
Provide the IP of the volttron instance when prompted for
address[]: and  provide public key of standalone agent when prompted
for credentials[]:<br/>
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
credentials []: rn_V3vxTLMwaIRUEIAIHee4-qM8X70irDThcn_TX6FA
comments []:
enabled [True]:
```

5. With a volttron activated shell, this script can be run with: 
```
python standalonefilewatchpublisher.py
```
