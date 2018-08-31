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
from services.core.WeatherAgent.weather.agent import BaseWeather
from volttron.platform.agent import utils
from volttron.utils.docs import doc_inherit
from volttron.platform.vip.agent import *

__version__ = "0.1.0"
_log = logging.getLogger(__name__)

LAT_LONG_REGEX = re.compile("^[0-9]{1,3}(\.[0-9]{1,4})?,( |\t?)[0-9]{1,3}(\.[0-9]{1,4})?$")
STATION_REGEX = re.compile("^[Kk][a-zA-Z]{3}$")

def weather_agent():
    # TODO
    return WeatherDotGovAgent


# TODO manage format for all times
class WeatherDotGovAgent(BaseWeather):
    def __init__(self):
        super(WeatherDotGovAgent,self).__init__("WeatherDotGov")
        self._api_features = {"get_hourly_forecast": {"PARAMS": "location (as string)"},
                             "get_current_weather": {"PARAMS": "location (as string)"}
                             }
        self._tables = {"current_weather": "current",
                       "hourly_forecast": "forecast"
                       }
        self._update_frequency = {"current_weather": datetime.timedelta(hours=1),
                                  "hourly_forecast": datetime.timedelta(hours=1)}
        # TODO encoding?
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }

    @doc_inherit
    def configure(self):
        # TODO

    @doc_inherit
    def query_current_weather(self, location, cache=True):
        """

        :param location: currently accepts station id (K followed by 3 letters, case insensitive) or
        lat/long (up to 4 decimals)
        :param cache: True if we want to use cached data if available, else False
        :return: a single current data record as a list
        """
        formatted_location = None
        url= ""
        if "LAT/LONG" in location:
            if LAT_LONG_REGEX.match(str(location["LAT/LONG"])):
                formatted_location = str(location)
                url = "https://api.weather.gov/points/{}/".format(formatted_location)
            else:
                # TODO lat long improperly formatted
        elif "STATION" in location:
            if STATION_REGEX.match(str(location["STATION"])):
                formatted_location = str(location)
                url = "https://api.weather.gov/stations/{}/observations/current".format(formatted_location)
            else:
                # TODO station improperly formatted
        if formatted_location:
            most_recent_data = self.cache.get_current_data(formatted_location)[0]
            update_required = (datetime.datetime.utcnow() - most_recent_data[2]) < datetime.timedelta(hours=1)
            if cache and not update_required:
                return most_recent_data
            else:

                self.manage_cache_size()
                request = requests.get(url, headers=self.headers)
                response = request.json()
                if self.api_error(response):
                    # TODO error state
                else:
                    data_dict = {}
                    points = {}
                    # TODO get times out of the data
                    request_time = 0
                    data_time = response["properties"]["generatedAt"]
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
                    self.cache.store_weather_records("current_weather",
                                                     [formatted_location, request_time, data_time, json.dumps(points)])
                    return data_dict
        else:
            # TODO
            string = "location not in an accepted format."

    @doc_inherit
    def query_hourly_forecast(self, location, cache=True):
        formatted_location = None
        url = ""
        if "LAT/LONG" in location:
            if LAT_LONG_REGEX.match(str(location)):
                formatted_location = str(location)
                url = "https://api.weather.gov/points/{}/forecast/hourly".format(formatted_location)
            else:
                # TODO lat/long improperly formatted
        elif "STATION" in location:
            # TODO we don't allow this type, as station->point does not exist
        if formatted_location:
            most_recent_data = self.cache.get_forecast_data("hourly_forecast", formatted_location)
            update_required = False
            if most_recent_data:
                forecast_timestamp = most_recent_data[0][2]
                update_required = (datetime.datetime.utcnow() - forecast_timestamp) < datetime.timedelta(hours=1)
            if cache and not update_required:
                return most_recent_data
            else:
                # TODO time formatting all times should be in utc format
                request_time = datetime.datetime.utcnow()
                request = requests.get(url, headers=self.headers)
                response = request.json()
                if self.api_error(response):
                    # TODO return special thing
                else:
                    # TODO get these out of the data
                    data_time = response["properties"]["generatedAt"]
                    data_dict = {}
                    data_list= []
                    # TODO record formatting for storage
                    for forecast_record in response["properties"]["periods"]:
                        # TODO get these out of the data
                        forecast_time = 0
                        record = [formatted_location, request_time, data_time, forecast_time, json.dumps()]
                        data_list.append(record)
                    self.cache.store_weather_records("hourly_forecast", data_list)
                    return data_dict
        else:
            # TODO completely unreadable location


    # TODO compare with historians to see how they handle unimplemented rpc methods
    def query_hourly_historical_Weather(self):
        raise NotImplementedError

    @doc_inherit
    def api_error(self, response):
        # TODO

    @doc_inherit
    def version(self):
        return __version__


def main(argv=sys.argv):
    """" Main entry point for the agent.

    :param argv:
    :return:
    """
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