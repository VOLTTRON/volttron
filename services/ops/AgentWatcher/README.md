## Agent Watcher

The Agent Watcher is used to monitor agents running on a VOLTTRON instance. Specifically it monitors whether a set of 
VIP identities (peers) are connected to the instance. If any of the peers in the set are not present then an alert will 
be sent.

### Configuration

The agent has two configuration values:

* watchlist: a list of VIP identities to watch on the platform instance
* check-period: interval in seconds between the agent watcher checking the platform peerlist and publishing alerts


    {
        "watchlist": [
            "platform.driver",
            "platform.actuator"
        ],
        "check-period": 10
    }


### Example Publish

The following is an example publish from a platform with an instance of the Platform Driver installed but not running.

    2021-01-25 15:25:43,077 (listeneragent-3.3 5081) __main__ INFO: Peer: pubsub, Sender: watcheragent-0.1_1:, Bus: , 
    Topic: alerts/AgentWatcher/james_watcheragent-0_1_1, Headers: {'alert_key': 'AgentWatcher', 
    'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message: 
    ('{"status": "BAD", "context": "Agent(s) expected but but not running '
     '[\'platform.driver\']", "last_updated": "2021-01-25T23:25:43.065109+00:00"}')
