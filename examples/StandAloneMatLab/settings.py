_topics = {
        'volttron_to_matlab': 'matlab/to_matlab/1',
        'matlab_to_volttron': 'matlab/to_volttron/1'
        }

# The parameters dictionary is used to populate the agent's 
# remote vip address.
_params = {
	# The root of the address.
	# Note:
	# 1. volttron instance should be configured to use tcp. use command vcfg
	# to configure
	'vip_address': 'tcp://192.168.56.101',
	'port': 22916,
	
	# public and secret key for the standalone_matlab agent.
	# These can be created using the command:  volttron-ctl auth keypair
	# public key should also be added to the volttron instance auth
	# configuration to enable standalone agent access to volttron instance. Use
	# command 'vctl auth add' Provide this agent's public key when prompted
	# for credential.

	'agent_public': 'dpu13XKPvGB3XJNVUusCNn2U0kIWcuyDIP5J8mAgBQ0',
	'agent_secret': 'Hlya-6BvfUot5USdeDHZ8eksDkWgEEHABs1SELmQhMs',
	
	# Public server key from the remote platform.  This can be
	# obtained using the command:
	# volttron-ctl auth serverkey
	'server_key': 'QTIzrRGQ0-b-37AbEYDuMA0l2ETrythM2V1ac0v9CTA'

}

def remote_url():
	return "{vip_address}:{port}?serverkey={server_key}" \
		"&publickey={agent_public}&" \
		"secretkey={agent_secret}".format(**_params)
