# DataMover Historian

The DataMover Historian is used to send data from one instance of
VOLTTRON to another. This agent is similar to the Forward Historian but
does not publish data on the target platform\'s message bus. Messages
are instead inserted into the backup queue in the target\'s historian.
This helps to ensure that messages are recorded.

If the target instance becomes unavailable or the target historian is
stopped then this agent\'s cache will build up until it reaches it\'s
maximum capacity or the instance and agent comes back online.

The DataMover now uses the configuration store for storing its
configurations. This allows dynamic updating of configuration without
having to rebuild the agent.

## Configuration Options

The following JSON configuration file shows all the options currently
supported by the DataMover agent.

``` {.python}
{
    # destination-serverkey
    #   The destination instance's publickey. Required if the
    #   destination-vip-address has not been added to the known-host file.
    #   See vctl auth --help for all instance security options.
    #
    #   This can be retrieved either through the command:
    #       vctl auth serverkey
    #   Or if the web is enabled on the destination through the browser at:
    #       http(s)://hostaddress:port/discovery/
    "destination-serverkey": null,

    # destination-vip-address - REQUIRED
    #   Address of the target platform.
    #   Examples:
    #       "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
    #       "destination-vip": "tcp://127.0.0.1:23916"
    "destination-vip": "tcp://<ip address>:<port>",

    # destination_historian_identity
    #   Identity of the historian to send data to. Only needed if data
    #   should be sent an agent other than "platform.historian"
    "destination-historian-identity": "platform.historian",

    # remote_identity - OPTIONAL
    #    identity that will show up in peers list on the remote platform
    #    By default this identity is randomly generated
    "remote-identity": "22916.datamover"
}
```
