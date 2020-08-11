# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


import datetime
import errno
import inspect
import logging
import os, os.path
from pprint import pprint
import re
import sys

from volttron.platform.vip.agent import Core, Agent
from volttron.platform.agent import utils
from volttron.platform import jsonrpc


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

# Set the bath based upon the currently executing file.  This allows us to
# debug through pycharm, but still have the reference correct when we deploy
# through the normal VOLTTRON control mechanisms.
MY_PATH = os.path.dirname(__file__)
WEBROOT = os.path.join(MY_PATH, "webroot")


class SimpleWebAgent(Agent):
    """
    A simple web enabled agent that will hook up with a volttron message bus
    and allow interaction between it via http.  This example agent shows a
    simple file serving agent, a json-rpc based call, and a websocket based
    connection mechanism.
    """

    def __init__(self, config_path, **kwargs):
        super(SimpleWebAgent, self).__init__(enable_web=True,
                                             **kwargs)

    @Core.receiver("onstart")
    def starting(self, sender, **kwargs):
        """
        Register routes for use through http.

        :param sender:
        :param kwargs:
        :return:
        """

        _log.debug("Starting: {}".format(self.__class__.__name__))

        ####################################################################
        # Path based registration examples
        #
        # Files will need to be in webroot/simpleweb in order for them to be
        # browsed from http://localhost:8080/simpleweb/index.html
        #
        # Note: filename is required as we don't currently autoredirect to
        # any default pages.
        self.vip.web.register_path("/simpleweb", os.path.join(WEBROOT))

        # Note the following two examples show the way to call either a jsonrpc
        # (default) endpoint and one that returns a different content-type.
        # With the JSON-RPC example from vc we only allow post requests, however
        # this is not required.
        
        # Endpoint will be available at http://localhost:8080/simple/text
        self.vip.web.register_endpoint("/simple/text", callback=self.text)
        
        # Endpoint will be available at http://localhost:8080/simple/jsonrpc
        self.vip.web.register_endpoint("/simpleweb/jsonrpc", self.rpcendpoint)

    def text(self, env, data):
        """
        Text/html content type specified so the browser can act appropriately.
        """
        # Response Type 200 OK is normal operation
        # 404 is not found
        return "200 OK", "This is some text", [("Content-Type", "text/html")]

    def rpcendpoint(self, env, data):
        """
        The default response is application/json so our endpoint returns appropriately
        with a json based response.
        """
        # Note we aren't using a valid json request to get the following output
        # id will need to be grabbed from data etc
        return jsonrpc.json_result("id", "A large number of responses go here")


def main():
    utils.vip_main(SimpleWebAgent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
