Example Multi-platform deployment
---------------------------------

These instructions are intended for early adopters who wish to setup
VOLTTRON 3.0 platforms on multiple computers communicating with a
VOLTTRON Central instance. VOLTTRON 3.0 is still under development and
these instructions will change as the process is simplified.

On the machine running the VOLTTRON Central agent

| Modify a copy of
volttron/scripts/management-service-demo/volttron-central-config
| Change the ip address to the ip of the machine hosting VOLTTRON
Central
|  "server" : {
|  "host": "",
|  "port": 8080
|  },

Replace the hashed passwords with your own using:

::

    import hashlib, uuid
    hashlib.sha512("your password").hexdigest()

Package, install, and start the volttron central agent using this config
file.

On all machines:

| To run without encryption
| Truncate to 0 bytes, or delete then touch ~/.volttron/curve.key

Create a config file to set VIP socket to an externally visible port

| create the file: ~/.volttron/config
| with the content:
| vip-address=tcp://:8081

| Create a configuration for the platform agent
| filename: platform-config

| {
|  "agentid": "Your Agent Name",
|  "agent\_type": "platform node",
|  "volttron\_central\_vip\_address": "tcp://:8081"
| }

Package, install, and start the platform agent agent.

Once all this is done, go to http://\ :8080/

Log in using the password you created for admin above.

| Open the console tab to see the authorization string:
|  "authorization": "ed97f9e5-6f6e-49f4-92ca-d532eb66ab83"

| In another browser go to:
| http://\ :8080/register-platforms.html

Put the auth string into "Auth Token"

Set vip.identity to "platform.agent"

Set Agent Id to any string you wish to use to identify this platform

Set VIP Address to the vip address setup in the config file for the
platform you are attempting to register

After clicking "Register Platform" go back to the other browser and
refresh it. The registered platform should appear.
