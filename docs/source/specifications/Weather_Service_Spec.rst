.. _WeatherAgentSpec:

=============================
Weather service specification
=============================

***********
Description
***********


The weather service agent will provide  API to access current weather data, historical data and weather forecast data.  There are several weather data providers some paid and some free. Weather data providers differs from one and other 
  1. In the kind of features provided - current data, historical data, forecast data
  2. The data points returned 
  3. The naming schema used to represent the data returned 
  4. Units of data returned 

The weather service agent would have a design similar to historians. There would be a single base weather service that defines the api signatures and the ontology of the weather data points. There would be one concrete  weather service agents for each weather provider. Users can install one or more provider specific agent to access weather data.  Data points returned by concrete weather agents would be mapped to standard names based on `CF standard names table <http://cfconventions.org/Data/cf-standard-names/57/build/cf-standard-name-table.html>`_

The initial implementations would be for
  1. `darksky.net <https://darksky.net/dev>`_ and
  2. `NOAA <http://www.noaa.gov>`_

The weather service will also provide basic caching capability so that repeated request for same data can be returned from cache instead of network round trip to the weather data provider. This is also useful to limit the number of request made to the provider as most weather data provider have restrictions on number of requests for developer/free api keys. 


********
Features
********

Core wether data retrieval features : 

  1. Retrieve current weather data.   
  2. Retrieve hourly weather forecast data. 
  3. Retrieve historical weather data. 
  4. Periodic polling of current weather data for one or more locations.  Users can configure one or more locations in a config file and weather agent will periodically poll for current weather data for the configured locations and publish the results to message bus. 

The set of points returned from the above queries would depends on the specific weather data provider, however the point names returned would be from the standard schema. 

Additional features:

  1. Since individual weather data provider can support slightly different sets of features, users should be able to query for the list of available features. For example a provider could provide daily weather forecast in addition to the hourly forecast data.
  2. The format of location for which weather data is requested would depends on specific weather data provider, so users should be able to query location specification for the provider used.
  3. The base weather agent would provide basic caching of data.

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

    1. **locations** - dictionary containing key based on value returned get_location_specification.  
       For example the location input could be either {“zipcode”:value} or {“region”:value, “country”: value}.

Returns: List of dictionary objects containing current weather data. The actual data points returned depends on the weather service provider.


3. Get hourly forecast data
---------------------------
rpc call to weather service method **’get_hourly_forecast’** 

Parameters:

    1. **locations** - dictionary containing key based on value returned get_location_specification.  
       For example the location input could be either {“zipcode”:value} or {“region”:value, “country”: value}.

optional parameters:

    2. **hours** - The number of hours for which forecast data should be returned. By default, any cached data will be returned, if available, otherwise the default quantity provided by the service will be returned.

Returns: List of dictionary objects containing forecasted data. The amount of data returned and duration depends on the weather service provider. For example, weatherbit.io returns hourly forecast data for 24 hours when using free account.


4. Get historical weather data
------------------------------
rpc call to weather service method **’get_hourly_historical’** 

Parameters:

    1. **locations** - dictionary containing key based on value returned get_location_specification.  
       For example the location input could be either {“zipcode”:value} or {“region”:value, “country”: value}.
    2. **start_date** - start date of requested data
    3. **end_date** - end date of requested data

Returns: List of dictionary objects containing historical data. The amount of data returned and duration depends on the weather service provider. For example, weatherbit.io returns hourly forecast data for 24 hours when using free account.

.. note:: Based on the weather data provider this api could do multiple calls to the data provider to get the requested data. For example, one call per day to darksky.net get all the history data between start_date and end_date. Repeated use may exhaust the amount of api calls allowed by a service.


5. Periodic polling of current weather data
-------------------------------------------
This can be achieved by configuring the locations for which data is requested in the agent’s configuration file along with polling interval. Results for each location configured, is published to its corresponding result topic. For example, location configured using zip gets periodic weather data published to the topic 
weather2/polling/current/ZIP/<zip>/all and location configured using city and region gets data published to weather2/polling/current/<city>/<region>/all

*************
Configuration
*************

Example configuration:

.. code-block::

{
    "api_key": "<api_key>",
    "locations": [
        {"zip": "22212"},
        {"zip": "99353"}
    ],
    "poll_time": 20 #seconds,
    
    #optional cache arguments
    max_cache_size: ...

}

Example registry configuration:

.. code-block::

Service_Point_Name,Standard_Point_Name,Service_Units,Standard_Units
temperature,air_temperature,fahrenheit,celsius

		    
*******
Caching
*******

Weather agent will cache data until the configured size limit is reached (if provided).

1. Current and forecast data:

   If current/forecast weather data exists in cache and if the request time is within the update time period of the api (specified by a concrete implementation) then by default cached data would be returned otherwise a new request is made for it. If hours is provided and the amount of cached data records is less than hours, this will also result in a new request.

2. Historical data cache:

   Weather api will query the cache for available data for the given time period and fill and missing time period with data from the remote provider. 

3. Clearing of cache:
   
   Users can configure the maximum size limit for cache. For each api call, before data is inserted in cache, weather agent will check for this size limit and purge records in this order.
   - Current data older than update time period
   - Forecast data older than update time period
   - History data starting with the oldest cached data

***********
Assumptions
***********

  1. User has api key for accessing weather api for a specific weather data provider, if a key is required.
  2. Different weather agent might have different requirement for how input locations     are specified. For example NOAA expects a station id, weatherbit.io accepts zip code.
  3. Not all features might be implemented by a specific weather agent. For example NOAA doesn’t make history data available using their weather api.
  4. Concrete agents could expose additional api features
  5. Optionally, data returned will be based on standard names provided by the CF standard names table (see Ontology). Any points with a name not mapped to a standard name would be returned as is.


********
Ontology
********

Data point returned by different providers would be mapped to common point names based on `CF standard names table <http://cfconventions.org/Data/cf-standard-names/57/build/cf-standard-name-table.html>`_
Mapping would be done using a CSV file (format specified in the configuration section, under "registry configuration")
