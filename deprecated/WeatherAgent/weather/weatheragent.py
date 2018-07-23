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

# }}}
import sys
import requests
import datetime
import logging
from dateutil.parser import parse

from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import headers as headers_mod, topics

from volttron.platform.agent import utils
from volttron.platform.vip.agent import *

import settings

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'

HEADER_NAME_DATE = headers_mod.DATE
HEADER_NAME_CONTENT_TYPE = headers_mod.CONTENT_TYPE
REQUESTS_EXHAUSTED = 'requests_exhausted'
'''
In order for this agent to retrieve data from Weather Underground,
 you must get a developer's key and put that into the seetings.py file.

http://www.wunderground.com/weather/api/

'''

TOPIC_DELIM = '/'

temperature = ["temperature_string", "temp_f", "temp_c", "feelslike_c", 
               "feelslike_f", "feelslike_string", "windchill_c", 
               "windchill_f", "windchill_string", "heat_index_c", 
               "heat_index_f", "heat_index_string"]
wind = ["wind_gust_kph", "wind_string", "wind_mph", "wind_dir", 
        "wind_degrees", "wind_kph", "wind_gust_mph", "pressure_in"]
location = ["local_tz_long", "observation_location", "display_location", 
            "station_id"]
time_topics = ["local_time_rfc822", "local_tz_short", "local_tz_offset", 
               "local_epoch", "observation_time", "observation_time_rfc822", 
               "observation_epoch"]
cloud_cover = ["weather", "solarradiation", "visibility_mi", "visibility_km", 
               "UV"]
precipitation = ["dewpoint_string", "precip_today_string", "dewpoint_f", 
                 "dewpoint_c", "precip_today_metric", "precip_today_in", 
                 "precip_1hr_in", "precip_1hr_metric", "precip_1hr_string"]
pressure_humidity = ["pressure_trend", "pressure_mb", "relative_humidity"]

categories = {'temperature': temperature, 'wind': wind,
              'location': location, 'precipitation': precipitation,
              'pressure_humidity': pressure_humidity,
              'time': time_topics, 'cloud_cover': cloud_cover}


class RequestCounter:
    def __init__(self, daily_threshold, minute_threshold, poll_time):
        dtime = datetime.datetime.now()
        f = open('.count', 'w+')
        line = f.readline()
        if line:
            saved_state = line.split(',')
            text_date = saved_state[0]
            saved_date = parse(text_date, fuzzy=True).date()
            if saved_date == dtime.date() and saved_state[2] == settings.KEY:
                self.daily = int(saved_state[1])
        else:
            self.daily = 0
        self.date = datetime.datetime.today().date()
        self.per_minute_requests = []
        self.minute_reserve = 1
        self.daily_threshold = daily_threshold
        if poll_time < 180:
            _log.warning('May exceed number of calls to WeatherUnderground'
                         'for free api plan limit is 500 queries per day. '
                         'poll_time should be greater than 3 minutes.')
        self.minute_threshold = minute_threshold - self.minute_reserve

    def request_available(self):
        '''
        Keep track of request on WU API key for saving state.
        '''
        now = datetime.datetime.today()
        if (now.date() - self.date).days < 1:
            if self.daily >= self.daily_threshold:
                False
        else:
            self.date = now.date()
            self.daily = 0
            f = open('.count', 'w+')
            _count = ''.join([str(self.date), ',',
                              str(self.daily), ',',
                              settings.KEY])
            f.write(_count)
            f.close()
        while (len(self.per_minute_requests) > 0 and
                (now - self.per_minute_requests[-1]).seconds > 60):
            self.per_minute_requests.pop()

        if len(self.per_minute_requests) < self.minute_threshold:
            self.per_minute_requests.insert(0, now)
            self.daily += 1
            f = open('.count', 'w+')
            _count = ''.join([str(self.date), ',',
                              str(self.daily), ',',
                              settings.KEY])
            f.write(_count)
            f.close()
        else:
            return False

        return True


def weather_service(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, '')

    agent_id = get_config('agentid')
    poll_time = get_config('poll_time')
    zip_code = get_config("zip")
    key = get_config('key')
    on_request_only = get_config('on_request_only')

    state = get_config("state")
    country = get_config("country")
    city = get_config("city")
    region = state if state != "" else country
    max_requests_per_day = get_config('daily_threshold')
    max_requests_per_minute = get_config('minute_threshold')

    class WeatherAgent(Agent):
        """Agent for querying WeatherUndergrounds API"""

        def __init__(self, **kwargs):
            super(WeatherAgent, self).__init__(**kwargs)
            self.valid_data = False

        @Core.receiver('onstart')
        def setup(self, sender, **kwargs):
            '''On start method'''
            self._keep_alive = True

            self.requestCounter = RequestCounter(max_requests_per_day,
                                                 max_requests_per_minute,
                                                 poll_time)
            # TODO: get this information from configuration file instead
            base = "http://api.wunderground.com/api/" + \
                (key if not key == '' else settings.KEY)
            self.baseUrl = base + "/conditions/q/"

            self.requestUrl = self.baseUrl
            if(zip_code != ""):
                self.requestUrl += zip_code + ".json"
            elif region != "":
                self.requestUrl += region + "/" + city + ".json"
            else:
                # Error Need to handle this
                print "No location selected"
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.WEATHER_REQUEST,
                                      callback=self.handle_request)
            if not on_request_only:
                self.weather = self.core.periodic(poll_time,
                                                  self.weather_push,
                                                  wait=0)

        def build_url_with_zipcode(self, zip_code):
            return self.baseUrl + zip_code + ".json"

        def build_url_with_city(self, region, city):
            return self.baseUrl + region + "/" + city + ".json"

        def build_dictionary(self, observation):
            weather_dict = {}
            for category in categories.keys():
                weather_dict[category] = {}
                weather_elements = categories[category]
                for element in weather_elements:
                    weather_dict[category][element] = observation[element]

            return weather_dict

        def publish_all(self, observation, topic_prefix="weather", headers={}):
            utcnow = utils.get_aware_utc_now()
            utcnow_string = utils.format_timestamp(utcnow)
            headers.update({HEADER_NAME_DATE: utcnow_string,
                            headers_mod.TIMESTAMP: utcnow_string})
            self.publish_subtopic(self.build_dictionary(observation),
                                  topic_prefix, headers)

        def publish_subtopic(self, publish_item, topic_prefix, headers):
            # TODO: Update to use the new topic templates
            if isinstance(publish_item, dict):
                # Publish an "all" property, converting item to json
                _topic = topic_prefix + TOPIC_DELIM + "all"
                self.vip.pubsub.publish(peer='pubsub',
                                        topic=_topic,
                                        message=publish_item,
                                        headers=headers)

                # Loop over contents, call publish_subtopic on each
                for topic in publish_item.keys():
                    self.publish_subtopic(publish_item[topic],
                                          topic_prefix + TOPIC_DELIM + topic,
                                          headers)
            else:
                # Item is a scalar type, publish it as is
                headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.PLAIN_TEXT
                self.vip.pubsub.publish(peer='pubsub',
                                        topic=topic_prefix,
                                        message=str(publish_item),
                                        headers=headers)

        def weather_push(self):
            '''
            Function called on periodic or request for weather information.
            '''
            _log.debug("Requesting url: "+self.requestUrl)
            (valid_data, observation) = self.request_data(self.requestUrl)
            if valid_data:
                headers = {headers_mod.FROM: agent_id}
                _log.debug('Headers: %s'.format(headers))
                self.publish_all(observation, headers=headers)
            else:
                _log.error("Invalid data, not publishing")

        def handle_request(self, peer, sender, bus, topic, headers, message):
            
            if sender == 'pubsub.compat':
                msg = jsonapi.loads(message[0])
            else:
                msg = message
                
            request_url = self.baseUrl

            # Identify if a zipcode or region/city was sent
            # Build request URL
            if 'zipcode' in msg:
                request_url = self.build_url_with_zipcode(msg['zipcode'])
            elif ('region' in msg) and ('city' in msg):
                request_url = self.build_url_with_city(msg['region'], msg['city'])
            else:
                _log.error('Invalid request, no zipcode '
                           'or region/city in request')
                # TODO: notify requester of error

            # Request data
            (valid_data, observation) = self.request_data(request_url)

            # If data is valid, publish
            if valid_data:
                resp_headers = {}
                resp_headers[headers_mod.TO] = headers[headers_mod.REQUESTER_ID]
                resp_headers['agentID'] = agent_id
                resp_headers[headers_mod.FROM] = agent_id
                _topic = 'weather' + TOPIC_DELIM + 'response'
                self.publish_all(observation, _topic, resp_headers)
            else:
                if observation == REQUESTS_EXHAUSTED:
                    _log.error('No requests avaliable')
                    # TODO: report error to client
                # Else, log that the data was invalid and report an error
                # to the requester
                else:
                    _log.error('Weather API response was invalid')
                    # TODO: send invalid data error back to requester

        def request_data(self, requestUrl):
            if self.requestCounter.request_available():
                try:
                    r = requests.get(requestUrl)
                    r.raise_for_status()
                    parsed_json = r.json()

                    observation = parsed_json['current_observation']
                    observation = convert(observation)
                    valid_data = True
                    return (valid_data, observation)
                except Exception as e:
                    _log.error(e)
                    valid_data = False
                    return (valid_data, None)
            else:
                _log.warning("No requests available")
                return (False, REQUESTS_EXHAUSTED)

        def print_data(self):
            print "{0:*^40}".format(" ")
            for key in self.observation.keys():
                print "{0:>25}: {1}".format(key, self.observation[key])
            print "{0:*^40}".format(" ")

    WeatherAgent.__name__ = 'weather_service'
    return WeatherAgent(**kwargs)


def convert(_input):
    if isinstance(_input, dict):
        return {convert(key): convert(value) for key, value in _input.iteritems()}
    elif isinstance(_input, list):
        return [convert(element) for element in _input]
    elif isinstance(_input, unicode):
        return _input.encode('utf-8')
    else:
        return _input


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(weather_service, version=__version__)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
