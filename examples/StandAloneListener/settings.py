# These topic will be watched.  The messages will be written to
# standard out.
topics_prefixes_to_watch = (
	'devices',
	#'datalogger'
)

heartbeat_period = 10

# The parameters dictionary is used to populate the agent's 
# remote vip address.
_params = {
	# The root of the address.
	'vip_address': 'tcp://127.0.0.1',
	'port': 22916,
	
	# public and secret key for the standalonelistener agent.
	# These can be created from the volttron-ctl keypair command.
	'agent_public': 'PCkAasrFk9ce5d8NWbgaWR5qc1HWncExaQHG0apkKTI',
	'agent_secret': 'D5wv-LjXFBLlQt7PmXMUQsSSW1919zzDh4-fJu_0MTM',
	
	# Public server key from the remote platform.  This can be
	# obtained from the starting of the platform volttron -v.
	# The output will include public key: ....
	'server_key': 'kHTZvPwnAZ8weZXOZVR8p2Ef82WHh-EN6OxwKg9GST8'  
}

def remote_url():
	return "{vip_address}:{port}?serverkey={server_key}" \
		"&publickey={agent_public}&" \
		"secretkey={agent_secret}".format(**_params)
