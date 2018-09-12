.. _TopicWatcher:

Topic Watcher Agent
===================

The Topic Watcher Agent subscribes to a set of configured topics and publishes an alert if
they are not published within a specified time limit. In addition to "standard" topics
the Topic Watcher Agent supports inspecting device `all` topics. This can be useful when
a device contains volatile points that may not be published.


Configuration
-------------

Topics are organied by groups. Any alerts raised will summarize all missing
topics in the group.

Individual topics have two configuration options. For standard topics
configuration consists of a key value pair of the topic to its time limit.

The other option is for `all` publishes. The topic key is paired with a
dictionary that has two keys, `"seconds"` and `"points"`. `"seconds"` is the
topic's time limit and `"points"` is a list of points to watch.

.. code-block:: python

    {
        "groupname": {
            "devices/fakedriver0/all": 10,

            "devices/fakedriver1/all": {
                "seconds": 10,
                "points": ["temperature", "PowerState"]
            }
        }
    }
