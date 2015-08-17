#Script for more easily dealing with a secured platform
#Replace values on the command line with those appropriate for your deployment
#And then use this to call volttron-ctl commands

#VIP-SOCKET is what your platform is setup to use for vip-address in its config file
#Curve Key is the public key output during platform start, for instance use the portion in parens:
#2015-08-17 10:26:22,387 () volttron.platform.main INFO: public key: '+=c#-/bCg6DsR1wcxN0^[^9H-v>/5.R.iC==M}ND' (zKmY2tcbDbB6ZHElJpDcBfIIzctjMR81py5-7c8k5E4)
#Public and Secret keys are generated using volttron-ctl keypair. The public key should have credentials in auth.json

#An example of a properly filled out line is:
#VOLTTRON_HOME=~/.volttron volttron-ctl $1 --vip-address 'tcp://127.0.0.1:999?serverkey=Yvv93Zj2qClyNsARJjP4CoHqxzPSTRtaljyFXNc5t30&publickey=pb348NuNq7RG36K2OQibykA1hKEbPsv0FOzuITwQW34&secretkey=rHagvIt931AdUJj-WR43B98lk5zEl-h0FIlLLFi9Ue0'


#Please edit this line for your deployment
VOLTTRON_HOME=~/.volttron volttron-ctl $1 --vip-address '<VIP-SOCKET>?serverkey=<Curve Key>&publickey=<Public key>&secretkey=<Secretkey>'