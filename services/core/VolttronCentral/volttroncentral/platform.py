import logging
from volttron.platform.agent.utils import get_utc_seconds_from_epoch

class Platforms(object):
    def __init__(self, vip):
        self._vip = vip
        self._platforms = {}
        self._log = logging.getLogger(__file__)

    def create_platform(self, platform_hash, **kwargs):
        self._platforms[platform_hash] = PlatformHandler(self._vip, **kwargs)
        return self._platforms[platform_hash]


class PlatformHandler(object):

    def __init__(self, vip, address, address_type, serverkey=None,
                 display_name=None):
        self.conn = None

        self._last_connection_checked = None
        self.devices = {}
        self.address
        self.address_type
        self.serverkey = None
        self.display_name = None
        self._log = logging.getLogger(__file__)

    def _attempt_connection(self):
        pass


    def is_bus_connected(self):
        return False

    def get_devices(self, cached=True):
        pass

