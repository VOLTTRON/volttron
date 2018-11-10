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
import json
import pkg_resources
import grequests
import datetime
from volttron.platform.agent.base_weather import BaseWeatherAgent
from volttron.platform.agent import utils
from volttron.utils.docs import doc_inherit
from volttron.platform.vip.agent import *

__version__ = "0.1.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

LAT_LONG_REGEX = re.compile("^-?[0-9]{1,3}(\.[0-9]{1,4})?,( |t?)-?[0-9]{1,3}(\.[0-9]{1,4})?$")
STATION_REGEX = re.compile("^[Kk][a-zA-Z]{3}$")
WFO_REGEX = re.compile("^[A-Z]{3}$")

# TODO all documentation
def weather_agent(config_path, **kwargs):
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)
    _log.debug("config_dict before init: {}".format(config_dict))
    utils.update_kwargs_with_config(kwargs, config_dict)
    return WeatherDotGovAgent(service_name="WeatherDotGov", **kwargs)


class WeatherDotGovAgent(BaseWeatherAgent):
    def __init__(self, **kwargs):
        super(WeatherDotGovAgent, self).__init__(**kwargs)
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        self.remove_service("get_hourly_historical")

    def get_update_interval(self, service_name):
        if service_name == "get_current_weather":
            return datetime.timedelta(hours=1)
        elif service_name == "get_hourly_forecast":
            # TODO get hourly may be a different interval
            return datetime.timedelta(hours=1)
        else:
            return None

    def get_point_name_defs_file(self):
        return pkg_resources.resource_stream(__name__, "data/name_mapping.csv")

    def get_location_string(self, location):
        if location.get('lat') and location.get('long'):
            formatted_location = self.get_lat_long_str(location)
            return formatted_location
        if location.get('station'):
            formatted_location = self.get_station_str(location)
            return formatted_location
        elif location.get("wfo") and location.get("x") and location.get("y"):
            formatted_location = self.get_gridpoints_str(location)
            return formatted_location
        else:
            raise ValueError("Invalid location {}".format(location))

    # TODO add docs
    def get_lat_long_str(self, location_dict):
        return "{},{}".format(location_dict.get("lat"),
                              location_dict.get("long"))

    # TODO add docs
    def get_station_str(self, location_dict):
        return location_dict.get("station")

    def get_gridpoints_str(self, location_dict):
        return "{}/{},{}".format(location_dict.get("wfo"), location_dict.get("x"), location_dict.get("y"))

    def validate_location(self, service_name, location):
        if service_name == "get_current_weather":
            return self.validate_location_formats(("station",), location)
        else:
            return self.validate_location_formats(("gridpoints", "lat/long"),
                                            location)

    def validate_location_formats(self, accepted_formats, location):
        if ("lat/long" in accepted_formats) and (location.get('lat') and location.get('long')):
            location_string = self.get_lat_long_str(location)
            if LAT_LONG_REGEX.match(location_string):
                return True
        elif ("station" in accepted_formats) and (location.get('station')):
            location_string = self.get_station_str(location)
            if STATION_REGEX.match(location_string):
                return True
            else:
                _log.debug("station did not matched regex")
                return False

        elif ("gridpoints" in accepted_formats) and (location.get("wfo") and location.get("x") and location.get("y")):
            if WFO_REGEX.match(location.get("wfo")) and (1 <= len(str(location.get("x"))) <= 3) and \
                    (1 <= len(str(location.get("y"))) <= 3):
                return True
        else:
            return False

    def generate_response_error(self, response_code):
        code_x100 = int(response_code / 100)
        if code_x100 == 2:
            raise RuntimeError("API request success, no data returned (code {})".format(response_code))
        elif code_x100 == 3:
            raise RuntimeError("API redirected, but requests did not reach the intended location (code {})"
                               .format(response_code))
        elif code_x100 == 4:
            raise RuntimeError("Client's API request failed (code {})".format(response_code))
        elif code_x100 == 5:
            raise RuntimeError("API request to server failed (code {})".format(response_code))
        else:
            raise RuntimeError("API request failed with unexpected response code (code {})"
                               .format(response_code))

    @doc_inherit
    def query_current_weather(self, location):
        """

        :param location: currently accepts station id (K followed by 3 letters, case insensitive) or
        lat/long (up to 4 decimals)
        :return: a single current data record as a list
        """
        if location.get('station'):
            formatted_location = self.get_location_string(location)
            url = "https://api.weather.gov/stations/{}/" \
                  "observations/latest".format(formatted_location)
        else:
            raise ValueError('Invalid location. Expected format is:'
                             '{"station":"station_id_value"}')
        grequest = [grequests.get(url, headers=self.headers, timeout=3)]
        gresponse = grequests.map(grequest)[0]
        response = json.loads(gresponse.content)
        if gresponse.status_code != 200:
            self.generate_response_error(gresponse.status_code)
        else:
            properties = response["properties"]
            observation_time = properties["timestamp"]
            return observation_time, properties

    @doc_inherit
    def query_hourly_forecast(self, location):
        """

        :param location: currently accepts lat/long only
        :return:
        """
        if location.get('lat') and location.get('long'):
            formatted_location = self.get_location_string(location)
            url = "https://api.weather.gov/points/{}/forecast/hourly".format(formatted_location)
        elif location.get("wfo") and location.get("x") and location.get("y"):
            formatted_location = self.get_gridpoints_str(location)
            url = "https://api.weather.gov/gridpoints/{}/forecast/hourly".format(formatted_location)
        else:
            raise ValueError("Improperly formatted station ID was passed.")
        _log.debug("Request Url: {}".format(url))
        grequest = [grequests.get(url, headers=self.headers, timeout=3)]
        gresponse = grequests.map(grequest)[0]
        response = json.loads(gresponse.content)
        if gresponse.status_code != 200:
            self.generate_response_error(gresponse.status_code)
        else:
            data = []
            properties = response["properties"]
            generation_time = properties["generatedAt"]
            periods = properties["periods"]
            for period in periods:
                forecast_time = period["startTime"]
                record = [forecast_time, period]
                data.append(record)
            return generation_time, data

    def query_hourly_historical(self, location, start_date, end_date):
        """

        :param location:
        :param start_date:
        :param end_date:
        :return: NotImplementedError
        """
        raise NotImplementedError


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
