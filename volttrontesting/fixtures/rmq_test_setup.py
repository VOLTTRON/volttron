import logging
import os
import shutil

import yaml

from volttron.platform import instance_setup, get_home
from volttron.platform.agent.utils import store_message_bus_config
from volttron.utils.rmq_setup import setup_rabbitmq_volttron
from volttrontesting.utils.utils import get_hostname_and_random_port

HOME = os.environ.get('HOME')
_log = logging.getLogger(__name__)


class RabbitTestConfig(object):
    def __init__(self):
        # Provides defaults for rabbitmq configuration file.
        self.rabbitmq_config = {
            'host': 'localhost',
            'certificate-data': {
                'country': 'US',
                'state': 'test-state',
                'location': 'test-location',
                'organization': 'test-organization',
                'organization-unit': 'test-team',
                'common-name': 'volttron_test_root_ca',
            },
            'virtual-host': 'volttron_test',
            'amqp-port': 5672,
            'amqp-port-ssl': 5671,
            'mgmt-port': 15672,
            'mgmt-port-ssl': 15671,
            # This is overwritten in the class below during
            # the create_rmq_volttron_setup function, but is
            # left here for completeness of the configuration.
            'rmq-home': '~/rabbitmq_server-3.7.7',
            'reconnect-delay': 5
        }

        self._instance_name = 'volttron_test'
        self._rmq_conf_file = None
        self._rmq_env_file = None

    @property
    def rmq_conf_file(self):
        return self._rmq_conf_file

    @rmq_conf_file.setter
    def rmq_conf_file(self, value):
        self._rmq_conf_file = value

    @property
    def rmq_env_file(self):
        return self._rmq_env_file

    @rmq_env_file.setter
    def rmq_env_file(self, value):
        self._rmq_env_file = value

    @property
    def common_name(self):
        return self.rabbitmq_config['certificate-data']['common-name']

    @property
    def instance_name(self):
        return self._instance_name

    @instance_name.setter
    def instance_name(self, value):
        self._instance_name = value
        self.rabbitmq_config['certificate-data']['common-name'] = '{}_root_ca'.format(self._instance_name)

    @property
    def node_name(self):
        return self.rabbitmq_config['node-name']

    @node_name.setter
    def node_name(self, value):
        self.rabbitmq_config['node-name'] = value

    @property
    def rmq_home(self):
        return self.rabbitmq_config['rmq-home']

    @rmq_home.setter
    def rmq_home(self, value):
        self.rabbitmq_config['rmq-home'] = value

    @property
    def rmq_port(self):
        return self.rabbitmq_config['amqp-port']

    @property
    def rmq_port_ssl(self):
        return self.rabbitmq_config['amqp-port-ssl']

    @property
    def virtual_host(self):
        return self.rabbitmq_config['virtual-host']

    def update_ports(self, amqp_port=None, amqp_port_ssl=None, mgmt_port=None, mgmt_port_ssl=None):
        if amqp_port:
            self.rabbitmq_config['amqp-port'] = amqp_port

        if amqp_port_ssl:
            self.rabbitmq_config['amqp-port-ssl'] = amqp_port_ssl

        if mgmt_port:
            self.rabbitmq_config['mgmt-port'] = mgmt_port

        if mgmt_port_ssl:
            self.rabbitmq_config['mgmt-port-ssl'] = mgmt_port_ssl


def create_rmq_volttron_setup(vhome=None, ssl_auth=False, env=None,
                              instance_name=None, secure_agent_users=False) -> RabbitTestConfig:
    """
        Set-up rabbitmq broker for volttron testing:
            - Install config and rabbitmq_config.yml in VOLTTRON_HOME
            - Create virtual host, exchanges, certificates, and users
            - Start rabbitmq server

    :param vhome: volttron home directory, if None, use default from environment
    :param ssl_auth: ssl authentication, if true, all users of message queue must authenticate
    :param instance_name: the canonical name for the instance being setup.s
    """
    if vhome:
        os.environ['VOLTTRON_HOME'] = vhome
    else:
        vhome = get_home()

    if secure_agent_users:
        os.umask(0o007)

    # Build default config file object, which we will then update to fit the
    # current context the code is running in.
    rabbit_config_obj = RabbitTestConfig()

    # for docker this will be setup so we can always use this for the home
    if os.environ.get('RMQ_HOME'):
        rabbit_config_obj.rmq_home = os.environ.get('RMQ_HOME')
    else:
        rmq_home_env_file = os.path.expanduser("~/.volttron_rmq_home")
        if not os.path.isfile(rmq_home_env_file):
            raise ValueError("Rabbitmq home dir can't be found please\n run bootstrap.py --rabbitmq")

        with open(rmq_home_env_file, 'r') as f:
            rabbit_config_obj.rmq_home = f.read().strip()

        os.environ['RMQ_HOME'] = rabbit_config_obj.rmq_home

    # instance name is the basename of the volttron home now.
    rabbit_config_obj.instance_name = instance_name
    rabbit_config_obj.node_name = os.path.basename(vhome)

    os.mkdir(os.path.join(vhome, "rmq_node_data"))

    rabbit_config_obj.rmq_conf_file = os.path.join(vhome, "rmq_node_data", rabbit_config_obj.node_name + "-rmq.conf")
    rabbit_config_obj.rmq_env_file = os.path.join(vhome, "rmq_node_data", rabbit_config_obj.node_name + "-rmq-env.conf")

    env['RABBITMQ_CONF_ENV_FILE'] = rabbit_config_obj.rmq_env_file

    # Create rabbitmq config for test
    rabbit_config_obj.rabbitmq_config['ssl'] = str(ssl_auth)
    host, rabbit_config_obj.rabbitmq_config['amqp-port'] = get_hostname_and_random_port()
    host, rabbit_config_obj.rabbitmq_config['amqp-port-ssl'] = get_hostname_and_random_port()
    host, rabbit_config_obj.rabbitmq_config['mgmt-port'] = get_hostname_and_random_port(10000, 20000)
    host, rabbit_config_obj.rabbitmq_config['mgmt-port-ssl'] = get_hostname_and_random_port(10000, 20000)
    rabbit_config_obj.rabbitmq_config['host'] = host
    rabbit_config_obj.rabbitmq_config['certificate-data']['common-name'] = '{}_root_ca'.format(rabbit_config_obj.instance_name)

    from pprint import pprint
    print("RMQ Node Name: {} env: ".format(rabbit_config_obj.node_name))
    pprint(env)

    # This is updating the volttron configuration file not the rabbitmq config file.
    instance_setup._update_config_file(instance_name=rabbit_config_obj.instance_name)
    vhome_config = os.path.join(vhome, 'rabbitmq_config.yml')

    if not os.path.isfile(vhome_config):
        with open(vhome_config, 'w') as yml_file:
            yaml.dump(rabbit_config_obj.rabbitmq_config, yml_file, default_flow_style=False)
        os.chmod(vhome_config, 0o744)

    store_message_bus_config(message_bus='rmq',
                             instance_name=rabbit_config_obj.instance_name)
    setup_rabbitmq_volttron('single',
                            verbose=False,
                            prompt=False,
                            instance_name=rabbit_config_obj.instance_name,
                            rmq_conf_file=rabbit_config_obj.rmq_conf_file,
                            env=env)

    return rabbit_config_obj

