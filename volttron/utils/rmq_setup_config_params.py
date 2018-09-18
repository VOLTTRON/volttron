# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import os
import logging
try:
    import yaml
except ImportError:
    raise RuntimeError('PyYAML must be installed before running this script ')

from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent.utils import get_platform_instance_name

_log = logging.getLogger(os.path.basename(__file__))


class RMQSetupConfigParams(object):
    def __init__(self):
        self.local_user = "guest"
        self.local_password = "guest"
        self.instance_name = get_platform_instance_name(prompt=True)
        self.rabbitmq_server = 'rabbitmq_server-3.7.7'
        self.crts = certs.Certs()
        self.volttron_home = get_home()
        self.volttron_rmq_config = os.path.join(self.volttron_home, 'rabbitmq_config.yml')
        self.config_opts = self.load_rmq_config(self.volttron_home)
        self.default_pass = "default_passwd"

    def load_rmq_config(self, volttron_home=None):
        """
        Load RabbitMQ config from VOLTTRON_HOME
        :param volttron_home: VOLTTRON_HOME path
        :return:
        """
        """Loads the config file if the path exists."""
        if not self.volttron_home:
            self.volttron_home = get_home()
            self.volttron_rmq_config = os.path.join(self.volttron_home, 'rabbitmq_config.yml')
        try:
            with open(self.volttron_rmq_config, 'r') as yaml_file:
                self.config_opts = yaml.load(yaml_file)
        except IOError as exc:
            _log.error("Error opening {}. Please create a rabbitmq_config.yml "
                       "file in your volttron home. If you want to point to a "
                       "volttron home other than {} please set it as the "
                       "environment variable VOLTTRON_HOME".format(
                self.volttron_rmq_config, self.volttron_home))
            raise
        except yaml.YAMLError as exc:
            raise

    def write_rmq_config(self, volttron_home=None):
        """
        Write new config options into $VOLTTRON_HOME/rabbitmq_config.yml
        :param volttron_home:
        :return:
        """
        if not self.volttron_home:
            self.volttron_home = get_home()
            self.volttron_rmq_config = os.path.join(self.volttron_home, 'rabbitmq_config.yml')
        try:
            with open(self.volttron_rmq_config, 'w') as \
                    yaml_file:
                yaml.dump(self.config_opts, yaml_file, default_flow_style=False)
        except IOError as exc:
            _log.error("Error writing to rabbitmq_config.yml file. Please"
                       "check VOLTTRON_HOME".format(self.volttron_home))
        except yaml.YAMLError as exc:
            raise