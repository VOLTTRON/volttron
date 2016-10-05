FileWatchPulblisher Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~


Introduction
============

FileWatchPublisher agent watches files for changes and publishes those changes per line on the corresponding topics.
Files and topics should be provided in the configuration.

Configuration
-------------

A simple configuration for FileWatchPublisher with two files to monitor is as follows:

::

    [
        {
            "file": "/var/log/syslog",
            "topic": "platform/syslog"
        },
        {
            "file": "/home/volttron/tempfile.txt",
            "topic": "temp/filepublisher"
        }
    ]

Using this example configuration, FileWatchPublisher will watch syslog and tempFile.txt files and
publish the changes per line on their respective topics.
