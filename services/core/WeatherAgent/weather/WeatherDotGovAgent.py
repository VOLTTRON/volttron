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

import os
import sys
import requests
from services.core.WeatherAgent.weather.agent import BaseWeatherAgent
from volttron.platform.agent import utils
from volttron.utils.docs import doc_inherit
from volttron.platform.vip.agent import *


def weatherAgent():
    # TODO check out the "historian" method from the sqlhistorian

# TODO figure out if we are expected to resolve the location
class WeatherDotGovAgent(BaseWeatherAgent):
    def __init__(self):
        super(BaseWeatherAgent, None, "https://api.weather.gov/")


    @doc_inherit
    def query_current_weather(self, location, cache=True):
        # TODO get the datetime object outta the data
        most_recent_data = self.cache.get_current_data(location)
        if cache and most_recent_data:

        else:
            self.manage_cache_size()
            request = requests.request("GET", "https://api.weather.gov/points/{}/".format(location))
            # TODO handle request results
            data = []
            self.cache.store_weather_records("current", data)
            return data

    @doc_inherit
    def query_hourly_forecast(self, location, cache=True):
        # TODO get the datetime object outta the data
        most_recent_data = self.cache.get_forecast_data("hourly_forecast", location)
        if cache and len(most_recent_data):
            # TODO format from json for reporting
        else:
            self.manage_cache_size()
            request = requests.request("GET", "https://api.weather.gov/points/{}/forecast/hourly".format(location))
            # TODO record formatting for storage
            data = []
            self.cache.store_weather_records("hourly_forecast", data)
            # TODO record format for reporting
            return data

    # TODO compare with historians to see how they handle unimplemented methods
    def query_hourly_historical_Weather(self):
        raise NotImplementedError

    # TODO
    def get_location_specification(self):

def main(argv=sys.argv):
    """" Main entry point for the agent.

    :param argv:
    :return:
    """
    try:
        utils.vip_main(historian, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass