Obix History Publisher
======================

The following is an example configuration for the Obix History Publisher.

    {
      "url": "http://example.com/obix/histories/EXAMPLE/",
      "username": "username",
      "password": "password",
      # Interval to query interface for updates in minutes.
      # History points are only published if new data is available
      # config points are gathered and published at this interval.
      "check_interval": 15,
      # Path prefix for all publishes
      "path_prefix": "devices/obix/history/",
      "register_config": "config://registry_config.csv"
    }
