import os
import yaml
import requests

from volttron.platform import instance_setup, get_home
from volttron.platform.agent.utils import store_message_bus_config
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttron.utils.rmq_setup import setup_rabbitmq_volttron, stop_rabbit

HOME = os.environ.get('HOME')
VOLTTRON_INSTANCE_NAME = 'volttron_test'

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
    'virtual-host': 'volttron_test',
    'amqp-port': 5672,
    'amqp-port-ssl': 5671,
    'mgmt-port': 15672,
    'mgmt-port-ssl': 15671,
    'rmq-home': os.path.join(HOME, 'rabbitmq_server/rabbitmq_server-3.7.7'),
    'reconnect-delay': 5
}


def create_rmq_volttron_setup(vhome=None, ssl_auth=False):
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

    rabbitmq_config['ssl'] = str(ssl_auth)
    vhome = get_home()
    instance_setup._update_config_file()
    vhome_config = os.path.join(vhome, 'rabbitmq_config.yml')

    if not os.path.isfile(vhome_config):
        with open(vhome_config, 'w') as yml_file:
            yaml.dump(rabbitmq_config, yml_file, default_flow_style=False)

    store_message_bus_config(message_bus='rmq',
                             instance_name=VOLTTRON_INSTANCE_NAME)

    setup_rabbitmq_volttron('single',
                            verbose=False,
                            prompt=False)


def cleanup_rmq_volttron_setup(vhome=None, ssl_auth=False):
    """
        Teardown rabbitmq at test end:
            - The function is called when DEBUG = False
            - delete test users, exchanges, and virtual host
            - user volttron_test-admin is deleted last in order to use its credentials to connect
            to the management interface
            - remove rabbitmq.conf
            - delete_exchange, delete_vhost, and stop_rabbit are controversial step, there maybe reason to keep
            the server running between tests
    """
    if vhome:
        os.environ['VOLTTRON_HOME'] = vhome
    rmq_mgmt = RabbitMQMgmt()
    users_to_remove = rmq_mgmt.get_users()
    users_to_remove.remove('guest')
    if ssl_auth:
        users_to_remove.remove('{}-admin'.format(VOLTTRON_INSTANCE_NAME))

    for user in users_to_remove:
        try:
            rmq_mgmt.delete_user(user)
        except (AttributeError, requests.exceptions.HTTPError):
            pass

    rmq_mgmt.delete_exchange(exchange='undeliverable',
                             vhost=rabbitmq_config['virtual-host'])
    rmq_mgmt.delete_exchange(exchange='volttron',
                             vhost=rabbitmq_config['virtual-host'])
    #rmq_mgmt.delete_vhost(vhost=rabbitmq_config['virtual-host'])

    if ssl_auth:
        rmq_mgmt.delete_user('volttron_test-admin')

    stop_rabbit(rmq_home=rabbitmq_config['rmq-home'])

    if ssl_auth:
        os.remove(os.path.join(rabbitmq_config['rmq-home'], 'etc/rabbitmq/rabbitmq.conf'))
