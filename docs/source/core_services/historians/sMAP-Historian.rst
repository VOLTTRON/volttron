.. _sMAP-Historian:

sMAP Historian
==============

This historian allows VOLTTRON data to be published to an sMAP server.
This replaces the DataLogger functionality of V2.0 as well as the
capability of 2.0 drivers to publish directly to sMAP.

To configure this historian the following must be in the config file.
This file is setup to point at the `available Test Instance of
sMAP <sMAP-Test-Instance>`__. For reliable storage, please setup your
own instance.

::

    {
        "agentid": "smap_historian",
        "source": "MyTestSource",
        "archiver_url": "http://smap-test.cloudapp.net",
        "key": "LEq1cEGc04RtcKX6riiX7eaML8Z82xEgQrp7"
    }

That's it! With this configuration, data will be pulled off the message
bus and published to your sMAP server.
