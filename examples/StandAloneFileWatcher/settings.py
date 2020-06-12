# This config is used by the agent to determine which files to watch
# and which topic additions to that file should be published on.
# The config needs to be taken in as a list, regardless of the number
# of entries.
#
# Example config:
# config = [
#   {
#       "file": "/full/path/to/file",
#       "topic": "topic/to/publish/changes"
#   }
#   ]

config = [
    {
        "file": "/var/log/syslog",
        "topic": "platform/syslog"
    },
    {
        "file": "/volttron/tempfile.csv",
        "topic": "temp/filepublisher"
    }
]

# The parameters dictionary is used to populate the agent's
# remote vip address.
_params = {
    # The root of the address.
    # Note:
    # 1. volttron instance should be configured to use tcp. use command vcfg
    # to configure
    'vip_address': 'tcp://127.0.0.1',
    'port': 22916,

    # public and secret key for the standalonelistener agent.
    # These can be created using the command:  volttron-ctl auth keypair
    # public key should also be added to the volttron instance auth
    # configuration to enable standalone agent access to volttron instance. Use
    # command 'vctl auth add' Provide this agent's public key when prompted
    # for credential.

    'agent_public': 'rn_V3vxTLMwaIRUEIAIHee4-qM8X70irDThcn_TX6FA',
    'agent_secret': 'DY4FhighTlv9UjKlCNIh-1WKp-M5nIHJacWsPZ0ixEs',

    # Public server key from the remote platform.  This can be
    # obtained using the command:
    # volttron-ctl auth serverkey
    'server_key': 'yqhjAOOeRO3Ls6Bih-QoplMWfMcIJJtg_H4uGS8Z9lw'
}


def remote_url():
    return "{vip_address}:{port}?serverkey={server_key}" \
           "&publickey={agent_public}&" \
           "secretkey={agent_secret}".format(**_params)
