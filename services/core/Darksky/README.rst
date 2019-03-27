.. _Darksky Agent:

=============
Darksky Agent
=============

Powered by Dark Sky

This agent provides the ability to query for current and forecast weather
data from Dark Sky. The agent extends BaseWeatherAgent that provides caching of
recently requested data, API call tracking, as well as mapping of weather
point names from NOAA's naming scheme to the standardized CF-conventions scheme.

Configuration
-------------

The following is an example configuration for the Dark Sky agent. The 'api_key'
parameter is required while all others are optional.

**Parameters**

 1. 'api_key' - api key string provided by Dark Sky - this is required and will not be provided by the VOLTTRON team
 2. 'database_file' - sqlite database file for weather data caching. Defaults to 'weather.sqlite' in the agent's data directory
 3. 'max_size_gb' - maximum size of cache database. When cache exceeds this size, data will get purged from cache till cache is within the configured size.
 4. 'poll_locations - list of locations to periodically poll for current data
 5. 'poll_interval' - polling frequency or the number of seconds between each poll.
 6. 'performance_mode' - If set to true, request response will exclude extra data points (this is primarily useful for reducing network traffic). If set to false, all data points are included in the response, and extra data is cached (to reduce the number of API calls used for future RPC calls).

::

    {
        'api_key': '<api key string>',
        'database_file': 'weather.sqlite',
        'max_size_gb': 1,
        'poll_locations': [{"lat": 39.7555, "long": -105.2211},
                           {"lat": 46.2804, "long": -119.2752}],
        'poll_interval': 60
    }

Registry Configuration
----------------------
The registry configuration file for this agent can be found in agent's data
directory. This configuration provides the point name mapping from the Dark Sky
API's point scheme to the CF-conventions scheme by default. Points that do not
specify 'Standard_Point_Name' were found to not have a logical match to any
point found in the CF-Conventions. For these points Dark Sky point name
convention (Service_Point_Name) will be used.

.. csv-table:: Registry Configuration
    :header: Service_Point_Name,Standard_Point_Name,Service_Units,Standard_Units

    precipIntensity,lwe_precipitation_rate,millimeter / hour,meter / second
    precipProbability,,,
    temperature,surface_temperature,degC,degK
    apparentTemperature,,,
    dewPoint,dew_point_temperature,degC,degK

Notes
~~~~~
The Dark Sky agent requires an API key to be configured in order for users to
request data. A user of the Dark Sky agent must obtain the key themselves.

Each key has the limitation of 1000 daily API calls, after which the service
indicates "daily usage limit exceeded" and data will not be returned. As the
VOLTTRON team desires to keep VOLTTRON services free, the agent is limited to
1000 API calls.

To help with data availability, data is cached for reuse in later RPC requests.
By default performance mode is set to False to ensure that the maximum amount of
data is cached.