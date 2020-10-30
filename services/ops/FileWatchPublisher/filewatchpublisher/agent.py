# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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
#}}}

import gevent
import logging
import os.path
import sys

from datetime import datetime
from volttron.platform.agent.utils import watch_file_with_fullpath
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.6'


def file_watch_publisher(config_path, **kwargs):
    """
    Load the FileWatchPublisher agent configuration and returns and instance
    of the agent created using that configuration.
    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: FileWatchPublisher agent instance
    :rtype: FileWatchPublisher agent
    """
    config = utils.load_config(config_path)
    return FileWatchPublisher(config, **kwargs)


class FileWatchPublisher(Agent):
    """
    Monitors files from configuration for changes and publishes added lines on corresponding topics.
    Ignores if a file does not exist and move to next file in configuration with an error message.
    Exists if all files does not exist.
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
        items = config.get("files")
        assert isinstance(items, list)
        self.file_topic = {}
        self.file_end_position = {}
        for item in self.config.get("files"):
            file = item["file"]
            self.file_topic[file] = item["topic"]
            if os.path.isfile(file):
                with open(file, 'r') as f:
                    self.file_end_position[file] = self.get_end_position(f)
            else:
                _log.error("File " + file + " does not exists. Ignoring this file.")
                items.remove(item)
        self.files_to_watch = items

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        _log.info("Starting "+self.__class__.__name__+" agent")
        if len(self.files_to_watch) == 0:
            _log.error("No file to watch and publish. Stopping "+self.__class__.__name__+" agent.")
            gevent.spawn_later(3, self.core.stop)
        else:
            for item in self.files_to_watch:
                file = item["file"]
                self.core.spawn(watch_file_with_fullpath, file, self.read_file)

    def read_file(self, file):
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
        self.vip.pubsub.publish(peer="pubsub", topic=topic, message=message)

    def get_end_position(self, f):
        f.seek(0, 2)
        return f.tell()


def main(argv=sys.argv):
    """
    Main method called by the platform.
    """
    utils.vip_main(file_watch_publisher, identity='platform.filewatchpublisher', version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
