.. _Config-Actuation:

========================
Config Actuation Example
========================

The Config Actuation example attempts to set points on a device when files are added or updated in its
:ref:`configuration store <VOLTTRON-Configuration-Store>`.


Configuration
-------------

The name of a configuration file must match the name of the device to be actuated.  The configuration file is a JSON
dictionary of point name and value pairs.  Any number of points on the device can be listed in the config.

.. code-block:: python

    {
        "point0": value,
        "point1": value
    }
