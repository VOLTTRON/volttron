import logging
import os
import shutil

import yaml
import requests

from volttron.platform import instance_setup, get_home
from volttron.platform.agent.utils import store_message_bus_config
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttron.utils.rmq_setup import setup_rabbitmq_volttron, stop_rabbit, start_rabbit
from volttrontesting.utils.utils import get_hostname_and_random_port

HOME = os.environ.get('HOME')
VOLTTRON_INSTANCE_NAME = 'volttron_test'
_log = logging.getLogger(__name__)

rabbitmq_config = {
    'host': 'localhost',
    'certificate-data': {
        'country': 'US',
        'state': 'test-state',
        'location': 'test-location',
        'organization': 'test-organization',
        'organization-unit': 'test-team',
        'common-name': '{}_root_ca'.format(VOLTTRON_INSTANCE_NAME),
    },
    'virtual-host': VOLTTRON_INSTANCE_NAME,
    'amqp-port': 5672,
    'amqp-port-ssl': 5671,
    'mgmt-port': 15672,
    'mgmt-port-ssl': 15671,
    'rmq-home': '/home/vdev/multi_node_rmq/rabbitmq_server-3.7.7',
    'reconnect-delay': 5
}


def create_rmq_volttron_setup(instance_name, vhome=None, ssl_auth=False):
    """
        Set-up rabbitmq broker for volttron testing:
            - Install config and rabbitmq_config.yml in VOLTTRON_HOME
            - Create virtual host, exchanges, certificates, and users
            - Start rabbitmq server

    :param vhome: volttron home directory, if None, use default from environment
    :param ssl_auth: ssl authentication, if true, all users of message queue must authenticate
    """
    if vhome:
        os.environ['VOLTTRON_HOME'] = vhome
    else:
        vhome = get_home()

    # Create rabbitmq config for test
    start_rabbit(rabbitmq_config['rmq-home'])  # so current ports in use and get_rand_port will not return ports in use
    rabbitmq_config['ssl'] = str(ssl_auth)

    host, rabbitmq_config['amqp-port'] = get_hostname_and_random_port()
    host, rabbitmq_config['amqp-port-ssl'] = get_hostname_and_random_port()
    host, rabbitmq_config['mgmt-port'] = get_hostname_and_random_port(10000, 20000)
    host, rabbitmq_config['mgmt-port-ssl'] = get_hostname_and_random_port(10000, 20000)
    rabbitmq_config['node-name'] = os.path.basename(vhome)
    rabbitmq_config['host'] = host
    rabbitmq_config['certificate-data']['common-name'] = '{}_root_ca'.format(instance_name)
    with open(os.path.expanduser("~/.volttron_rmq_home"), 'r') as f:
        rabbitmq_config['rmq-home'] = f.read().strip()


    instance_setup._update_config_file()
    vhome_config = os.path.join(vhome, 'rabbitmq_config.yml')

    if not os.path.isfile(vhome_config):
        with open(vhome_config, 'w') as yml_file:
            yaml.dump(rabbitmq_config, yml_file, default_flow_style=False)

    store_message_bus_config(message_bus='rmq',
                             instance_name=VOLTTRON_INSTANCE_NAME)
    setup_rabbitmq_volttron('single',
                            verbose=False,
                            prompt=False,
                            instance_name=VOLTTRON_INSTANCE_NAME,
                            rmq_conf_file=os.path.join(vhome, rabbitmq_config['node-name'] + "-rmq.conf"),
                            rmq_env_file=os.path.join(vhome, rabbitmq_config['node-name'] + "-rmq-env.conf"))



