_topics = {
    'volttron_to_matlab': 'matlab/to_matlab/1',
    'matlab_to_volttron': 'matlab/to_volttron/1',
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

    'agent_public': 'qtYEDEqN7G0MAuw-HhxXFc5lTyTaqCoYdgLHL5WZBBc',
    'agent_secret': 'Qq9AI5ZeL5cFS9_-ZtTklnxCHeeq-rk4gXzl5pKaJLk',

    # Public server key from the remote platform.  This can be
    # obtained using the command:
    # volttron-ctl auth serverkey
    'server_key': '4e-WQpYCsvyamj23k44OO9673aWGY4blR98b2vC7yQ4'

}


def remote_url():
    return "{vip_address}:{port}?serverkey={server_key}" \
        "&publickey={agent_public}&" \
        "secretkey={agent_secret}".format(**_params)
