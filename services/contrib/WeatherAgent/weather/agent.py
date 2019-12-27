
from datetime import datetime
import logging
import sys
import urllib.request, urllib.error, urllib.parse
import socket
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform import jsonapi


utils.setup_logging()
_log = logging.getLogger(__name__)


class WeatherAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(WeatherAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        # dictionary of different topics being published
        self.current_publishes = {}
        # Change next line to your wunderground API key
        self.api_key = ''
        self.default_config = {'api_key': self.api_key}
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")
    
    def configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)
        # make sure config variables are valid
        try:
            self.api_key = str(config['api_key'])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))

    @Core.receiver("onstart")
    def starting(self, sender, **kwargs):
        self.subscribe_to_buses()
        _log.info("Weather agent started")

    def add_weather_report(self, peer, sender, bus, topic, headers, message):
        _log.debug("message is %s", message)
        if self.is_json_message(message, sender):
            message = jsonapi.loads(message)
            if self.is_expected_add_message(message):
                weather_report_type = message["type"]
                city = message["city"]
                state = message["state"]
                repeat_time = message["time"]
                topic_name = self.create_topic_name(weather_report_type, city, state)
                wunderground_url = self.make_url(weather_report_type, city, state)
                _log.info("Topic name for sender %s is %s, url is %s.", sender, topic_name, wunderground_url)
                if not self.topic_is_being_published(topic_name):
                    self.start_new_publish(topic_name, repeat_time, wunderground_url, sender)
                else:
                    assert topic_name in self.current_publishes
                    assert 'senders' in self.current_publishes[topic_name]
                    assert 'freq' in self.current_publishes[topic_name]
                    assert 'greenlet' in self.current_publishes[topic_name]
                    self.update_existing_topic(topic_name, repeat_time, wunderground_url, sender)
            else:
                _log.info("Unexpected Add Weather Report message. Make sure JSON message has requires fields")
        else:
            _log.info("Message must be JSON")

    def del_weather_report(self, peer, sender, bus, topic, headers, message):
        if self.is_json_message(message, sender):
            message = jsonapi.loads(message)
            if self.is_expected_delete_message(message):
                topic_name = self.create_topic_name(message["type"], message["city"], message["state"])
                if self.topic_is_being_published(topic_name):
                    publish_report_details = self.current_publishes[topic_name]
                    assert publish_report_details is not None
                    assert publish_report_details['senders'] is not None
                    # Make sure the weather report delete request is from a currently subscribed sender
                    if sender in publish_report_details['senders']:
                        publish_report_details['senders'].remove(sender)
                        if self.topic_has_no_subscribers(topic_name):
                            self.stop_publishing_topic(topic_name)
                    else:
                        _log.info("Sender not subscribed to topic. No actions performed")
                else:
                    _log.info("Topic not currently being published, nothing was removed")
            else:
                _log.info("Unexpected delete weather report message. Make sure all required fields are there")
        else:
            _log.info("Message must be JSON format")

    def create_topic_name(self, report_type, city, state):
        topic_name = city + '/' + state + '/' + report_type
        return topic_name

    def make_url(self, weather_report_type, city, state):
        base_url = 'http://api.wunderground.com/api/' + self.api_key + '/'
        appended_url = base_url + weather_report_type + '/q/' + state + '/' + city + '.json'
        return appended_url

    def is_json_message(self, message, sender):
        try:
            jsonapi.loads(message)
            return True
        except ValueError:
            _log.info("Message published by %s has invalid value (JSON format)", sender)
            return False
        except TypeError:
            _log.info("Message published by %s has invalid type (JSON format)", sender)
            return False

    def is_expected_delete_message(self, message):
        if isinstance(message, dict):
            if all(k in message for k in ("type", "city", "state")) and len(message) >= 3:
                return True
        return False

    def is_expected_add_message(self, message):
        if self.is_expected_delete_message(message) and "time" in message:
            time = message["time"]
            if isinstance(time, int):
                # Repeat request time must be reasonably high
                if time > 30:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def change_publish_time_frequency(self, topic_name, repeat_time, wunderground_url):
        parsed_weather_data = self.retrieve_weather_data(wunderground_url)
        updated_greenlet = self.core.periodic(repeat_time, self.publish_weather_report, [topic_name, parsed_weather_data])
        self.current_publishes[topic_name]['greenlet'].kill()
        self.current_publishes[topic_name]['greenlet'] = updated_greenlet
        self.current_publishes[topic_name]['freq'] = repeat_time

    def topic_is_being_published(self, topic_name):
        return topic_name in self.current_publishes

    def start_new_publish(self, topic_name, repeat_time, wunderground_url, sender):
        try:
            parsed_weather_data = self.retrieve_weather_data(wunderground_url)
            if "error" not in parsed_weather_data["response"]:
                periodic_greenlet = self.core.periodic(repeat_time, self.publish_weather_report,
                                                       [topic_name, parsed_weather_data])
                self.current_publishes[topic_name] = {'freq': repeat_time, 'senders': {sender},
                                                      'greenlet': periodic_greenlet}
            else:
                _log.info("City, state, or request type invalid.")
        except urllib.error.URLError:
            _log.info("No internet connection?")
        except socket.timeout:
            _log.info("Connection timed out!")

    def topic_has_no_subscribers(self, topic_name):
        return len(self.current_publishes[topic_name]['senders']) == 0

    def stop_publishing_topic(self, topic_name):
        _log.info('Ending publishing to topic %s', topic_name)
        self.current_publishes[topic_name]['greenlet'].kill()
        self.current_publishes.pop(topic_name, None)

    def update_existing_topic(self, topic_name, repeat_time, wunderground_url, sender):
        try:
            if self.current_publishes[topic_name]['freq'] > repeat_time:
                self.change_publish_time_frequency(topic_name, repeat_time, wunderground_url)
            self.current_publishes[topic_name]['senders'].add(sender)
        except urllib.error.URLError:
            _log.info("Check internet connection")
        except socket.timeout:
            _log.info("Connection timed out!")

    def publish_weather_report(self, topic_name, parsed_weather_data):
        now = utils.format_timestamp(datetime.utcnow())
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        self.vip.pubsub.publish('pubsub', topic_name, headers, jsonapi.dumps(parsed_weather_data))

    def retrieve_weather_data(self, url):
        f = urllib.request.urlopen(url, None, 5)
        json_string = f.read()
        f.close()
        return jsonapi.loads(json_string)

    def subscribe_to_buses(self):
        self.vip.pubsub.subscribe('pubsub', 'Add Weather Service', callback=self.add_weather_report)
        self.vip.pubsub.subscribe('pubsub', 'Stop Weather Service', callback=self.del_weather_report)


def main(argv=sys.argv):
    try:
        utils.vip_main(WeatherAgent)
    except Exception as e:
            _log.exception(e)


if __name__ == '__main__':
    sys.exit(main())
