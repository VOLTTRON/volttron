## Stand Alone File Watcher example agent

This python script will listen to the specified files and publishupdates to specific topics on the remote instance.

Setup:
1. Make sure volttron instance is running using tcp address. use vcfg
    command to configure the volttron instance address.

2. Update settings.py

3. Add this standalone agent to volttron auth entry using vctl auth add
command. Provide ip of the volttron instance when prompted for
address[]: and  provide public key of standalone agent when prompted
for credentials[]:<br/>
For more details see
https://volttron.readthedocs.io/en/main/platform-features/control/authentication-commands.html?highlight=%22agent%20authentication%22#how-to-authenticate-an-agent-to-communicate-with-volttron-platform

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

4. With a volttron activated shell this script can be run with: 
```
python standalonefilewatchpublisher.py
```