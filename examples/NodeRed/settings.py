# List of topics to be watched. Messages received will be written to stdout.
topic_prefixes_to_watch = ['']

# Seconds between hearbeat publishes
heartbeat_period = 10

# Volttron address and keys used to create agents
agent_kwargs = {
    # Volttron VIP address
    'address': 'tcp://127.0.0.1:22916',

    # Required keys for establishing an encrypted VIP connection
    'secretkey': '',
    'publickey': '',
    'serverkey': '',

    # Don't use the configuration store
    'enable_store': False,
}
