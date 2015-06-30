# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

from __future__ import absolute_import, print_function
import base64
from datetime import datetime
import gevent
import logging
import sys
import requests
import os
import os.path as p
import re
import shutil
import tempfile
import uuid

import psutil

import gevent
from zmq.utils import jsonapi
from volttron.platform.vip.agent import *

from volttron.platform import vip, jsonrpc, control
from volttron.platform.control import Connection
from volttron.platform.agent import utils

from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND,
                                       PARSE_ERROR, UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)

def listener_agent(config_path, **kwargs):
    config = utils.load_config(config_path)


    class ListenerAgent(Agent):

        def __init__(self, **kwargs):
            super(ListenerAgent, self).__init__(**kwargs)

            print('my identity {} address: {}'.format(self.core.identity,
                                                      self.core.address))
            # a list of registered managers of this platform.
            self._settings = {}
            self._load_settings()
            
            self._subscribed = False

        def _store_settings(self):
            with open('listener.settings', 'wb') as f:
                f.write(jsonapi.dumps(self._settings))
                f.close()

        def _load_settings(self):
            try:
                with open('listener.settings', 'rb') as f:
                    self._settings = self._settings = jsonapi.loads(f.read())
                f.close()
            except Exception as e:
                _log.debug('Exception '+ e.message)
                self._settings = {}

        @RPC.export
        def set_setting(self, key, value):
            _log.debug("Setting key: {} to value: {}".format(key, value))
            self._settings[key] = value
            self._store_settings()


        @RPC.export
        def get_setting(self, key):
            _log.debug('Retrieveing key: {}'.format(key))
            return self._settings.get(key, '')

        @Core.periodic(30)
        def publish_heartbeat(self):
            historian_present = False

#             base_topic = 'datalogger/log/listener/heartbeat'


            message = jsonapi.dumps({'Readings': "HI!!",
                                 'Units': 'string',
                                 'agentname': self.core.identity})
            self.vip.rpc.call('platform.agent','publish_to_peers', topic='neighborhood/needs',
                          message=message)
        
 
 
        @Core.receiver('onstart')
        def starting(self, sender, **kwargs):
            print('***** Demo Agent is starting')
        
            self.vip.pubsub.subscribe('pubsub', 
                                  '', self.onmessage)
            print("SUBSCRIBED")

        def onmessage(self, peer, sender, bus, topic, headers, message):
            
            print("ON MESSAGE: {}".format(message))
            
            
        
            '''
            Receive energy usage change message from another agent. If we have energy
            needs and there is now some available, use it.
            '''
#             message = jsonapi.loads(message[0])        
            
        @Core.receiver('onstop')
        def stoping(self, sender, **kwargs):
            pass

    ListenerAgent.__name__ = 'ListenerAgent'
    return ListenerAgent(**kwargs)




def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(listener_agent,
                       description='Agent available to manage from a remote '
                                    + 'system.',
                       no_pub_sub_socket=True,
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

from __future__ import absolute_import, print_function
import base64
from datetime import datetime
import gevent
import logging
import sys
import requests
import os
import os.path as p
import re
import shutil
import tempfile
import uuid

import psutil

import gevent
from zmq.utils import jsonapi
from volttron.platform.vip.agent import *

from volttron.platform import vip, jsonrpc, control
from volttron.platform.control import Connection
from volttron.platform.agent import utils

from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND,
                                       PARSE_ERROR, UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)

def listener_agent(config_path, **kwargs):
    config = utils.load_config(config_path)


    class ListenerAgent(Agent):

        def __init__(self, **kwargs):
            super(ListenerAgent, self).__init__(**kwargs)

            print('my identity {} address: {}'.format(self.core.identity,
                                                      self.core.address))
            # a list of registered managers of this platform.
            self._settings = {}
            self._load_settings()
            
            self._subscribed = False

        def _store_settings(self):
            with open('listener.settings', 'wb') as f:
                f.write(jsonapi.dumps(self._settings))
                f.close()

        def _load_settings(self):
            try:
                with open('listener.settings', 'rb') as f:
                    self._settings = self._settings = jsonapi.loads(f.read())
                f.close()
            except Exception as e:
                _log.debug('Exception '+ e.message)
                self._settings = {}

        @RPC.export
        def set_setting(self, key, value):
            _log.debug("Setting key: {} to value: {}".format(key, value))
            self._settings[key] = value
            self._store_settings()


        @RPC.export
        def get_setting(self, key):
            _log.debug('Retrieveing key: {}'.format(key))
            return self._settings.get(key, '')

        @Core.periodic(30)
        def publish_heartbeat(self):
            historian_present = False

#             base_topic = 'datalogger/log/listener/heartbeat'


            message = jsonapi.dumps({'Readings': "HI!!",
                                 'Units': 'string',
                                 'agentname': self.core.identity})
=======
>>>>>>> 310143f6c8209f6f1e05a2d018505597edc64c33
#             self.vip.pubsub.publish(peer='pubsub',
#                                     topic=base_topic,
#                                     message=[message])

            

            self.vip.rpc.call('platform.agent','publish_to_peers', topic='neighborhood/needs',
                          message=message)
        
 
 
        @Core.receiver('onstart')
        def starting(self, sender, **kwargs):
            print('***** Demo Agent is starting')
        
            self.vip.pubsub.subscribe('pubsub', 
                                  '', self.onmessage)
            print("SUBSCRIBED")

        def onmessage(self, peer, sender, bus, topic, headers, message):
            
            print("ON MESSAGE: {}".format(message))
            
            _log.debug("Topic: {topic}, Headers: {headers}, "
                             "Message: {message}".format(
                             topic=topic, headers=headers, message=message))
        
            '''
            Receive energy usage change message from another agent. If we have energy
            needs and there is now some available, use it.
            '''
            message = jsonapi.loads(message[0])        
            
        @Core.receiver('onstop')
        def stoping(self, sender, **kwargs):
            pass

    ListenerAgent.__name__ = 'ListenerAgent'
    return ListenerAgent(**kwargs)




def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(listener_agent,
                       description='Agent available to manage from a remote '
                                    + 'system.',
                       no_pub_sub_socket=True,
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass