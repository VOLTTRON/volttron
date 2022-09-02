# Dark Sky Agent

Powered by [Dark Sky](https://darksky.net/dev)

This agent provides the ability to query for current and forecast
weather data from Dark Sky. The agent extends BaseWeatherAgent that
provides caching of recently requested data, API call tracking, as well
as mapping of weather point names from Darksky\'s naming scheme to the
standardized CF-conventions scheme.

## Requirements

The Dark Sky agent requires the Pint package. This package can be
installed in an activated environment with:

    pip install pint

## Dark Sky Endpoints

The Dark Sky agent provides the following endpoints in addition to those
included with the base weather agent:

### Get Minutely Forecast Data

RPC call to weather service method **'get_minutely_forecast'**

Parameters:

- **locations** - List of dictionaries containing location details. Dark Sky requires

>     [{"lat": <lattitude>, "long": <longitude>},...]

optional parameters:

- **minutes** - The number of minutes for which forecast data should
   be returned. By default, it is 60 minutes as well as the current
   minute. Dark Sky does not provide minutely data for more than one
   hour (60 minutes) into the future.

### Get Daily Forecast Data

RPC call to weather service method **'get_minutely_forecast'**

Parameters:

- **locations** - List of dictionaries containing location details. Dark Sky requires

>     [{"lat": <lattitude>, "long": <longitude>},...]

optional parameters:

- **days** - The number of days for which forecast data should be
  returned. By default, it is the next 7 days as well as the current day.

**Please note: If your forecast request to the Dark Sky agent asks for
more data points than the default, the agent must use an additional API
calls; an additional API call will be used to fetch any records not
included in the default forecast request for the current day, and one
additional call for each subsequent day of data the request would
require, regardless of Dark Sky agent endpoint (If requesting 60 hours
of hourly data Monday night at 8PM, 3 API calls must be made to fulfill
the request: one for the initial request containing 48 hours of data,
one for the remaining 4 hours of Wednesday evening\'s data, and one for
records in Thursday\'s forecast).**

## Configuration

The following is an example configuration for the Dark Sky agent. The
\"api_key\" parameter is required while all others are optional.

**Parameters**

1.  \"api_key\" - api key string provided by Dark Sky - this is required and will not be provided by the VOLTTRON team.
2.  \"api_calls_limit\" - limit of api calls that can be made to the remote before the agent no longer returns weather 
results. The agent will keep track of number of api calls and return an error when the limit is reached without 
attempting a connection to dark sky server. This is primarily used to prevent possible charges. If set to -1, no limit 
will be applied by the agent. Dark sky api might return a error after limit is exceeded. Defaults to -1
3.  \"database_file\" - sqlite database file for weather data caching. Defaults to \"weather.sqlite\" in the agent\'s 
data directory.
4.  \"max_size_gb\" - maximum size of cache database. When cache exceeds this size, data will get purged from cache 
till cache is within the configured size.
5.  \"poll_locations - list of locations to periodically poll for current data.
6.  \"poll_interval\" - polling frequency or the number of seconds between each poll.
7.  \"performance_mode\" - If set to true, request response will exclude extra data points (this is primarily useful 
for reducing network traffic). If set to false, all data points are included in the response, and extra data is cached 
(to reduce the number of API calls used for future RPC calls). Defaults to True.

Example configuration:

    {
        "api_key": "<api key string>",
        "api_calls_limit": 1000,
        "database_file": "weather.sqlite",
        "max_size_gb": 1,
        "poll_locations": [{"lat": 39.7555, "long": -105.2211},
                           {"lat": 46.2804, "long": -119.2752}],
        "poll_interval": 60
    }

## Registry Configuration

The registry configuration file for this agent can be found in agent\'s
data directory. This configuration provides the point name mapping from
the Dark Sky API\'s point scheme to the CF-conventions scheme by
default. Points that do not specify \"Standard_Point_Name\" were found
to not have a logical match to any point found in the CF-Conventions.
For these points Dark Sky point name convention (Service_Point_Name)
will be used.

  |Service_Point_Name   | Standard_Point_Name     |  Service_Units     | Standard_Units |
  |---------------------|-------------------------|--------------------|----------------|
  |precipIntensity      | lwe_precipitation_rate  |millimeter / hour   |meter / second  |
  |precipProbability    |                         |                    |                |
  |temperature          | surface_temperature     | degC               |degK            |
  |apparentTemperature  |                         | degC               |degK            |
  |dewPoint             | dew_point_temperature   | degC               |degK            |


## Notes

The Dark Sky agent requires an API key to be configured in order for
users to request data. A user of the Dark Sky agent must obtain the key
themselves.

API call tracking features will work only when each agent instance uses
its own api key. If API key is shared across multiple dark sky agent
instances, disable this feature by setting api_calls_limit = -1.

As of writing, dark sky gives 1000 daily API calls free for a trial
account. Once this limit is reached, the error \"daily usage limit
exceeded\" is returned. See <https://darksky.net/dev> for details

By default performance mode is set to True and for a given location and
time period only the requested data points are returned. Set
performance_mode to False to query all available data for a given
location and time period if you want to cache all the data points for
future retrieval there by reducing number of API calls.
