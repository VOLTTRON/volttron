.. _Driven-Applications:

Driven Agents
=============

Configuration for running OpenEIS applications within VOLTTRON.
---------------------------------------------------------------

The configuration of an agent within VOLTTRON requires a small
modification to the imports of the OpenEIS application and a couple of
configuration parameters.

Import and Extend
~~~~~~~~~~~~~~~~~

::

    from volttron.platform.agent import (AbstractDrivenAgent, Results)
    ...
    class OpeneisApp(AbstractDrivenAgent):

Configuration
~~~~~~~~~~~~~

The two parameters that are necessary in the json configuration file are
"application" and "device". An optional but recommended argument should
also be added "agentid".

::

    {
        "agentid": "drivenlogger1",
        "application": "drivenlogger.logdevice.LogDevice",
        "device": "pnnl/isb1/oat",
        ...
    }

Any other keys will be passed on to the openeis application when it is
run.
