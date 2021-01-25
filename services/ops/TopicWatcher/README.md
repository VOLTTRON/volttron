##Topic Watcher Agent

The Topic Watcher Agent listens to a set of configured topics and publishes an alert if they are not published within 
some time limit.  In addition to “standard” topics the Topic Watcher Agent supports inspecting device "all" topics. This
can be useful when a device contains volatile points that may not be published.

###Requirements

The Topic Watcher agent requires the Sqlite 3 package. This package can be installed in an activated environment with:

    pip install sqlite3

###Configuration

Topics are organized by groups in a JSON structure with the group's identifier as the key. Any alerts raised will 
summarize all missing topics in the group.

Individual topics have two configuration options.  For standard topics configuration consists of a key value pair of the
topic to its time limit.

    {
        "groupname: {
            "devices/campus/building/point": 10
        }
    }


    {
        "groupname": {
            "devices/fakedriver0/all": 10,
    
            "devices/fakedriver1/all": {
                "seconds": 10,
                "points": ["temperature", "PowerState"]
            }
        }
    }
