.. _FakeDriver:

.. role:: bash(code)
   :language: bash

Fake Driver
===========

The FakeDriver is included as a way to quickly see data published to the message bus in a format
that mimics what a true Driver would produce. This is an extremely simple implementation of the
:ref:`VOLTTRON driver framework<VOLTTRON-Driver-Framework>`.

Here, we make a script to build and deploy the fake driver.


- Create a config directory (if one doesn't already exist) inside your Volttron repository: :code:`mkdir config`. All local config files will be worked on here.
- Copy over the example config file and registry config file:

.. code-block:: bash

    `cp examples/configurations/drivers/fake.config config/`
    `cp examples/configurations/drivers/fake.csv config/`

- Edit :code:`registry_config` for the paths on your system:

fake.config::

    {
        "driver_config": {},
        "registry_config": "config://fake.csv",
        "interval": 5,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat",
        "driver_type": "fakedriver",
        "publish_breadth_first_all": false,
        "publish_depth_first": false,
        "publish_breadth_first": false
   	}

- Create a copy of the Master Driver config:

.. code-block:: bash

    cp examples/configurations/drivers/master-driver.agent config/fake-master-driver.config

- Add fake.csv and fake.config to the :ref:`configuration store<config-store>`:

.. code-block:: bash

    vctl config store platform.driver devices/campus/building/fake config/fake.config
    vcfl config store platform.driver fake.csv config/fake.csv --csv

- Edit fake-master-driver.config to reflect paths on your system

fake-master-driver.config::

    {
        "driver_scrape_interval": 0.05
    }

- Use the scripts/install-agent.py script to install the Master Driver agent:

.. code-block:: bash

    python scripts/install-agent.py -s services/core/MasterDriverAgent -c config/fake-master-driver.config

- If you have a :ref:`Listener Agent<Listener-Agent>` already installed, you should start seeing data being published to the bus.
