## Stand Alone File Watcher example agent

This python script will listen to the specified files and publish updates to specific topics on a volttron instance.

Setup:
1. Make sure volttron instance is running using tcp address. Use vcfg command to configure the volttron instance address.

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

4. Update the config section of settings.py with the files this agent should watch for and
which topics it should publish on for each file.  

5. Add this standalone agent to volttron auth entry by inserting the generated public key to this command:
```
vctl auth add --credentials <generated_publickey>
```

6. With a volttron activated shell, this script can be run with: 
```
python standalonefilewatchpublisher.py
```
