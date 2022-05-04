## Stand Alone MatLab Example Agent

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

4. Update settings.py with the topics this agent should watch

6. Add this standalone agent to volttron auth entry by inserting the generated public key to this command:
```
vctl auth add --credentials <generated_publickey>
```

7. With a volttron activated shell this script can be run like:
```
python standalone_matlab.py
```