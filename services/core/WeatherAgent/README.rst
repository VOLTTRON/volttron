.. _Weather_Agent:

============
WeatherAgent
============

Weather agent provides interface to get weather data from
`WeatherUnderground  <http://www.wunderground.com/>`_.
In order for this agent to retrieve data from Weather Underground,
 you must get a developer's key and put that in the config file. Please see
`<http://www.wunderground.com/weather/api/>`_

Features
--------

1. Periodic polling of current weather conditions for one or more locations.

   Results for each location configured, is published to its corresponding
   result topic. Location configured using zip gets periodic weather data
   published to the topic weather2/polling/current/ZIP/<zip>/all and location
   configured using city and region gets data published to
   weather2/polling/current/<city>/<region>/all

2. Request for weather data by making a pubsub request. You can
request for
    a. current conditions:
       Publish request to weather2/request/current/{region}/{city}/all
    b. history
       Publish request to
        i. weather2/request/history/{region}/{city}/all/start_date or
        ii. weather2/request/history/{region}/{city}/all/start_date/end_date
        If end_date is not given it defaults to start_date + 1.
    c. hourly forecast for a day
       Publish request to weather2/request/hourly/{region}/{city}/all
    d. hourly forecast for 10 days
       Publish request to weather2/request/hourly10days/{region}/{city}/all

3. Specifying location: location should be specified in the request url using
{region}+{city} or {zip} with the following possible values
    a. state/city - example: Washington/Richland
    b. two letter state code/ city - example: WA/Richland
    c. country/city - example: Australia/Sydney
    d. ZIP/zipcode - example: ZIP/99354

4. Error:
   Errors are reported to weather2/error topics. The error topic is
   derived by replacing the string "request" or "polling" in the request
   topic by the string "error".
   For example, error occurred during a request to
   weather2/request/current/WA/Richland/all will be published to topic
   weather2/error/current/WA/Richland/all



Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by this agent.

.. code-block:: python

    {
        #1: request only, 2: polling & request. for polling poll_time should
        # also be specified
        "operation_mode": 2,

        "wu_api_key": "<your api key>",

        "locations": [
            {"zip": "22212", # zip has higher priority than city+region
            # no need if zip is defined. if using city, should also mention region
            "city": "Incheon",
            # region can be State, two letter state code, or country. Note,
            # ambiguous city + region combination would result in exception
            "region": "KO", #state or country. no need if zip is defined
            }
        ],

        # This section is used to make weather agent periodically publish
        # current conditions. Mandatory parameter for polling to work.
        # Set up poll_time to make sure the number of API calls to WU is less
        # than your WU subscription daily limit. Unit - seconds
        "poll_time": 20 #seconds

    }
