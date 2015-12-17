# These topic will be watched.  The messages will be written to
# standard out.
topics_prefixes_to_watch = (
	'devices',
	'heartbeat/anybody',
	'heartbeat/admin_only',
)

heartbeat_period = 10

# The parameters dictionary is used to populate the agent's
# remote vip address.
_params = {
	# The root of the address.
	'vip_address': 'tcp://127.0.0.1',
	'port': 55055,

	# public and secret key for the standalonelistener agent.
	# These can be created from the volttron-ctl keypair command.
	'agent_public': 'XR-l7nMBB1zDRsUS2Mjb9lePkcNsgoosHKpCDm6D9TI',
	'agent_secret': '3cjyXbfFrdV04khkIWj9SFeLDWY8_4V1DCuVz0w8A4c',

	# Public server key from the remote platform.  This can be
	# obtained from the starting of the platform volttron -v.
	# The output will include public key: ....
	'server_key': '4vn5_n_zMlk9K_p5RKcX48-8xdzWrnUgjB0IW-xEJDE'
}

def remote_url():
	return "{vip_address}:{port}?serverkey={server_key}" \
		"&publickey={agent_public}&" \
		"secretkey={agent_secret}".format(**_params)

