#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

from __future__ import print_function, absolute_import

import logging
import requests
import gevent
import zmq
from volttron.platform.agent import utils
from .agent import Agent, Core, RPC
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from zmq.utils import jsonapi
from urlparse import urlparse, urljoin
from gevent.fileobject import FileObject
_log = logging.getLogger(__name__)
from datetime import datetime, timedelta

class DiscoveryError(StandardError):
    """ Raised when a different volttron central tries to register.
    """
    pass


class KeyDiscoveryAgent(Agent):
    """
    Class to get server keys of external/remote platforms
    """
    def __init__(self, address, serverkey, identity, external_address_config, bind_web_address, *args, **kwargs):
        super(KeyDiscoveryAgent, self).__init__(identity, address, **kwargs)
        self._external_address_file = external_address_config
        self._ext_addresses = dict()
        self._grnlets = dict()
        self._vip_socket = None
        self._my_web_address = bind_web_address

    @Core.receiver('onstart')
    def startup(self, sender, **kwargs):
        """
        Try to get server keys of all the remote platforms. If unsuccessful, setup events to try again later
        :param sender: caller
        :param kwargs: optional arguments
        :return:
        """
        self._vip_socket = self.core.socket
        self._read_platform_address_file()
        for name in self._ext_addresses:
            if self._ext_addresses[name]['bind-web-address'] not in self._my_web_address:
                web_address = self._ext_addresses[name]['bind-web-address']
                self._distribute_key(name, web_address)

    def _delayed_discovery(self, name, web_address):
        """
        Try to get serverkey of remote platform. If unsuccessful, try again later
        :param name: name of remote instance
        :param web_address: web address of remote instance
        :return:
        """
        serverkey = ''
        self._grnlets[name].cancel()
        self._grnlets.pop(name, None)
        self._distribute_key(name, web_address)


    def _distribute_key(self, name, web_address):
        """
            Try to get serverkey of remote instance and send it to RoutingService to connect to the remote instance.
            If unsuccessful, try again later.
        :param name: instance name
        :param web_address: web address of remote instance
        :return:
        """
        serverkey = ''
        try:
            serverkey = self._get_serverkey(web_address)
            _log.debug("Found key")
        except DiscoveryError:
            _log.debug("Try again later")
            # If discovery error, try again later
            utc_now = utils.get_aware_utc_now()
            delay = utc_now + timedelta(seconds=2)
            self._grnlets[name] = self.core.schedule(delay, self._delayed_discovery, name, web_address)
        except ConnectionError:
            pass

        # Send the serverkey to RoutingService to establish socket connection with remote platform
        if serverkey:
            frames = [b'external_serverkey', bytes(serverkey), name]
            self._vip_socket.send_vip(b'', 'routing_table', frames, copy=False)

    def _read_platform_address_file(self):
        """
        Read the external addresses file
        :return:
        """

        try:
            with open(self._external_address_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                self._ext_addresses = jsonapi.loads(data) if data else {}
        except IOError as e:
            _log.error("Error opening file %", self._external_address_file)
        except Exception:
            _log.exception('error loading %s', self._external_address_file)

    def _get_serverkey(self, web_address):
        """
        Use http discovery call to get serverkey of remote instance
        :param web_address: web address of remote instance
        :return:
        """

        r = {}
        try:
            parsed = urlparse(web_address)

            assert parsed.scheme
            assert not parsed.path

            real_url = urljoin(web_address, "/discovery/")
            response = requests.get(real_url)

            if not response.ok:
                raise DiscoveryError(
                    "Invalid discovery response from {}".format(real_url)
                )
            r = response.json()
            return r['serverkey']
        except AttributeError as e:
            raise DiscoveryError(
                "Invalid web_address passed {}"
                    .format(web_address)
            )
        except (ConnectionError, NewConnectionError) as e:
            raise DiscoveryError(
                "Connection to {} not available".format(real_url)
            )
        except Exception as e:
            raise DiscoveryError(
                "Unknown Exception".format(e.message)
            )
