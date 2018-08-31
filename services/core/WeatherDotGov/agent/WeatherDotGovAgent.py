# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official,
# policies either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import logging
import re
import sys
import requests
import datetime
import json
from volttron.platform.agent.base_weather import BaseWeather
from volttron.platform.agent import utils
from volttron.utils.docs import doc_inherit
from volttron.platform.vip.agent import *

__version__ = "0.1.0"
_log = logging.getLogger(__name__)

LAT_LONG_REGEX = re.compile("^[0-9]{1,3}(\.[0-9]{1,4})?,( |\t?)[0-9]{1,3}(\.[0-9]{1,4})?$")
STATION_REGEX = re.compile("^[Kk][a-zA-Z]{3}$")

def weather_agent():
    # TODO check out the historian class from sql historian
    return WeatherDotGovAgent


class WeatherDotGovAgent(BaseWeather):
    def __init__(self):
        super(WeatherDotGovAgent, self).__init__("WeatherDotGov")
        self._api_features = {"get_hourly_forecast": {"PARAMS": "location (as string)"},
                              "get_current_weather": {"PARAMS": "location (as string)"}
                              }
        self._tables = {"current_weather": "current",
                        "hourly_forecast": "forecast"
                        }
        self._update_frequency = {"current_weather": datetime.timedelta(hours=1),
                                  "hourly_forecast": datetime.timedelta(hours=1)
                                  }
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }

    @doc_inherit
    def query_current_weather(self, location, cache=True):
        """

        :param location: currently accepts station id (K followed by 3 letters, case insensitive) or
        lat/long (up to 4 decimals)
        :param cache: True if we want to use cached data if available, else False
        :return: a single current data record as a list
        """
        formatted_location = None
        url = ""
        if "LAT/LONG" in location:
            if LAT_LONG_REGEX.match(str(location["LAT/LONG"])):
                formatted_location = str(location)
                url = "https://api.weather.gov/points/{}/".format(formatted_location)
            else:
                raise ValueError("Improperly formatted lat/long was passed.")
        elif "STATION" in location:
            if STATION_REGEX.match(str(location["STATION"])):
                formatted_location = str(location)
                url = "https://api.weather.gov/stations/{}/observations/current".format(formatted_location)
            else:
                raise ValueError("Improperly formatted station ID was passed.")
        if formatted_location:
            most_recent_data = self.get_cached_current_data("current_weather", formatted_location)[0]
            update_required = (datetime.datetime.utcnow() - most_recent_data[2]) < datetime.timedelta(hours=1)
            if cache and not update_required:
                return most_recent_data
            else:
                request = requests.get(url, headers=self.headers)
                response = request.json()
                if not request.ok():
                    raise RuntimeError("API request failed.")
                else:
                    data_dict = {}
                    points = {}
                    request_time = datetime.datetime.utcnow().timestamp()
                    data_time = datetime.datetime.strptime(response["properties"]["generatedAt"], "%Y-%m-%dT%H:%M%z")\
                        .timestamp()
                    for point in response["properties"]:
                        if "value" in response[point]:
                            value = response["properties"][point]['value']
                            value = self.manage_unit_conversion(self.weather_mapping[point]["Service_Units"],
                                                                value,
                                                                self.weather_mapping[point]["Standardized_Units"])
                            if point in self.reverse_map:
                                mapped_name = self.reverse_map[point]
                                points[mapped_name] = value
                            else:
                                points[point] = value
                    data_dict[formatted_location][request_time] = {"data_time": data_time,
                                                                   "points": points}
                    self.store_weather_records("current_weather", "current",
                                               [formatted_location, request_time, data_time, json.dumps(points)])
                    return data_dict
        else:
            raise ValueError("Unhandled location format was passed.")

    @doc_inherit
    def query_hourly_forecast(self, location, cache=True):
        """

        :param location:
        :param cache:
        :return:
        """
        formatted_location = None
        url = ""
        if "LAT/LONG" in location:
            if LAT_LONG_REGEX.match(str(location)):
                formatted_location = str(location)
                url = "https://api.weather.gov/points/{}/forecast/hourly".format(formatted_location)
            else:
                raise ValueError("Improperly formatted lat/long was passed.")
        if formatted_location:
            most_recent_data = self.get_cached_forecast_data("hourly_forecast", formatted_location)
            update_required = False
            if most_recent_data:
                forecast_timestamp = most_recent_data[0][2]
                update_required = (datetime.datetime.utcnow() - forecast_timestamp) < datetime.timedelta(hours=1)
            if cache and not update_required:
                return most_recent_data
            else:
                request_time = datetime.datetime.utcnow().timestamp()
                request = requests.get(url, headers=self.headers)
                response = request.json()
                if not request.ok():
                    raise RuntimeError("API request failed.")
                else:
                    data_time = response["properties"]["generatedAt"]
                    data_list = []
                    data_dict = {}
                    for record in response["properties"]["periods"]:
                        forecast_record = response["properties"]["periods"][record]
                        forecast_time = datetime.datetime.strptime(forecast_record["point"],
                                                                   "%Y-%m-%dT%H:%M%z").timestamp()
                        data_dict[formatted_location][request_time] = forecast_record["point"]
                        record = [formatted_location, request_time, data_time, forecast_time,
                                  json.dumps(forecast_record)]
                        data_list.append(record)
                    self.store_weather_records("hourly_forecast", "forecast", data_list)
                    return data_dict
        else:
            raise ValueError("Unhandled location format was passed.")

    def query_hourly_historical_weather(self, location, start_period, end_period):
        """Unimplemented method stub."""
        raise NotImplementedError

    @doc_inherit
    def version(self):
        """

        :return: Running WeatherDotGovAgent's version number
        """
        return __version__


def main(argv=sys.argv):
    """" Main entry point for the agent."""
    try:
        utils.vip_main(weather_agent, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
