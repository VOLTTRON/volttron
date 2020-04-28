.. _FakeDriver:

Fake Driver
===========

The FakeDriver is included as a way to quickly see data published to the message bus in a format 
that mimics what a true Driver would produce. This is an extremely simple implementation of the 
:ref:`VOLTTRON driver framework<VOLTTRON-Driver-Framework>`   

Make a script to build and deploy the fake driver.

- Create a config directory (if one doesn't already exist). All local config files will be 
  worked on here.
- cp examples/configurations/drivers/fake.config config/
- Edit registry_config for the paths on your system

fake.config::

    {
        "driver_config": {},
        "registry_config":"config://fake.csv",
        "interval": 5,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat",
        "driver_type": "fakedriver",
        "publish_breadth_first_all": false,
        "publish_depth_first": false,
        "publish_breadth_first": false
   	}

- cp services/core/MasterDriverAgent/master-driver.agent config/fake-master-driver.config
- Add fake.csv and fake.config to the :ref:`configuration store<config-store>`.
- Edit fake-master-driver.config to reflect paths on your system

fake-master-driver.config::

    {
        "driver_scrape_interval": 0.05
    }

- Use the scripts/install-agent.py script to install the Master Driver agent:

::

    python scripts/install-agent.py -s services/core/MasterDriverAgent -c config/fake-master-driver.config

- If you have a :ref:`Listener Agent<Listener-Agent>` already installed, you should start seeing data being published to the bus.
