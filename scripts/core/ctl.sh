#Script for more easily dealing with a secured platform
#Replace values for the variables with those appropriate for your deployment
#And then use this to call volttron-ctl commands

#VOLTTRON_HOME will be ~/.volttron unless you have specifically changed it. Use the modifed value if you have 
#VIP_SOCKET is what your platform is setup to use for vip-address in its config file
#Curve Key is the public key output during platform start, for instance use the portion in parens:
#2015-08-17 10:26:22,387 () volttron.platform.main INFO: public key: '+=c#-/bCg6DsR1wcxN0^[^9H-v>/5.R.iC==M}ND' (zKmY2tcbDbB6ZHElJpDcBfIIzctjMR81py5-7c8k5E4)
#Public and Secret keys are generated using volttron-ctl keypair. The public key should have credentials in auth.json


#Modify these values for your deployment
export VOLTTRON_HOME=~/.volttron
VIP_SOCKET=tcp://127.0.0.1:9999
SERVER_KEY=<Server public key>
PUBLIC_KEY=<Public portion of keypair>
SECRET_KEY=<Secret portion of keypair>

export VIP_ADDRESS="$VIP_SOCKET?serverkey=$SERVER_KEY&publickey=$PUBLIC_KEY&secretkey=$SECRET_KEY"

volttron-ctl $1 --vip-address $VIP_ADDRESS

