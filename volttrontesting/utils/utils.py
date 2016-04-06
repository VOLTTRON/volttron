

import time

import gevent


def poll_gevent_sleep(max_seconds, condition=lambda: True):
    """Sleep until condition is true or max_seconds has passed.

    :param int max_seconds: max seconds to wait for condition
    :param function condition: function to run (must return bool)
    :return: True if condition returned true; False on timeout
    :rtype: bool
    :raises ValueError: if max_seconds is negative
    """
    if max_seconds < 0:
        raise ValueError('max_seconds must be positive number')
    time_start = time.time()
    while True:
        if condition():
            return True
        gevent.sleep(0.2)
        if time.time() > time_start + max_seconds:
            return False


def messages_contains_prefix(prefix, messages):
    """ REturns true if any of the keys of message start with prefix.

    :param prefix:
    :param messages:
    :return:
    """
    return any(map(lambda x: x.startswith(prefix), messages.keys()))
