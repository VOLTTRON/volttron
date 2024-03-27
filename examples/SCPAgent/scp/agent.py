# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

from enum import Enum, auto
import inspect
from json import JSONDecodeError
import logging
from pathlib import Path

from gevent import subprocess

from volttron.platform import jsonapi
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent.utils import vip_main, load_config


__version__ = "0.1"
logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger(inspect.getmodulename(__file__))


class WhichWayEnum(Enum):
    SENDING = auto()
    RECEIVING = auto()


class ScpAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(ScpAgent, self).__init__(**kwargs)
        config = load_config(config_path)
        self._remote_user = None
        self._ssh_id = None
        self.default_config = dict(
            ssh_id=config.get("ssh_id"),  # "~/.ssh/id_rsa",
            remote_user=config.get("remote_user")  # "osboxes@localhost"
        )
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure,
                                  actions=["NEW", "UPDATE"], pattern="config")
        self._subscribed = False

    def configure(self, config_name, action, contents):
        conf = {}
        conf.update(contents)
        self._ssh_id = conf.get("ssh_id")
        self._remote_user = conf.get('remote_user')

        if not self._subscribed:
            self.vip.pubsub.subscribe(peer="pubsub", prefix="transfer", callback=self.transfer_file)
            self._subscribed = True

    def transfer_file(self, peer, sender, bus, topic, headers, message):
        """
        Pubsub interface for transferring files.

        The interface requires message to be a dictionary like object
        or a json serializable string with the following required structure:

        {
            "direction": "SENDING"
            "remote_path": "/remote/path/file.txt",
            "local_path": "/local/path/file.txt"
        }

        The above direction must be either "SENDING" or "RECEIVING".  The path must be available
        on the host that is providing the content and will overwrite the data on the receiving
        side of the connection.

        """
        enabled = self.__check_configuration__()

        if not enabled:
            return False

        if isinstance(message, str):
            try:
                message = jsonapi.loads(message)
            except JSONDecodeError:
                _log.error(f"Invalid json passed through string interface")
                return

        direction = message.get("direction")
        remote_path = message.get("remote_path")
        local_path = message.get("local_path")

        enabled = True
        if not remote_path:
            enabled = False
            _log.error(f"remote_path not specified in message to pub sub")

        if not local_path:
            enabled = False
            _log.error(f"local_path not specified in message to pub sub")

        if direction not in WhichWayEnum.__members__:
            _log.error(f"which_way must be either SENDING or RECEIVING.")
            enabled = False

        if not enabled:
            return

        if direction == WhichWayEnum.SENDING.name:
            success = self.__handle_scp__(WhichWayEnum.SENDING, local_path, remote_path)
        else:
            success = self.__handle_scp__(WhichWayEnum.RECEIVING, remote_path, local_path)

        if not success:
            _log.error(f"Unable to send to/recieve scp files.")

    @RPC.export
    def trigger_download(self, remote_path, local_path):
        _log.debug('Triggering download')
        enabled = self.__check_configuration__()

        if not enabled:
            return False

        return self.__handle_scp__(WhichWayEnum.RECEIVING, remote_path, local_path)

    @RPC.export
    def trigger_upload(self, local_path, remote_path):
        _log.debug('Trigger upload')
        enabled = self.__check_configuration__()

        if not enabled:
            return False

        return self.__handle_scp__(WhichWayEnum.SENDING, local_path, remote_path)

    def __check_configuration__(self):
        enabled = True
        if self._ssh_id is None:
            _log.error("Configuration error, ssh_id is not set")
            enabled = False
        if self._remote_user is None:
            _log.error("Configuration error, invalid remote user configured")
            enabled = False
        return enabled

    def __handle_scp__(self, which_way: WhichWayEnum, from_arg, to_arg):
        cmd = ["scp", "-o", "LogLevel=VERBOSE",
               "-o", "PasswordAuthentication=no",
               "-o", "IdentitiesOnly=yes",
               "-o", "Compression=yes",
               "-i", self._ssh_id]

        if which_way == WhichWayEnum.SENDING:
            cmd.extend([f"{from_arg}", f"{self._remote_user}:{to_arg}"])
        else:
            cmd.extend([f"{self._remote_user}:{from_arg}", f"{to_arg}"])

        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        p.wait()
        _log.debug(p.stderr.read().decode('utf-8'))
        _log.debug(p.stdout.read().decode('utf-8'))
        _log.debug(f"Complete {which_way.name}")
        _log.debug(f"Return code: {p.returncode}")
        if p.returncode == 0:
            return True
        return False


if __name__ == '__main__':
    vip_main(ScpAgent, version=__version__)
