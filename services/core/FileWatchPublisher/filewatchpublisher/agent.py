# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

#}}}

import logging
import sys

from datetime import datetime
from volttron.platform.agent.utils import watch_file_with_fullpath
from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.agent import utils


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.6'


def file_watch_publisher(config_path, **kwargs):
    """Load the FileWatchPublisher agent configuration and returns and instance
    of the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: FileWatchPublisher agent instance
    :rtype: FileWatchPublisher agent
    """
    config = utils.load_config(config_path)
    return FileWatchPublisher(config, **kwargs)


class FileWatchPublisher(Agent):
    """Monitors files for changes and publishes added lines
        on corresponding topics.

    :param config: Configuration dict
    :type config: dict

    Example configuration:

    .. code-block:: python

        {
	        "publish_file": [
                {
                    "file": "/var/log/syslog",
                    "topic": "platform/syslog",
                },
                {
                    "file": "/home/volttron/tempfile.txt",
                    "topic": "temp/filepublisher",
                }
	        ]
        }
    """
    def __init__(self, config, **kwargs):
        super(FileWatchPublisher, self).__init__(**kwargs)
        self.config = config
        self.file_topic = {}
        self.file_end_position = {}
        for item in self.config:
            file =  item["file"]
            self.file_topic[file] = item["topic"]
            with open(file, 'r') as f:
                self.file_end_position[file] = self.get_end_position(f)

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        _log.info("Starting "+self.__class__.__name__+" agent")
        for item in self.config:
            file = item["file"]
            self.core.spawn(watch_file_with_fullpath, file, self.read_file)

    def read_file(self,file):
        _log.debug('loading file %s', file)
        with open(file, 'r') as f:
            f.seek(self.file_end_position[file])
            for line in f:
                self.publish_file(line.strip(),self.file_topic[file])
            self.file_end_position[file] = self.get_end_position(f)

    def publish_file(self, line, topic):
        message = {'timestamp':  datetime.utcnow().isoformat() + 'Z',
                   'line': line}
        _log.debug('publishing message {} on topic {}'.format(message, topic))
        self.vip.pubsub.publish(peer="pubsub", topic=topic,
                                message=message)

    def get_end_position(self, f):
        f.seek(0,2)
        return f.tell()


def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(file_watch_publisher, identity='platform.filewatchpublisher')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
