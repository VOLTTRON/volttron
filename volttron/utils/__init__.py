import re

from watchdog.events import PatternMatchingEventHandler

from volttron.platform import get_home
import logging

_log = logging.getLogger(__name__)


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


class VolttronHomeFileReloader(PatternMatchingEventHandler):
    """
    Extends PatternMatchingEvent handler to watch changes to a singlefile/file pattern within volttron home.
    filetowatch should be path relative to volttron home.
    For example filetowatch auth.json with watch file <volttron_home>/auth.json.
    filetowatch *.json will watch all json files in <volttron_home>
    """
    def __init__(self, filetowatch, callback):
        super(VolttronHomeFileReloader, self).__init__([get_home() + '/' + filetowatch])
        _log.debug("patterns is {}".format([get_home() + '/' + filetowatch]))
        self._callback = callback

    def on_any_event(self, event):
        _log.debug("Calling callback on event {}".format(event))
        self._callback()


class AbsolutePathFileReloader(PatternMatchingEventHandler):
    """
    Extends PatternMatchingEvent handler to watch changes to a singlefile/file pattern within volttron home.
    filetowatch should be path relative to volttron home.
    For example filetowatch auth.json with watch file <volttron_home>/auth.json.
    filetowatch *.json will watch all json files in <volttron_home>
    """
    def __init__(self, filetowatch, callback):
        super(VolttronHomeFileReloader, self).__init__([filetowatch])
        self._callback = callback
        self._filetowatch = filetowatch

    @property
    def watchfile(self):
        return self._filetowatch

    def on_any_event(self, event):
        self._callback()
