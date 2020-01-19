import logging
import requests
from urllib.parse import urlparse, urljoin

from volttron.platform import jsonapi
from volttron.platform.certs import Certs

_log = logging.getLogger(__name__)


class DiscoveryError(Exception):
    """ Raised when a different volttron central tries to register.
    """
    pass


class DiscoveryInfo(object):
    """ A DiscoveryInfo class.

    The DiscoveryInfo class provides a wrapper around the return values from
    a call to the /discovery/ endpoint of the `volttron.platform.web.
    """

    def __init__(self, **kwargs):

        self.discovery_address = kwargs.pop('discovery_address')
        self.vip_address = kwargs.pop('vip-address', None)
        self.serverkey = kwargs.pop('serverkey', None)
        self.instance_name = kwargs.pop('instance-name')
        try:
            self.rmq_address = kwargs.pop('rmq-address')
        except KeyError:
            self.messagebus_type = 'zmq'
        else:
            self.messagebus_type = 'rmq'
        try:
            self.rmq_ca_cert = kwargs.pop('rmq-ca-cert')
        except KeyError:
            self.messagebus_type = 'zmq'
        else:
            self.messagebus_type = 'rmq'
        self.certs = Certs()

        assert len(kwargs) == 0

    @staticmethod
    def request_discovery_info(web_address):
        """  Construct a `DiscoveryInfo` object.

        Requests a response from discovery_address and constructs a
        `DiscoveryInfo` object with the returned json.

        :param web_address: An http(s) address with volttron running.
        :return:
        """

        try:
            parsed = urlparse(web_address)

            assert parsed.scheme
            assert not parsed.path

            real_url = urljoin(web_address, "/discovery/")
            _log.info('Connecting to: {}'.format(real_url))
            response = requests.get(real_url, verify=False)

            if not response.ok:
                raise DiscoveryError(
                    "Invalid discovery response from {}".format(real_url)
                )
        except AttributeError as e:
            raise DiscoveryError(
                "Invalid web_address passed {}"
                .format(web_address)
            )
        except requests.exceptions.RequestException as e:
            raise DiscoveryError(
                "Connection to {} not available".format(real_url)
            )
        except Exception as e:
            raise DiscoveryError("Unhandled exception {}".format(e))

        return DiscoveryInfo(
            discovery_address=web_address, **(response.json()))

    def __str__(self):
        dk = {
            'discovery_address': self.discovery_address,
            'instance_name': self.instance_name,
            'rmq_address': self.rmq_address,
            'rmq_ca_cert': self.rmq_ca_cert,
            'messagebus_type': self.messagebus_type
        }
        if self.vip_address:
            dk['vip_address'] = self.vip_address
            dk['serverkey'] = self.serverkey

        return jsonapi.dumps(dk)
