import re

from watchdog.events import PatternMatchingEventHandler


def is_ip_private(vip_address):
    """ Determines if the passed vip_address is a private ip address or not.

    :param vip_address: A valid ip address.
    :return: True if an internal ip address.
    """
    ip = vip_address.strip().lower().split("tcp://")[1]

    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile("^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile("^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile("^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile("^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) is not None or priv_24.match(
        ip) is not None or priv_20.match(ip) is not None or priv_16.match(
        ip) is not None


def get_hostname():
    with open('/etc/hostname') as fp:
        hostname = fp.read().strip()

    assert hostname
    return hostname


class FileReloader(PatternMatchingEventHandler):
    def __init__(self, filetowatch, callback):
        super(FileReloader, self).__init__(['*/'+filetowatch])
        self._callback = callback
        self._filetowatch = filetowatch

    @property
    def watchfile(self):
        return self._filetowatch

    def on_any_event(self, event):
        self._callback()
