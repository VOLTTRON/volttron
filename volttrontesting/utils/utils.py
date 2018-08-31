from datetime import datetime
import socket
import time
from random import randint
from random import random

import gevent
import pytest

from volttron.platform.messaging import headers as headers_mod


def poll_gevent_sleep(max_seconds, condition=lambda: True, sleep_time=0.2):
    """Sleep until condition is true or max_seconds has passed.

    :param int max_seconds: max seconds to wait for condition
    :param function condition: function to run (must return bool)
    :return: True if condition returned true; False on timeout
    :rtype: bool
    :raises ValueError: if max_seconds is negative
    """
    if max_seconds < 0:
        raise ValueError('max_seconds must be positive number')

    if sleep_time < 0.2:
        raise ValueError('sleep_time must be > 0.2')

    time_start = time.time()
    while True:
        if condition():
            return True
        gevent.sleep(sleep_time)
        if time.time() > time_start + max_seconds:
            return False


def messages_contains_prefix(prefix, messages):
    """ Returns true if any of the keys of message start with prefix.

    :param prefix:
    :param messages:
    :return:
    """
    return any(map(lambda x: x.startswith(prefix), messages.keys()))


def get_rand_http_address():
    return "http://{}".format(get_rand_ip_and_port())


def get_rand_tcp_address():
    return "tcp://{}".format(get_rand_ip_and_port())


def get_rand_vip():
    return get_rand_tcp_address()


def get_rand_ip_and_port():
    ip = "127.0.0.{}".format(randint(1, 254))
    port = get_rand_port(ip)
    return ip + ":{}".format(port)


def get_rand_port(ip=None):
    port = randint(5000, 6000)
    if ip:
        while is_port_open(ip, port):
            port = randint(5000, 6000)
    return port


def is_port_open(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((ip, port))
    return result == 0


def build_devices_header_and_message(points=['abc', 'def']):

    meta_templates = [
        {'units': 'F', 'tz': 'UTC', 'type': 'float'},
        {'units': '%', 'tz': 'UTC', 'type': 'float'}
    ]

    data = {}
    meta_data = {}

    for point in points:
        data[point] = random() * 10
        meta_data[point] = meta_templates[randint(0,len(meta_templates)-1)]

    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }

    return headers, [data, meta_data]


def publish_device_messages(to_platform,
                            all_topic='devices/campus/building/unit/all',
                            points=['abc', 'def']):
    assert to_platform is not None
    agent = to_platform.build_agent()
    headers, message = build_devices_header_and_message(points)
    agent.vip.pubsub.publish(peer='pubsub', topic=all_topic, headers=headers,
                             message=message).get()
    gevent.sleep(.1)
    agent.core.stop()
    return headers, message


def publish_message(to_platform,
                    topic,
                    headers={},
                    message={}):
    assert to_platform is not None
    agent = to_platform.build_agent()
    headers, message = headers, message
    agent.vip.pubsub.publish(peer='pubsub', topic=topic, headers=headers,
                             message=message).get()
    gevent.sleep(.1)
    agent.core.stop()
    return headers, message


def validate_published_device_data(expected_headers, expected_message,
                                   headers, message):
    assert headers and message
    assert expected_headers[headers_mod.DATE] == headers[headers_mod.DATE]

    for k, v in expected_message[0].items():
        assert k in message[0]
        assert message[0][k] == pytest.approx(v, abs=1e-6)
