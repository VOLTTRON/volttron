# Ambient Weather Agent {#Ambient Weather Agent}

The Ambient weather agent provides the ability to query for current
weather data from Ambient weather stations via the Ambient weather API.
The agent inherits features of the Volttron BaseWeatherAgent which
provides caching of recently recieved data, as well as point name
mapping and unit conversion using the standardized CF-conventions
scheme.

The values from the Ambient weather station can be accessed through the
cloud platform which can be accessed at
<https://dashboard.ambientweather.net/dashboard>

Two API Keys are required for all REST API requests:

> applicationKey - identifies the developer / application. To request an
> application key please email <support@ambientweather.com>
>
> apiKey - grants access to past/present data for a given user\'s
> devices. A typical consumer-facing application will initially ask the
> user to create an apiKey on thier AmbientWeather.net account page
> (<https://dashboard.ambientweather.net/account>) and paste it into the
> app. Developers for personal or in-house apps will also need to create
> an apiKey on their own account page.

API requests are capped at 1 request/second for each user\'s apiKey and
3 requests/second per applicationKey. When this limit is exceeded, the
API will return a 429 response code. This will result in a response from
the Ambient agent containing \"weather_error\" and no weather data.

## Ambient Endpoints

The Ambient Weather agent provides only current weather data (all other
base weather endpoints are unimplemented, and will return a record
containing \"weather_error\" if used).

The location format for the Ambient agent is as follows:

> {\"location\": \"\<location_string\>\"}

Ambient locations are Arbitrary string identifiers given to a weather
station by the weather station owner/operator.

This is an example response:

    2019-12-17 15:35:56,395 (listeneragent-3.3 3103) listener.agent INFO: Peer: pubsub, Sender: platform.ambient:, Bus: , Topic: weather/poll/current/all, Headers: {'Date': '2019-12-17T23:35:56.392709+00:00', 'Content-Type': 'Content-Type', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
    [{'location': 'Lab Home A',
      'observation_time': '2019-12-18T07:33:00.000000+00:00',
      'weather_results': {'batt1': 1,
                          'battout': 1,
                          'dateutc': 1576625580000,
                          'dewPointin': 39.6,
                          'feelsLikein': 70.2,
                          'humidity1': 1,
                          'humidityin': 31,
                          'macAddress': '50:F1:4A:F7:3C:C4',
                          'name': 'Home A WS',
                          'tempinf': 71.9,
                          'tz': 'Etc/GMT'}},
     {'location': 'Lab Home B',
      'observation_time': '2019-12-18T07:33:00.000000+00:00',
      'weather_results': {'batt1': 1,
                          'battout': 1,
                          'dateutc': 1576625580000,
                          'dewPoint1': 28.6,
                          'dewPointin': 23.5,
                          'feelsLike1': 35.7,
                          'feelsLikein': 53.4,
                          'humidity1': 75,
                          'humidityin': 31,
                          'macAddress': '18:93:D7:3B:89:0C',
                          'name': 'Home B WS',
                          'temp1f': 35.7,
                          'tempinf': 53.4,
                          'tz': 'Etc/GMT'}}]

The selection of weather data points which are included may depend upon
the type of Ambient device.

### Configuration

The following is an example configuration for the Ambient agent. The
\"api_key\" and \"app_key\" parameters are required while all others are
optional.

**Parameters**

:   1.  \"api_key\" - api key string provided by Ambient - this is
        required and will not be provided by the VOLTTRON team.
    2.  \"appplication_key\" - application key string provided by
        Ambient - this is required and will not be provided by the
        VOLTTRON team.
    3.  \"database_file\" - sqlite database file for weather data
        caching. Defaults to \"weather.sqlite\" in the agent\'s data
        directory.
    4.  \"max_size_gb\" - maximum size of cache database. When cache
        exceeds this size, data will get purged from cache till cache is
        within the configured size.
    5.  \"poll_locations - list of locations to periodically poll for
        current data.
    6.  \"poll_interval\" - polling frequency or the number of seconds
        between each poll.

Example configuration:

``` {.json}
{
    "application_key" : "<api_key>",
    "api_key":"<application_key>",
    "poll_locations": [
      {"location": "Lab Home A"},
      {"location": "Lab Home B"}
    ],
    "poll_interval": 60,
    "identity": "platform.ambient"
}
```

#### Registry Configuration

The registry configuration file for this agent can be found in agent\'s
data directory. This configuration provides the point name mapping from
the Ambient API\'s point scheme to the CF-conventions scheme by default.
Points that do not specify \"Standard_Point_Name\" were found to not
have a logical match to any point found in the CF-Conventions. For these
points Ambient point name convention (Service_Point_Name) will be used.

  Service_Point_Name   Standard_Point_Name            Service_Units   Standard_Units
  -------------------- ------------------------------ --------------- ----------------
  feelsLike            apparent_temperature           degF            
  dewPoint             dew_point_temperature          degF            
  dewPointin           dew_point_temperature_indoor   degF            
  soiltempf                                           degF            
  soilhum                                                             
  uv                   ultraviolet_index                              

  : Registry Configuration

## Running Ambient Agent Tests

The following instructions can be used to run PyTests for the Ambient
agent.

1\. Set up the test file - test_ambient_agent.py is the PyTest file for
the ambient agent. The test file features a few variables at the top of
the tests. These will need to be filled in by the runner of the Ambient
agent tests. The LOCATIONS variable specifies a list of \"locations\" of
Ambient devices. The required format is a list of dictionaries of the
form {\"location\": \<ambient weather station location\>}. Locations are
determined by the user when configuring a weather station for the
Ambient service using the Ambient app. For more information about the
Ambient API, visit <https://www.ambientweather.com/api.html>

2\. Set up the test environment - The tests are intended to be run from
the Volttron root directory using the Volttron environment. Setting the
environment variable, DEBUG_MODE=True or DEBUG=1 will preserve the test
setup and can be useful for debugging purposes. When testing from
pycharm set the Working Directory value to be the root of volttron
source/checkout directory.

Example command line:

``` {.}
(volttron) <user>@<host>:~/volttron$ pytest -s ~/house-deployment/Ambient
```
