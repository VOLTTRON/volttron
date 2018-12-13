.. _Weather.gov Agent:

=================
Weather.gov Agent
=================

This agent provides the ability to query for current and forecast weather
data from NOAA. The agent provides caching of recently requested data, as
well as mapping of weather point names from NOAA's naming scheme to the
standardized CF-conventions scheme.

Configuration
-------------
The following is an example configuration for the Weather.gov agent. The
'database_file' parameter allows the user to specify a sqlite database file
of his or her choice for weather data caching (by default the agent will use
'weather.sqlite' in the agent's data directory, this parameter may be omitted).
'max_size_gb' allows the user to limit the storage capacity of the cache for
deployments with storage limitations (in many cases this may be omitted or
set to None). 'poll_locations expects a list of location dictionaries to poll
for current data, and 'poll_interval' specifies the number of seconds between
each poll.

::

    {
        'database_file': 'weatherdotgov.sqlite'
        'max_size_gb': 1,
        'poll_locations': [],
        'poll_interval': 5
    }

Registry Configuration
----------------------
The registry configuration file for this agent can be found in agent's data
directory. This configuration provides the point name mapping from NOAA's point
scheme to the CF-conventions scheme by default. The file leaves the unit name
columns for each point blank, as this agent does not include unit conversion.
Points that do not specify 'Standard_Point_Name' were found to not have a
a logical match to any point found in the CF-Conventions (for example,
heatIndex is a non-standardized unit of measurement).

.. csv-table:: Registry Configuration
    :header: Service_Point_Name,Standard_Point_Name,Service_Units,Standard_Units

    heatIndex,,,
    presentWeather,,,
    seaLevelPressure,air_pressure_at_mean_sea_level,,
    temperature,air_temperature,,

Notes
~~~~~
The Weather.Gov agent does not utilize an API key, as NOAA allows users to
gather weather data for free, and does not provide nor require keys.

This implementation of the weather agent does not include historical weather
data, as NOAA does not provide an accessible endpoint from which historical
data may be obtained.

As the data provided by NOAA often contains empty, nested, or difficult to
format data points, this agent does not provide unit conversion at this time.