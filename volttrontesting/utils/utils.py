import os
import socket
import subprocess
import time
from datetime import datetime
from random import randint
from random import random

import gevent
import mock
import pytest

from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod


def is_running_in_container():
    # type: () -> bool
    """ Determines if we're running in an lxc/docker container. """
    out = subprocess.check_output('cat /proc/1/sched', shell=True)
    out = out.decode('utf-8').lower()
    checks = [
        'docker' in out,
        '/lxc/' in out,
        out.split()[0] not in ('systemd', 'init',),
        os.path.exists('/.dockerenv'),
        os.path.exists('/.dockerinit'),
        os.getenv('container', None) is not None
    ]
    return any(checks)


def get_hostname_and_random_port(min_ip=5000, max_ip=6000):
    with open('/etc/hostname') as fp:
        hostname = fp.read().strip()

    assert hostname
    try:
        # socket.getfqdn(hostname)
        ip = socket.gethostbyname(hostname)
        port = get_rand_port(ip, min_ip, max_ip)
    except socket.gaierror:
        err = "Lookup of hostname {} unssucessful, please verify your /etc/hosts " \
              "doesn't have a local resolution to hostname".format(hostname)
        raise StandardError(err)
    return hostname, port


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


def get_rand_http_address(https=False):
    if https:
        host, port = get_hostname_and_random_port()
        result = "https://{}:{}".format(host, port)
    else:
        result = "http://{}".format(get_rand_ip_and_port())
    return result


def get_rand_tcp_address():
    return "tcp://{}".format(get_rand_ip_and_port())


def get_rand_vip():
    return get_rand_tcp_address()


def get_rand_ip_and_port():
    ip = "127.0.0.{}".format(randint(1, 254))
    port = get_rand_port(ip)
    return ip + ":{}".format(port)


def get_rand_port(ip=None, min_ip=5000, max_ip=6000):
    port = randint(min_ip, max_ip)
    if ip:
        while is_port_open(ip, port):
            port = randint(min_ip, max_ip)
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

    time1 = utils.format_timestamp( datetime.utcnow())
    headers = {
        headers_mod.DATE: time1,
        headers_mod.TIMESTAMP: time1
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
        # pytest.approx gives 10^-6 (one millionth accuracy)
        assert message[0][k] == pytest.approx(v)


class AgentMock(object):
    '''
    The purpose for this parent class is to be used for unit
    testing of agents. It takes in the class methods of other
    classes, turns them into it's own mock methods. For testing,
    dynamically replace the agent's current base class with this
    class, while passing in the agent's current classes as arguments.

    For example:
        Agent_to_test.__bases__ = (AgentMock.imitate(Agent, Agent()), )

    As noted in the example, __bases__ takes in a tuple.
    Also, the parent class Agent is passed as both Agent and the
    instantiated Agent(), since it contains a class within it
    that needs to be mocked as well
    '''
    @classmethod
    def imitate(cls, *others):
        for other in others:
            for name in other.__dict__:
                try:
                    setattr(cls, name, mock.create_autospec(other.__dict__[name]))
                except (TypeError, AttributeError):
                    pass
        return cls
