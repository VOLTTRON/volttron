.. _Weather.gov Agent:

=================
Weather.gov Agent
=================

This agent provides the ability to query for current and forecast weather
data from NOAA. The agent extends BaseWeatherAgent that provides caching of
recently requested data, as well as mapping of weather point names from NOAA's
naming scheme to the standardized CF-conventions scheme.

Requirements
------------
The Weather.Gov agent requires the Pint package. This package can be installed in an
activated environment with:

::

    pip install pint

Configuration
-------------
The following is an example configuration for the Weather.gov agent. All
configuration parameters are optional.

**Parameters**

 1. "database_file" - sqlite database file for weather data caching. Defaults to "weather.sqlite" in the agent's data directory
 2. "max_size_gb" - maximum size of cache database. When cache exceeds this size, data will get purged from cache until the cache is within the configured size.
 3. "poll_locations" - list of locations to periodically poll for current data
 4. "poll_interval" - polling frequency or the number of seconds between each poll.

::

    {
        "database_file": "weather.sqlite",
        "max_size_gb": 1,
        "poll_locations": [{"station": "KLAX"}, {"station": "KPHX"}],
        "poll_interval": 60
    }

Registry Configuration
----------------------
The registry configuration file for this agent can be found in agent's data
directory. This configuration provides the point name mapping from NOAA's point
scheme to the CF-conventions scheme by default. The file leaves the unit name
columns for each point blank, as this agent does not include unit conversion.
Points that do not specify 'Standard_Point_Name' were found to not have a
logical match to any point found in the CF-Conventions. For these points NOAA
point names (Service_Point_Name) will be used.

.. csv-table:: Registry Configuration
    :header: Service_Point_Name,Standard_Point_Name,Service_Units,Standard_Units

    heatIndex,,,
    presentWeather,,,
    seaLevelPressure,air_pressure_at_mean_sea_level,,
    temperature,air_temperature,,

Notes
~~~~~
The WeatherDotGov agent does not utilize an API key, as NOAA allows users to
gather weather data for free, and does not provide nor require keys.

This implementation of the weather agent does not include historical weather
data, as NOAA does not provide an accessible endpoint from which historical
data may be obtained.

Data provided by NOAA is in a nested dictionary format. The base weather agent
does not handle unit conversion for arbitrary nested dictionary format and hence
this agent does not support unit conversion at this time.
