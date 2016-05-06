Data Publisher
==============

The data publisher agent allows the playback of csv data to the message
bus as if it were a device.

::

    {    # basetopic can be devices, analysis, or custom base topic
        "basetopic": "devices",
        "publisherid": "PUBLISHER",
        "maintain_timestamp": 1,

        # Declare standard topic format that identifies campus, building,
        # device (unit), and subdevices (subdevices are optional)
        "campus": "campus1",
        "building": "building1",
        "unit": {
                "rtu4": {
                    "subdevices": []
                },
                "rtu5": {
                    "subdevices": []
                },
                "rtu3": {
                    "subdevices": []
                }
        },
        "unittype_map": {
            ".*Temperature": "Farenheit",
            ".*SetPoint": "Farenheit",
            "OutdoorDamperSignal": "On/Off",
            "SupplyFanStatus": "On/Off",
            "CoolingCall": "On/Off",
            "SupplyFanSpeed": "RPM",
            "Damper*.": "On/Off",
            "Heating*.": "On/Off",
            "DuctStatic*.": "On/Off"
        },
        
        # If a custom topic is desired the entire topic must be configured.
        # e.g., "custom_topic": 'custom/topic/configuration'
        # "custom_topic":
        "input_file": "/home/volttron/shared/data.csv",
        
        # Publish interval in seconds
        "publish_interval": 1,
        
        # Tell the playback to maintain the location in the file if playback stops
        # before the file ends.
        # default 0
        "remember_playback": 1,
        
        # Start playback from 0 even though remember playback may be set.
        # default 0
        "reset_playback": 0
    }

