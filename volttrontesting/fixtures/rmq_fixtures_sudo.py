import pytest
import tempfile
import os
import shutil
import json
import socket
import subprocess
import time

from volttron.utils.rmq_mgmt import create_vhost, create_exchange, get_users, delete_user, get_user_permissions, \
                                    delete_vhost

ROOT_CA_NAME = 'volttron-root-ca'
DEFAULT_ROOT_CA_CN = '{} {}'.format(socket.gethostname(), ROOT_CA_NAME)
VIRTUAL_HOST = 'volttron'
SERVER_NAME = 'volttron1-server'
INSTANCE_NAME = 'volttron1'
RMQ_SERVER_LOC = '/usr/lib/rabbitmq/bin/rabbitmq-server'
RMQ_CTL = '/usr/lib/rabbitmq/bin/rabbitmqctl'
HOST = 'localhost'
AMQP_PORT = 5671
MGMT_PORT = 15671
RMQ_CONF_FILE = os.path.join(os.path.expanduser('~'), 'rabbitmq.conf')
NODE_NAME = 'rabbitmq-test-{0}'.format(str(AMQP_PORT))
RABBIT_PATH = os.path.join(tempfile.gettempdir(), 'rabbitmq.{0}/'.format(AMQP_PORT))
RABBIT_LOG = '/tmp/rmq/rmq_test'
RABBIT_MNESIA = RABBIT_PATH + 'mnesia'
RABBIT_PLUGINS = '/tmp/plugins'


def volttron_details():
    """Creates VOLTTRON home and sets instance name"""

    vh = tempfile.mkdtemp()
    if os.path.exists(vh):
        shutil.rmtree(vh)

    os.mkdir(vh)

    return {'vhome': vh, 'instance_name': INSTANCE_NAME}


def rmq_volttron_config(v_details):
    """Writes to rabbitmq_config.json file in VOLTTRON home"""

    vhome = v_details['vhome']
    instance_name = v_details['instance_name']

    rmq_conf = {"instance-name": instance_name,
                "user": "guest",
                "pass": "guest",
                "host": socket.gethostname(),
                "mgmt-port": MGMT_PORT,
                "amqp-port": AMQP_PORT,
                "ssl": True,
                "virtual-host": VIRTUAL_HOST}

    with open(os.path.join(vhome, 'rabbitmq_config.json'), 'w') as conf_file:
        json.dump(rmq_conf, conf_file)

    config = """[volttron]
message-bus = rmq
instance-name = {}""".format(instance_name)

    with open(os.path.join(vhome, 'config'), 'w') as c:
        c.write(config)


@pytest.fixture(scope='session')
def rmq_fixture(request):
    """
    Writes rabbitmq.conf file for RMQ server and begins RMQ server.
    :param request:
    :return:
    """

    v_details = volttron_details()

    rmq_volttron_config(v_details)

    sudo_passwd = os.environ.get('SUDO_PASSWD', None)

    assert sudo_passwd is not None

    cmd = 'echo {sudo_passwd} | sudo {rmq_server_loc}'.format(sudo_passwd=sudo_passwd,
                                                              rmq_server_loc=RMQ_SERVER_LOC)

    p = subprocess.Popen(cmd, shell=True)

    time.sleep(15)  # Wait for server to start up

    def cleanup_and_stop():
        p.kill()

    request.addfinalizer(cleanup_and_stop)


@pytest.fixture(scope='session')
def setup_vhost_rmq_already_running(request, rmq_fixture):
    """
    Responsible for creating and eventually deleting virtual host
    and exchange used for RMQ testing.
    :param request:
    :param rmq_fixture:
    :return:
    """

    vhost = VIRTUAL_HOST
    # Create a new "volttron" vhost
    response = create_vhost(vhost, ssl_auth=True)
    exchange = 'volttron'
    alternate_exchange = 'undeliverable'
    # Create a new "volttron" exchange. Set up alternate exchange to capture
    # all unroutable messages
    properties = dict(durable=True, type='topic',
                      arguments={"alternate-exchange": alternate_exchange})
    create_exchange(exchange, properties=properties, vhost=vhost, ssl_auth=True)

    # Create alternate exchange to capture all unroutable messages.
    # Note: Pubsub messages with no subscribers are also captured which is
    # unavoidable with this approach
    properties = dict(durable=True, type='fanout')
    create_exchange(alternate_exchange, properties=properties, vhost=vhost,
                    ssl_auth=True)

    def cleanup_rmq_volttron_test_setup():
        try:
            users = get_users(ssl_auth=True)
            users.remove('guest')
            users_to_remove = []
            for user in users:
                perm = get_user_permissions(user, vhost, ssl_auth=True)
                if perm:
                    users_to_remove.append(user)
            print("Users to remove: {}".format(users_to_remove))
            # Delete all the users using virtual host
            for user in users_to_remove:
                delete_user(user)
            delete_vhost('volttron')
        except KeyError as e:
            return

    request.addfinalizer(cleanup_rmq_volttron_test_setup)



