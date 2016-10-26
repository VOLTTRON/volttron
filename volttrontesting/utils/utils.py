import socket
import time
from random import randint

import gevent


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


