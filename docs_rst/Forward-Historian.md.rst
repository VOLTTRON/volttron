Introduction
------------

The forward historian can be found in the core services directory. Use
it to send information to another Volttron instance.

Configuration
-------------

The default configuration file is
*services/core/ForwardHistorian/config* . Change **destination-vip** to
point towards the foreign Volttron instance.

::

    {
        "agentid": "forwarder"
        "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
    }

See Also
~~~~~~~~

`Historians <historians>`__
