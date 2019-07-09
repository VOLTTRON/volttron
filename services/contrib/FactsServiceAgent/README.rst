Ecorithm's Facts Service Agent
==============================
Ecorithm's Facts Service agent is used to push data to a remote cloud storage solution at frequent intervals.

.. figure:: https://assets.ecorithm.com/static/ecoweb/img/historian_2x.png
   :alt: Real-time Historian on Ecorithm's Platform
   :align: center
   :width: 61%

   *Real-time Historian on Ecorithm's Platform*

Features
--------
- Sending data to Ecorithm's Facts Service `API <https://facts.prod.ecorithm.com/api/v1/>`_ using ``requests`` module
- Database to store topics not being sent to the API when running a multi-building configuration
- Automatic backup of data if API is unreachable using ``Base Historian`` agent built-in backup database

Prerequisites
-------------
- An Ecorithm account: visit `Ecorithm.com <https://ecorithm.com>`_ for more information
- At minimum, one building attached to your account
- An Internet connection (for HTTPS requests)

Recommended Setup
-----------------
- ``BACnet Proxy`` Agent
- ``Facts Service`` Agent
- ``Master Driver`` Agent

**Note**: If you're planning on using only the Facts Service agent, it is recommended to disable the ``Platform`` agent since communication with a Volttron Central instance isn't required, hence saving resources.

Configuration
-------------
Default configuration::

    {
      "facts_service_parameters": {
        "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
        "username": "",
        "password": "",
        "unmapped_topics_database": "unmapped_topics.db"
      },
      "building_parameters": {
        "building_id": null,
        "topic_building_mapping": {}
      },
      "retry_period": 300.0,
      "submit_size_limit": 1000,
      "max_time_publishing": 30.0,
      "backup_storage_limit_gb": null,
      "topic_replace_list": [],
      "gather_timing_data": false,
      "readonly": false,
      "capture_device_data": true,
      "capture_log_data": false,
      "capture_analysis_data": false,
      "capture_record_data": false,
      "message_publish_count": 10000,
      "history_limit_days": null,
      "storage_limit_gb": null
    }

Minimum changes to apply:

- Fill ``username`` and ``password`` with your Ecorithm's account credentials
- If you are trending one building only, set ``building_id`` to the ID of the building and leave ``topic_building_mapping`` to ``{}``.
- If you are trending points from multiple buildings, leave ``building_id`` to ``null``. Set ``topic_building_mapping`` as a dictionary mapping ``topic`` to ``building_id`` e.g.::

    "building_parameters": {
      "building_id": null,
      "topic_building_mapping": {
        "fake_campus/fake_building_A/fake_device_A/point": 1,
        "fake_campus/fake_building_A/fake_device_B/point": 1,
        "fake_campus/fake_building_B/fake_device/point": 42
      }
    },

Other settings belong to the ``BaseHistorian`` agent.

Installation
------------

1. Start Volttron
2. From an activated shell, run ``python scripts/install-agent.py -s services/contrib/FactsServiceAgent -c services/contrib/FactsServiceAgent/config --start --enable``
