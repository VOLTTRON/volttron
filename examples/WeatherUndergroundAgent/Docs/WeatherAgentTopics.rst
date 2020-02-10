.. _WeatherAgentTopics:

Weather Agent Topics
--------------------

Topics used by the WeatherAgent with example output.

['weather/all', '{"temperature": {"windchill\_f": "NA", "temp\_f": 69.1,
"heat\_index\_f": "NA", "heat\_index\_string": "NA", "temp\_c": 20.6,
"feelslike\_c": "20.6", "windchill\_string": "NA", "feelslike\_f":
"69.1", "heat\_index\_c": "NA", "windchill\_c": "NA",
"feelslike\_string": "69.1 F (20.6 C)", "temperature\_string": "69.1 F
(20.6 C)"}, "cloud\_cover": {"visibility\_mi": "10.0", "solarradiation":
"", "weather": "Clear", "visibility\_km": "16.1", "UV": "6"},
"location": {"display\_location": {"city": "Richland", "full":
"Richland, WA", "elevation": "121.00000000", "state\_name":
"Washington", "zip": "99352", "country": "US", "longitude":
"-119.29721832", "state": "WA", "country\_iso3166": "US", "latitude":
"46.28490067"}, "local\_tz\_long": "America/Los\_Angeles",
"observation\_location": {"city": "Richland, Richland", "full":
"Richland, Richland, Washington", "elevation": "397 ft", "country":
"US", "longitude": "-119.304375", "state": "Washington",
"country\_iso3166": "US", "latitude": "46.285866"}, "station\_id":
"KWARICHL21"}, "time": {"local\_tz\_offset": "-0700", "local\_epoch":
"1368724778", "observation\_time": "Last Updated on May 16, 10:18 AM
PDT", "local\_tz\_short": "PDT", "observation\_epoch": "1368724692",
"local\_time\_rfc822": "Thu, 16 May 2013 10:19:38 -0700",
"observation\_time\_rfc822": "Thu, 16 May 2013 10:18:12 -0700"},
"pressure\_humidity": {"relative\_humidity": "40%", "pressure\_mb":
"1014", "pressure\_trend": "-"}, "precipitation": {"dewpoint\_string":
"44 F (7 C)", "precip\_1hr\_in": "0.00", "precip\_today\_in": "0.00",
"precip\_today\_metric": "0", "precip\_today\_string": "0.00 in (0 mm)",
"dewpoint\_f": 44, "dewpoint\_c": 7, "precip\_1hr\_string": "0.00 in ( 0
mm)", "precip\_1hr\_metric": " 0"}, "wind": {"wind\_degrees": 3,
"wind\_kph": 2.7, "wind\_gust\_mph": "3.0", "wind\_mph": 1.7,
"wind\_string": "From the North at 1.7 MPH Gusting to 3.0 MPH",
"pressure\_in": "29.94", "wind\_dir": "North", "wind\_gust\_kph":
"4.8"}}']

['weather/temperature/all', '{"windchill\_f": "NA", "temp\_f": 69.1,
"heat\_index\_f": "NA", "heat\_index\_string": "NA", "temp\_c": 20.6,
"feelslike\_c": "20.6", "windchill\_string": "NA", "feelslike\_f":
"69.1", "heat\_index\_c": "NA", "windchill\_c": "NA",
"feelslike\_string": "69.1 F (20.6 C)", "temperature\_string": "69.1 F
(20.6 C)"}']

['weather/temperature/windchill\_f', 'NA']

['weather/temperature/temp\_f', '69.1']

['weather/temperature/heat\_index\_f', 'NA']

['weather/temperature/heat\_index\_string', 'NA']

['weather/temperature/temp\_c', '20.6']

['weather/temperature/feelslike\_c', '20.6']

['weather/temperature/windchill\_string', 'NA']

['weather/temperature/feelslike\_f', '69.1']

['weather/temperature/heat\_index\_c', 'NA']

['weather/temperature/windchill\_c', 'NA']

['weather/temperature/feelslike\_string', '69.1 F (20.6 C)']

['weather/temperature/temperature\_string', '69.1 F (20.6 C)']

['weather/cloud\_cover/all', '{"visibility\_mi": "10.0",
"solarradiation": "", "weather": "Clear", "visibility\_km": "16.1",
"UV": "6"}']

['weather/cloud\_cover/visibility\_mi', '10.0']

['weather/cloud\_cover/solarradiation', '']

['weather/cloud\_cover/weather', 'Clear']

['weather/cloud\_cover/visibility\_km', '16.1']

['weather/cloud\_cover/UV', '6']

['weather/location/all', '{"display\_location": {"city": "Richland",
"full": "Richland, WA", "elevation": "121.00000000", "state\_name":
"Washington", "zip": "99352", "country": "US", "longitude":
"-119.29721832", "state": "WA", "country\_iso3166": "US", "latitude":
"46.28490067"}, "local\_tz\_long": "America/Los\_Angeles",
"observation\_location": {"city": "Richland, Richland", "full":
"Richland, Richland, Washington", "elevation": "397 ft", "country":
"US", "longitude": "-119.304375", "state": "Washington",
"country\_iso3166": "US", "latitude": "46.285866"}, "station\_id":
"KWARICHL21"}']

['weather/location/display\_location/all', '{"city": "Richland", "full":
"Richland, WA", "elevation": "121.00000000", "state\_name":
"Washington", "zip": "99352", "country": "US", "longitude":
"-119.29721832", "state": "WA", "country\_iso3166": "US", "latitude":
"46.28490067"}']

['weather/location/display\_location/city', 'Richland']

['weather/location/display\_location/full', 'Richland, WA']

['weather/location/display\_location/elevation', '121.00000000']

['weather/location/display\_location/state\_name', 'Washington']

['weather/location/display\_location/zip', '99352']

['weather/location/display\_location/country', 'US']

['weather/location/display\_location/longitude', '-119.29721832']

['weather/location/display\_location/state', 'WA']

['weather/location/display\_location/country\_iso3166', 'US']

['weather/location/display\_location/latitude', '46.28490067']

['weather/location/local\_tz\_long', 'America/Los\_Angeles']

['weather/location/observation\_location/all', '{"city": "Richland,
Richland", "full": "Richland, Richland, Washington", "elevation": "397
ft", "country": "US", "longitude": "-119.304375", "state": "Washington",
"country\_iso3166": "US", "latitude": "46.285866"}']

['weather/location/observation\_location/city', 'Richland, Richland']

['weather/location/observation\_location/full', 'Richland, Richland,
Washington']

['weather/location/observation\_location/elevation', '397 ft']

['weather/location/observation\_location/country', 'US']

['weather/location/observation\_location/longitude', '-119.304375']

['weather/location/observation\_location/state', 'Washington']

['weather/location/observation\_location/country\_iso3166', 'US']

['weather/location/observation\_location/latitude', '46.285866']

['weather/location/station\_id', 'KWARICHL21']

['weather/time/all', '{"local\_tz\_offset": "-0700", "local\_epoch":
"1368724778", "observation\_time": "Last Updated on May 16, 10:18 AM
PDT", "local\_tz\_short": "PDT", "observation\_epoch": "1368724692",
"local\_time\_rfc822": "Thu, 16 May 2013 10:19:38 -0700",
"observation\_time\_rfc822": "Thu, 16 May 2013 10:18:12 -0700"}']

['weather/time/local\_tz\_offset', '-0700']

['weather/time/local\_epoch', '1368724778']

['weather/time/observation\_time', 'Last Updated on May 16, 10:18 AM
PDT']

['weather/time/local\_tz\_short', 'PDT']

['weather/time/observation\_epoch', '1368724692']

['weather/time/local\_time\_rfc822', 'Thu, 16 May 2013 10:19:38 -0700']

['weather/time/observation\_time\_rfc822', 'Thu, 16 May 2013 10:18:12
-0700']

['weather/pressure\_humidity/all', '{"relative\_humidity": "40%",
"pressure\_mb": "1014", "pressure\_trend": "-"}']

['weather/pressure\_humidity/relative\_humidity', '40%']

['weather/pressure\_humidity/pressure\_mb', '1014']

['weather/pressure\_humidity/pressure\_trend', '-']

['weather/precipitation/all', '{"dewpoint\_string": "44 F (7 C)",
"precip\_1hr\_in": "0.00", "precip\_today\_in": "0.00",
"precip\_today\_metric": "0", "precip\_today\_string": "0.00 in (0 mm)",
"dewpoint\_f": 44, "dewpoint\_c": 7, "precip\_1hr\_string": "0.00 in ( 0
mm)", "precip\_1hr\_metric": " 0"}']

['weather/precipitation/dewpoint\_string', '44 F (7 C)']

['weather/precipitation/precip\_1hr\_in', '0.00']

['weather/precipitation/precip\_today\_in', '0.00']

['weather/precipitation/precip\_today\_metric', '0']

['weather/precipitation/precip\_today\_string', '0.00 in (0 mm)']

['weather/precipitation/dewpoint\_f', '44']

['weather/precipitation/dewpoint\_c', '7']

['weather/precipitation/precip\_1hr\_string', '0.00 in ( 0 mm)']

['weather/precipitation/precip\_1hr\_metric', ' 0']

['weather/wind/all', '{"wind\_degrees": 3, "wind\_kph": 2.7,
"wind\_gust\_mph": "3.0", "wind\_mph": 1.7, "wind\_string": "From the
North at 1.7 MPH Gusting to 3.0 MPH", "pressure\_in": "29.94",
"wind\_dir": "North", "wind\_gust\_kph": "4.8"}']

['weather/wind/wind\_degrees', '3']

['weather/wind/wind\_kph', '2.7']

['weather/wind/wind\_gust\_mph', '3.0']

['weather/wind/wind\_mph', '1.7']

['weather/wind/wind\_string', 'From the North at 1.7 MPH Gusting to 3.0
MPH']

['weather/wind/pressure\_in', '29.94']

['weather/wind/wind\_dir', 'North']

['weather/wind/wind\_gust\_kph', '4.8']
