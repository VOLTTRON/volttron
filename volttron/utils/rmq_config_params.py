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

import os
import logging


try:
    import yaml
except ImportError:
    raise RuntimeError('PyYAML must be installed before running this script ')

from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent.utils import get_platform_instance_name

_log = logging.getLogger(__name__)


class RMQConfig(object):
    """
    Utility class to read/write RabbitMQ related configuration
    """

    def __init__(self):
        self.instance_name = get_platform_instance_name()
        # This is written durn the bootstrap phase of the rabbitmq installation
        # however for docker we don't write this at all so we need to
        # use the default location for this
        rmq_home_file = os.path.expanduser("~/.volttron_rmq_home")
        if os.path.isfile(rmq_home_file):
            with open(os.path.expanduser("~/.volttron_rmq_home")) as f:
                self.rabbitmq_server = f.read().strip()
        else:
            self.rabbitmq_server = os.path.expanduser("~/rabbitmq_server/rabbitmq_server-3.7.7/")

        assert os.path.isdir(self.rabbitmq_server), "Missing rabbitmq server directory{}".format(self.rabbitmq_server)
        self.crts = certs.Certs()
        self.volttron_home = get_home()
        self.volttron_rmq_config = os.path.join(self.volttron_home, 'rabbitmq_config.yml')
        self.default_pass = "default_passwd"
        self.config_opts = None
        try:
            self.load_rmq_config()
        except (IOError, yaml.YAMLError) as exc:
            self.config_opts = {}
        self._set_default_config()

    def _set_default_config(self):
        """
        init with default values
        :return:
        """
        self.config_opts.setdefault('host', "localhost")
        self.config_opts.setdefault("ssl", "true")
        self.config_opts.setdefault('amqp-port', 5672)
        self.config_opts.setdefault('amqp-port-ssl', 5671)
        self.config_opts.setdefault('mgmt-port', 15672)
        self.config_opts.setdefault('mgmt-port-ssl', 15671)
        self.config_opts.setdefault('virtual-host', 'volttron')
        self.config_opts.setdefault('reconnect-delay', 30)
        self.config_opts.setdefault('user', self.instance_name + '-admin')
        rmq_home = os.path.join(os.path.expanduser("~"),
                                "rabbitmq_server/rabbitmq_server-3.7.7")
        self.config_opts.setdefault("rmq-home", rmq_home)

    def load_rmq_config(self, volttron_home=None):
        """
        Load RabbitMQ config from VOLTTRON_HOME
        :param volttron_home: VOLTTRON_HOME path
        :return:
        """
        """Loads the config file if the path exists."""
        
        with open(self.volttron_rmq_config, 'r') as yaml_file:
            self.config_opts = yaml.safe_load(yaml_file)
            if self.config_opts.get('rmq-home'):
                self.config_opts['rmq-home'] = os.path.expanduser(
                    self.config_opts['rmq-home'])

    def write_rmq_config(self, volttron_home=None):
        """
        Write new config options into $VOLTTRON_HOME/rabbitmq_config.yml
        :param volttron_home: VOLTTRON_HOME path
        :return:
        """
        try:
            with open(self.volttron_rmq_config, 'w') as \
                    yaml_file:
                yaml.dump(self.config_opts, yaml_file, default_flow_style=False)
            # Explicitly give read access to group and others. RMQ user and
            # agents should be able to read this config file
            os.chmod(self.volttron_rmq_config, 0o744)
        except IOError as exc:
            _log.error("Error writing to rabbitmq_config.yml file. Please"
                       "check VOLTTRON_HOME".format(self.volttron_home))
        except yaml.YAMLError as exc:
            raise



    @property
    def hostname(self):
        return self.config_opts.get('host')

    @property
    def amqp_port(self):
        return self.config_opts.get('amqp-port', 5672)

    @property
    def amqp_port_ssl(self):
        return self.config_opts.get('amqp-port-ssl', 5671)

    @property
    def mgmt_port(self):
        return self.config_opts.get('mgmt-port', 15672)

    @property
    def mgmt_port_ssl(self):
        return self.config_opts.get('mgmt-port-ssl', 15671)

    @property
    def virtual_host(self):
        return self.config_opts.get('virtual-host')

    @property
    def admin_user(self):
        return self.config_opts.get('user')

    @property
    def admin_pwd(self):
        return self.config_opts.get('pass', self.default_pass)

    @property
    def rmq_home(self):
        return self.config_opts.get('rmq-home')

    @property
    def is_ssl(self):
        ssl_auth = self.config_opts.get('ssl', 'true')
        return ssl_auth in ('true', 'True', 'TRUE', True)

    @property
    def use_existing_certs(self):
        use_existing = self.config_opts.get('use-existing-certs')
        if use_existing is not None:
            return use_existing in ('true', 'True', 'TRUE', True)
        return use_existing

    @property
    def certificate_data(self):
        return self.config_opts.get('certificate-data')

    @property
    def local_user(self):
        return "guest"

    @property
    def local_password(self):
        return "guest"

    @property
    def node_name(self):
        return self.config_opts.get('node-name', 'rabbit')

    def reconnect_delay(self):
        return self.config_opts.get('reconnect-delay')

    @hostname.setter
    def hostname(self, host):
        self.config_opts['host'] = host

    @amqp_port.setter
    def amqp_port(self, port):
        self.config_opts['amqp-port'] = port

    @amqp_port_ssl.setter
    def amqp_port_ssl(self, port):
        self.config_opts['amqp-port-ssl'] = port

    @mgmt_port_ssl.setter
    def mgmt_port_ssl(self, port):
        self.config_opts['mgmt-port-ssl'] = port

    @mgmt_port.setter
    def mgmt_port(self, port):
        self.config_opts['mgmt-port'] = port

    @virtual_host.setter
    def virtual_host(self, vhost):
        self.config_opts['virtual-host'] = vhost

    @admin_user.setter
    def admin_user(self, user):
        self.config_opts['user'] = user

    @admin_pwd.setter
    def admin_pwd(self, pwd):
        self.config_opts['pass'] = pwd

    @rmq_home.setter
    def rmq_home(self, rhome):
        self.config_opts['rmq-home'] = rhome

    @is_ssl.setter
    def is_ssl(self, ssl_flag):
        self.config_opts['ssl'] = ssl_flag

    @certificate_data.setter
    def certificate_data(self, data):
        self.config_opts['certificate-data'] = data

    @node_name.setter
    def node_name(self, name):
        self.config_opts['node-name'] = name


