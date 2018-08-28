import os
import yaml
import requests

from volttron.platform import instance_setup, get_home
from volttron.platform.agent.utils import store_message_bus_config
from volttron.utils.rmq_mgmt import _load_rmq_config, get_users, delete_user, delete_vhost, delete_exchange
from volttron.utils.rmq_setup import stop_rabbit


HOME = os.environ.get('HOME')
VOLTTRON_INSTANCE_NAME = 'volttron_test'

rabbitmq_config = {
    'host': 'localhost',
    'certificate-data': {
        'country': 'US',
        'state': 'Washington',
        'location': 'Richland',
        'organization': 'PNNL',
        'organization-unit': 'VOLTTRON Team',
        'common-name': '{}_root_ca'.format(VOLTTRON_INSTANCE_NAME),
    },
    'virtual-host': 'volttron_test',
    'amqp-port': 5672,
    'amqp-port-ssl': 5671,
    'mgmt-port': 15672,
    'mgmt-port-ssl': 15671,
    'rmq-home': os.path.join(HOME, 'rabbitmq_server/rabbitmq_server-3.7.7')
}


def create_rmq_volttron_setup(ssl_auth=False):
    """
        Create RMQ volttron test setup:
            - Install config and rabbitmq_config.yml in VOLTTRON_HOME
            - Create virtual host, exchanges, certificates, and users

    :param ssl_auth: ssl authentication
    """
    rabbitmq_config['ssl'] = str(ssl_auth)
    vhome = get_home()
    instance_setup._install_config_file()
    vhome_config = os.path.join(vhome, 'rabbitmq_config.yml')

    if not os.path.isfile(vhome_config):
        with open(vhome_config, 'w') as yml_file:
            yaml.dump(rabbitmq_config, yml_file, default_flow_style=False)

    store_message_bus_config(message_bus='rmq',
                             instance_name=VOLTTRON_INSTANCE_NAME)

    instance_setup.setup_rabbitmq_volttron(type='single',
                                           verbose=False,
                                           prompt=False)


def cleanup_rmq_volttron_setup():
    """
        Clean-up RMQ volttron test setup:
            - The function is called when DEBUG = False
            - delete test users, exchanges, and virtual host
    """
    global config_opts
    _load_rmq_config()
    users_to_remove = get_users()
    users_to_remove.remove('guest')

    # Delete all the users using virtual host
    for user in users_to_remove:
        try:
            delete_user(user)
        except (AttributeError, requests.exceptions.HTTPError):
            pass

    try:
        delete_exchange(exchange='undeliverable',
                        vhost=rabbitmq_config['virtual-host'])
        delete_exchange(exchange='volttron',
                        vhost=rabbitmq_config['virtual-host'])
        delete_vhost(vhost=rabbitmq_config['virtual-host'])
        # stop_rabbit(rmq_home=rabbitmq_config['rmq-home'])
    except requests.exceptions.HTTPError:
        pass
