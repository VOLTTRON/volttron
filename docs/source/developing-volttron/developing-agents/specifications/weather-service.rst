.. _Weather-Agent-Specification:

===============
Weather Service
===============

***********
Description
***********

The weather service agent provides  API to access current weather data,
historical data and weather forecast data.  There are several weather data
providers, some paid and some free. Weather data providers differs from one
and other

  1. In the kind of features provided - current data, historical data, forecast
     data
  2. The data points returned
  3. The naming schema used to represent the data returned
  4. Units of data returned
  5. Frequency of data updates

The weather service agent has a design similar to historians. There
is a single base weather service that defines the api signatures and
the ontology of the weather data points. There is one concrete
weather service agents for each weather provider. Users can install one or
more provider specific agent to access weather data.

The initial implementation is for `NOAA <http://www.noaa.gov>`_ and
would support current and forecast data requests. NOAA does not support
accessing historical weather data through their api. This agent implements
request data caching.

The second implementation is for `darksky.net <https://darksky.net/dev>`_.


********
Features
********

Base weather agent features:
 1. Caching

    The weather service provides basic caching capability so that
    repeated request for same data can be returned from cache instead of network
    round trip to the weather data provider. This is also useful to limit the
    number of request made to the provider as most weather data provider
    have restrictions on number of requests for developer/free api keys. The
    size of the cache can be restricted by setting an optional configuration
    parameter 'max_size_gb'
 2. Name mapping

    Data points returned by  concrete weather agents is mapped to
    standard names based on
    `CF standard names table <http://cfconventions.org/Data/cf-standard-names/57/build/cf-standard-name-table.html>`_
    Name mapping is done using a CSV file. See `Configuration`_ section
    for an example configuration

 3. Unit conversion

    If data returned from the provider is of the format
    {"data_point_name":value}, base weather agent can do unit conversions on
    the value.  Both name mapping and unit conversions can be specified as a
    csv file and packaged with the concrete implementing agent. This feature
    is not mandatory. See `Configuration`_ section for an example
    configuration

Core weather data retrieval features :

  1. Retrieve current weather data.   
  2. Retrieve hourly weather forecast data. 
  3. Retrieve historical weather data. 
  4. Periodic polling of current weather data for one or more locations.
     Users can configure one or more locations in a config file and weather
     agent will periodically poll for current weather data for the configured
     locations and publish the results to message bus.

The set of points returned from the above queries depends on the specific
weather data provider, however the point names returned are from the
standard schema.

Note:

  1. Since individual weather data provider can support slightly different
     sets of features, users are able to query for the list of available
     features. For example a provider could provide daily weather forecast in
     addition to the hourly forecast data.


***
API
***

1. Get available features
---------------------------
rpc call to weather service method **’get_api_features’**

Parameters - None

Returns - dictionary of api features that can be called for this weather agent.


2. Get current weather data
---------------------------
rpc call to weather service method **’get_current_weather’** 

Parameters:

    1. **locations** - dictionary containing location details. The format of
       location accepted differs between different weather providers and
       even different APIs supported by the same provider
       For example the location input could be either
       {“zipcode”:value} or {“region”:value, “country”: value}.

Returns:
  List of dictionary objects containing current weather data.
  The actual data points returned depends on the weather service provider.


3. Get hourly forecast data
---------------------------
rpc call to weather service method **’get_hourly_forecast’** 

Parameters:

    1. **locations** - dictionary containing location details. The format of
       location accepted differs between different weather providers and
       even different APIs supported by the same provider
       For example the location input could be either
       {“zipcode”:value} or {“region”:value, “country”: value}.

optional parameters:

    2. **hours** - The number of hours for which forecast data are
       returned. By default, it is 24 hours.

Returns:
  List of dictionary objects containing forecast data. If weather data provider
  returns less than requested number of hours result returned would contain a
  warning message in addition to the result returned by the provider


4. Get historical weather data
------------------------------
rpc call to weather service method **’get_hourly_historical’** 

Parameters:

    1. **locations** - dictionary containing location details.
       For example the location input could be either
       {“zipcode”:value} or {“region”:value, “country”: value}.
    2. **start_date** - start date of requested data
    3. **end_date** - end date of requested data

Returns:
  List of dictionary objects containing historical data.

.. note:: Based on the weather data provider this api could do
 multiple calls to the data provider to get the requested data. For example,
 darksky.net allows history data query by a single date and not a date range.

5. Periodic polling of current weather data
-------------------------------------------
This can be achieved by configuring the locations for which data is requested
in the agent’s configuration file along with polling interval. Results for
each location configured, is published to its corresponding result topic.
is no result topic prefix is configured, then results for all locations are
posted to the topic weather/poll/current/all. poll_topic_suffixes when
provided should be a list of string with the same length as the number of
poll_locations. When topic prefix is specified, each location's result is
published to weather/poll/current/<poll_topic_suffix for that location>
topic_prefix.

*************
Configuration
*************

Example configuration:

.. code-block:: python

    {
        poll_locations: [
            {"zip": "22212"},
            {"zip": "99353"}
        ],
        poll_topic_suffixes: ["result_22212", "result_99353"],
        poll_interval: 20 #seconds,

        #optional cache arguments
        max_cache_size: ...

    }

Example configuration for mapping point names returned by weather provider to
a standard name and units:

.. code-block:: console

  Service_Point_Name,Standard_Point_Name,Service_Units,Standard_Units
  temperature,air_temperature,fahrenheit,celsius

		    
*******
Caching
*******

Weather agent will cache data until the configured size limit is reached
(if provided).

1. Current and forecast data:

   If current/forecast weather data exists in cache and if the request time
   is within the update time period of the api (specified by a concrete
   implementation) then by default cached data would be returned otherwise a
   new request is made for it. If hours is provided and the amount of cached
   data records is less than hours, this will also result in a new request.

2. Historical data cache:

   Weather api will query the cache for available data for the given
   time period and fill and missing time period with data from the
   remote provider.

3. Clearing of cache:
   
   Users can configure the maximum size limit for cache.
   For each api call, before data is inserted in cache, weather agent will
   check for this size limit and purge records in this order.
   - Current data older than update time period
   - Forecast data older than update time period
   - History data starting with the oldest cached data

***********
Assumptions
***********

  1. User has api key for accessing weather api for a specific weather data
     provider, if a key is required.
  2. Different weather agent might have different requirement for how
     input locations  are specified. For example NOAA expects a station id
     for querying current weather and requires either a lat/long or
     gridpoints to query for forecast. weatherbit.io accepts zip code.
  3. Not all features might be implemented by a specific weather agent.
     For example NOAA doesn’t make history data available using their weather
     api.
  4. Concrete agents could expose additional api features
  5. Optionally, data returned will be based on standard names provided by
     the CF standard names table (see Ontology). Any points with a name not
     mapped to a standard name would be returned as is.


