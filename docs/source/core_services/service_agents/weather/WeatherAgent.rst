.. _WeatherAgent:

Weather Agent
=============

The Weather Agent provides weather data retrieved from Weather
Underground to agents. It provides an example of accessing an external
resource and publishing it to the VOLTTRON Message Bus. It also provides
an example of dividing data up into topics and for implementing the
"all" topic at each level. The Weather agent retrieves data in two ways.

Usage
-----

In the first, the agent periodically retrieves information about a
specific area from weather underground and publishes current information
periodically (default once an hour) to the message bus. The area is set
in the agents configuration file. Agents that are interested in this
information can subscribe to "*weather/<subtopic>/<field>*\ " where
<subtopic> and <field> are described in the topics section below. Agents
may also subscribe to "*weather/all*\ " which will give them a
hierarchical json document laid out according to the weather agent
topics (as below) or "*weather/<subtopic>/all*\ " which provides a json
document with all of the fields for the weather topic specified.

The second mode of operation is on demand. An agent may specifically
request weather data for an area by posting a message on the
"*weather/request*\ " topic. The agents message includes the identifying
information about the area (region/city, or zip code) which is used in
the request to Weather Underground. The Weather Agent replies on the
"weather/response" topic (to avoid confusion with agents subscribing to
the periodic posts). As with the first mode of operation, the agent
making the request can subscribe to the "*weather/response/all*\ "
subtopic, "*weather/response/<subtopic>/all*\ ", or
"*weather/response/<subtopic>/<field>*\ " topics to receive the response
data from the Weather Agent. Agents making requests must have the
requesterID header set.

3.0 Agent Example
-----------------

To make a request of the weather agent.

::

    Python 2.7.6 (default, Jun 22 2015, 17:58:13) 
    [GCC 4.8.2] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> from volttron.platform.vip.agent import *
    >>> a = Agent()
    >>> import gevent
    >>> gevent.spawn(a.core.run).join(0)
    >>> a.vip.pubsub.publish('pubsub', 'weather/request', headers={'requesterID': 'agentid'}, message={'zipcode': '99336'}).get(timeout=10)

::


        headers = {}
        headers[headers_mod.REQUESTER_ID] = agent_id
        msg = {"zipcode": "99352"}
        self.publish_json('weather/request', headers, msg)

**Make sure you get your own API Key from Weather Underground before
using the weather agent.**

Sample Output
-------------

Following is the response message that would be returned on
"weather/all" or "weather/response/all".

::

    {
        "cloud_cover": {
            "UV": "6",
            "solarradiation": "",
            "visibility_km": "16.1",
            "visibility_mi": "10.0",
            "weather": "Clear"
        },
        "location": {
            "display_location": {
                "city": "Richland",
                "country": "US",
                "country_iso3166": "US",
                "elevation": "121.00000000",
                "full": "Richland, WA",
                "latitude": "46.28490067",
                "longitude": "-119.29721832",
                "state": "WA",
                "state_name": "Washington",
                "zip": "99352"
            },
            "local_tz_long": "America/Los_Angeles",
            "observation_location": {
                "city": "Richland, Richland",
                "country": "US",
                "country_iso3166": "US",
                "elevation": "397 ft",
                "full": "Richland, Richland, Washington",
                "latitude": "46.285866",
                "longitude": "-119.304375",
                "state": "Washington"
            },
            "station_id": "KWARICHL21"
        },
        "precipitation": {
            "dewpoint_c": 7,
            "dewpoint_f": 44,
            "dewpoint_string": "44 F (7 C)",
            "precip_1hr_in": "0.00",
            "precip_1hr_metric": " 0",
            "precip_1hr_string": "0.00 in ( 0 mm)",
            "precip_today_in": "0.00",
            "precip_today_metric": "0",
            "precip_today_string": "0.00 in (0 mm)"
        },
        "pressure_humidity": {
            "pressure_mb": "1014",
            "pressure_trend": "-",
            "relative_humidity": "40%"
        },
        "temperature": {
            "feelslike_c": "20.6",
            "feelslike_f": "69.1",
            "feelslike_string": "69.1 F (20.6 C)",
            "heat_index_c": "NA",
            "heat_index_f": "NA",
            "heat_index_string": "NA",
            "temp_c": 20.6,
            "temp_f": 69.1,
            "temperature_string": "69.1 F (20.6 C)",
            "windchill_c": "NA",
            "windchill_f": "NA",
            "windchill_string": "NA"
        },
        "time": {
            "local_epoch": "1368724778",
            "local_time_rfc822": "Thu, 16 May 2013 10:19:38 -0700",
            "local_tz_offset": "-0700",
            "local_tz_short": "PDT",
            "observation_epoch": "1368724692",
            "observation_time": "Last Updated on May 16, 10:18 AM PDT",
            "observation_time_rfc822": "Thu, 16 May 2013 10:18:12 -0700"
        },
        "wind": {
            "pressure_in": "29.94",
            "wind_degrees": 3,
            "wind_dir": "North",
            "wind_gust_kph": "4.8",
            "wind_gust_mph": "3.0",
            "wind_kph": 2.7,
            "wind_mph": 1.7,
            "wind_string": "From the North at 1.7 MPH Gusting to 3.0 MPH"
        }
    }

For a more comprehensive listing of Weather Agent subtopics see
:ref:`WeatherAgentTopics <WeatherAgentTopics>`
