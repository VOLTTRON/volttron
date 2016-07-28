# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
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

import datetime
import sys
import logging

from gevent.fileobject import FileObject
from volttron.platform.agent.utils import watch_file
from volttron.platform.messaging.health import STATUS_BAD, STATUS_GOOD, Status
from volttron.platform.vip.agent import Agent, Core, PubSub, RPC
from volttron.platform.messaging import (headers as headers_mod, topics)
from volttron.platform.agent import utils
from volttron.platform.messaging.utils import normtopic

from dateutil.parser import parse

import io


utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = "0.1"


class SyslogAgent(Agent):
    """
    The `SyslogAgent` is a agent that publishes /var/log/syslog content
    on message bus whenever there is change on that file.
    """

    def __init__(self, syslog_file_path, syslog_topic):
        """ Configures the `SyslogAgent`

        @param syslog_file_path: path to the syslog file.
        @syslog_topic: topic to publish syslog message on.
        """
        super(SyslogAgent, self).__init__(identity='syslog')
        self.syslog_file_path = syslog_file_path
        self.syslog_topic = syslog_topic
                
        with open(self.syslog_file_path, 'r') as f:
            self.prev_end_position = self.get_end_position(f)
            
    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        _log.info("Starting Syslog agent")
        self.core.spawn(watch_file, self.syslog_file_path, self.read_syslog_file)
        
    def read_syslog_file(self):
        _log.debug('loading syslog file %s', self.syslog_file_path)
        with open(self.syslog_file_path, 'r') as f:    
            f.seek(self.prev_end_position)
            for line in f:
                self.publish_syslog(line.strip())
            self.prev_end_position = self.get_end_position(f)
        
    def publish_syslog(self, line):
        _log.debug('publishing syslog line {}'.format(line))
        message = {'timestamp':line[:15],
                    'line': line[15:].strip()}
        _log.debug(message)
        self.vip.pubsub.publish(peer="pubsub", topic=self.syslog_topic,
                                message=message)

    def get_end_position(self, f):
        f.seek(0,2)
        return f.tell()

def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(SyslogAgent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
