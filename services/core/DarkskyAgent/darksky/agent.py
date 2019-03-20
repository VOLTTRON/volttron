"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import datetime
import pytz
import sys
import re
import json
import grequests
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now
from volttron.platform.agent.base_weather import BaseWeatherAgent

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

WEATHER_WARN = "weather_warnings"
WEATHER_RESULTS = "weather_results"

SERVICES_MAPPING = {
 'SERVICE_HOURLY_FORECAST':
     {'service': 'get_hourly_forecast', 'json_name': 'hourly', 'type':
         'forecast'},
 'SERVICE_DAIlY_FORECAST':
     {'service': 'get_daily_forecast', 'json_name':  'daily', 'type':
         'forecast'},
 'SERVICE_CURRENT_WEATHER':
     {'service': 'get_current_weather', 'json_name': 'currently', 'type':
         'current'},
 'SERVICE_MINUTELY_FORECAST':
     {'service': 'get_minutely_forecast', 'json_name': 'minutely', 'type':
         'forecast'}
}

WEATHER_ERROR = "weather_error"

LAT_LONG_REGEX = re.compile("^-?[0-9]{1,3}(\.[0-9]{1,4})?$")


def darksky(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Darksky
    :rtype: Darksky
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}
    if not config:
        _log.error("Darksky agent configuration: ".format(config))
        # TODO an additional check should be made here for the api key
        raise RuntimeError("Darksky agent must be configured with an api key.")
    _log.debug("config_dict before init: {}".format(config))
    utils.update_kwargs_with_config(kwargs, config)

    return Darksky(**kwargs)


class Darksky(BaseWeatherAgent):
    """
    Document agent constructor here.
    """

    def __init__(self, performance_mode=False, **kwargs):
        super(Darksky, self).__init__(**kwargs)
        self.performance_mode = performance_mode
        _log.debug("vip_identity: " + self.core.identity)
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        minutely_service = SERVICES_MAPPING['SERVICE_MINUTELY_FORECAST'][
                                  'service']
        self.register_service(minutely_service,
                              self.get_update_interval(minutely_service),
                              'forecast', description=
                              "Params: locations ([{type: value},...])")
        daily_service = SERVICES_MAPPING['SERVICE_DAIlY_FORECAST']['service']
        self.register_service(daily_service,
                              self.get_update_interval(daily_service),
                              'forecast', description=
                              "Params: locations ([{type: value},...])")
        self.remove_service("get_hourly_historical")

    @RPC.export
    def get_version(self):
        """
        Provides the current version of the agent.
        :return: current version number in string format.
        """
        return __version__

    def validate_location(self, service_name, location):
        if 'lat' in location and 'long' in location:
            if LAT_LONG_REGEX.match(str(location['lat'])) and \
                    LAT_LONG_REGEX.match(str(location['long'])):
                return True
        else:
            return False

    # TODO update/validate service intervals
    def get_update_interval(self, service_name):
        if service_name == "get_current_weather":
            return datetime.timedelta(hours=1)
        elif service_name == "get_hourly_forecast":
            return datetime.timedelta(hours=1)
        elif service_name == "get_minutely_forecast":
            return datetime.timedelta(minutes=5)
        elif service_name == 'get_daily_forecast':
            return datetime.timedelta(hours=1)
        else:
            return None

    # TODO
    def get_api_description(self, service_name):
        if service_name is "get_current_weather":
            return "Provides current weather observations by lat/long via RPC "\
                   "(Requires {'lat': <latitude>, 'long': <longitude>}"
        elif service_name is "get_hourly_forecast":
            return "Provides <hours> (optional) hours of forecast predictions "\
                   "by lat/long via RPC (Requires {'lat': <latitude>, 'long': "\
                   "<longitude>}"
        elif service_name is "get_minutely_forecast":
            return "Provides 60 minutes of forecast predictions "\
                   "by lat/long via RPC (Requires {'lat': <latitude>, 'long': "\
                   "<longitude>}"
        elif service_name is "get_daily_forecast":
            return "Provides 1 week of daily forecast predictions "\
                   "by lat/long via RPC (Requires {'lat': <latitude>, 'long': "\
                   "<longitude>}"
        else:
            raise RuntimeError(
                "Service {} is not implemented by Darksky.".format(
                    service_name))

    # TODO
    def get_point_name_defs_file(self):
        pass

    # TODO handle timezone offset
    def get_darksky_forecast(self, service, location):
        if "lat" in location and 'long' in location:
            url = "https://api.darksky.net/forecast/{key}/{lat}," \
               "{long}".format(key=self._api_key, lat=location['lat'],
                               long=location['long'])
            if self.performance_mode:
                services = ["currently", "hourly", "minutely", "daily"]
                if service in services:
                    services.remove(service)
                    url += "?excludes=" + ",".join(services)
                else:
                    raise RuntimeError("Requested service {} is not provided"
                                       "by the Darksky API".format(service))
        else:
            raise ValueError('Invalid location. Expected format is: '
                             '"{"lat": "xxx.xxxx", "long": "xxx.xxxx"}"')
        grequest = [grequests.get(url, headers=self.headers, timeout=3)]
        gresponse = grequests.map(grequest)[0]
        if gresponse is None:
            raise RuntimeError("get request did not return any "
                               "response")
        response = json.loads(gresponse.content)
        if gresponse.status_code != 200:
            self.generate_response_error(url, gresponse.status_code)
        return response

    @staticmethod
    def format_multientry_response(location, response, request_type,
                                   timezone=None):
        data = []
        generation_time = get_aware_utc_now()\
            .replace(microsecond=0, second=0, minute=0)
        for entry in response['data']:
            entry_time = datetime.datetime.fromtimestamp(entry['time'])
            if timezone:
                entry_time.replace(tzinfo=pytz.timezone(timezone))
            if request_type is 'forecast':
                data.append([json.dumps(location), generation_time, entry_time,
                             json.dumps(entry)])
            else:
                data.append([json.dumps(location), entry_time, json.dumps(
                    entry)])
        return data

    def query_current_weather(self, location):
        darksky_response = self.get_darksky_forecast(
            SERVICES_MAPPING['SERVICE_CURRENT_WEATHER']['service'], location)
        response_timezone = darksky_response['timezone']
        current_response = darksky_response.pop('currently')
        current_epoch = current_response['time']
        current_time = datetime.datetime.fromtimestamp(current_epoch)
        if response_timezone:
            current_time.replace(tzinfo=pytz.timezone(response_timezone))
        if not self.performance_mode:
            # if performance mode isn't running we'll be receiving extra data
            # that we can store to help with conserving daily api calls
            for service in SERVICES_MAPPING:
                if service is not 'SERVICE_CURRENT_WEATHER' and \
                        service in darksky_response:
                    service_response = darksky_response.pop(
                        SERVICES_MAPPING[service]['json_name'])
                    service_data = self.format_multientry_response(
                        location, service_response, SERVICES_MAPPING[
                            service]['type'], timezone=response_timezone)
                    self.store_weather_records(SERVICES_MAPPING[service][
                                                   'service'], service_data)
        return format_timestamp(current_time), current_response

    def query_forecast_service(self, service_name, location):
        darksky_response = self.get_darksky_forecast(
            SERVICES_MAPPING[service_name]['service'], location)
        forecast_response = darksky_response.pop(SERVICES_MAPPING[service_name]
                                                 ['json_name'])
        response_timezone = darksky_response['timezone']
        forecast_data = []
        for entry in forecast_response['data']:
            entry_time = datetime.datetime.fromtimestamp(entry['time'])
            if response_timezone:
                entry_time.replace(tzinfo=pytz.timezone(response_timezone))
            forecast_data.append([format_timestamp(entry_time), entry])
        generation_time = format_timestamp(get_aware_utc_now()
                                           .replace(microsecond=0, second=0,
                                                    minute=0))
        if not self.performance_mode:
            # if performance mode isn't running we'll be receiving extra data
            # that we can store to help with conserving daily api calls
            for service in SERVICES_MAPPING:
                if service is not service_name and service in darksky_response:
                    service_response = darksky_response.pop(
                        SERVICES_MAPPING[service]['json_name'])
                    if SERVICES_MAPPING[service]['type'] is not 'current':
                        service_data = self.format_multientry_response(
                            location, service_response, SERVICES_MAPPING[
                                service]['type'], timezone=response_timezone)
                    else:
                        service_data = \
                            [json.dumps(location), datetime.datetime.
                                fromtimestamp(service_response['time']),
                             json.dumps(service_response)]
                    self.store_weather_records(SERVICES_MAPPING[service][
                                                   'service'], service_data)
        return generation_time, forecast_data

    def query_hourly_forecast(self, location):
        generation_time, forecast_data = self.query_forecast_service(
            'SERVICE_HOURLY_FORECAST', location)
        return generation_time, forecast_data

    def query_daily_forecast(self, location):
        generation_time, forecast_data = self.query_forecast_service(
            'SERVICE_DAILY_FORECAST', location)
        return generation_time, forecast_data

    def query_minutely_forecast(self, location):
        generation_time, forecast_data = self.query_forecast_service(
            'SERVICE_MINUTELY_FORECAST', location)
        return generation_time, forecast_data

    @RPC.export
    def get_minutely_forecast(self, locations, minutes=60):
        request_time = get_aware_utc_now()
        result = []
        for location in locations:
            record_dict = self.validate_location_dict(
                SERVICES_MAPPING['SERVICE_MINUTELY_FORECAST']['service'],
                location)
            if record_dict:
                result.append(record_dict)
                continue

            # check if we have enough recent data in cache
            record_dict = self.get_cached_minutely_forecast(location, minutes,
                                                            request_time)
            cache_warning = record_dict.get(WEATHER_WARN)
            # if cache didn't work out query remote api
            if not record_dict.get(WEATHER_RESULTS):
                _log.debug("forecast weather by minute from api")
                record_dict = self.get_remote_minutely_forecast(location,
                                                                minutes,
                                                                request_time)
                if cache_warning:
                    warnings = record_dict.get(WEATHER_WARN, [])
                    warnings.extend(cache_warning)
                    record_dict[WEATHER_WARN] = warnings
                _log.debug("record_dict from remote : {}".format(record_dict))
            result.append(record_dict)
        return result

    @RPC.export
    def get_daily_forecast(self, locations, days):
        request_time = get_aware_utc_now()
        result = []
        for location in locations:
            record_dict = self.validate_location_dict(
                SERVICES_MAPPING['SERVICE_DAILY_FORECAST']['service'],
                location)
            if record_dict:
                result.append(record_dict)
                continue

            # check if we have enough recent data in cache
            record_dict = self.get_cached_daily_forecast(location, days,
                                                         request_time)
            cache_warning = record_dict.get(WEATHER_WARN)
            # if cache didn't work out query remote api
            if not record_dict.get(WEATHER_RESULTS):
                _log.debug("forecast weather by minute from api")
                record_dict = self.get_remote_daily_forecast(location,
                                                             days,
                                                             request_time)
                if cache_warning:
                    warnings = record_dict.get(WEATHER_WARN, [])
                    warnings.extend(cache_warning)
                    record_dict[WEATHER_WARN] = warnings
                _log.debug("record_dict from remote : {}".format(record_dict))
            result.append(record_dict)
        return result

    @staticmethod
    def generate_response_error(url, response_code):
        """
        raises a descriptive runtime error based on the response code
        returned by a service.
        :param url: actual url used for requesting data from Darksky
        :param response_code: Http response code returned by a service
        following a request
        """
        code_x100 = int(response_code / 100)
        if code_x100 == 2:
            raise RuntimeError(
                "Remote API returned no data(code:{}, url:{})".format(
                    response_code, url))
        elif code_x100 == 3:
            raise RuntimeError(
                "Remote API redirected request, "
                "but redirect failed (code:{}, url:{})".format(response_code,
                                                               url))
        elif code_x100 == 4:
            raise RuntimeError(
                "Invalid request ({}) Remote API returned "
                " Code {}".format(url, response_code))
        elif code_x100 == 5:
            raise RuntimeError(
                "Remote API returned invalid response "
                "(code:{}, url:{})".format(response_code, url))
        else:
            raise RuntimeError(
                "API request failed with unexpected response "
                "code (code:{}, url:{})".format(response_code, url))


def main():
    """Main method called to start the agent."""
    utils.vip_main(darksky, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
