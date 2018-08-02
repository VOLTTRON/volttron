import pytest
import tempfile
import os
import shutil
import json
import socket

from pytest_rabbitmq.factories import process

from volttron.platform import certs
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
RABBIT_LOG= '/tmp/rmq/rmq_test'
RABBIT_MNESIA = RABBIT_PATH + 'mnesia'
RABBIT_PLUGINS = '/tmp/plugins'


def volttron_details():
    """Creates VOLTTRON home and sets instance name"""

    vh = tempfile.mkdtemp()
    if os.path.exists(vh):
        shutil.rmtree(vh)

    os.mkdir(vh)

    return {'vhome': vh, 'instance_name': INSTANCE_NAME}


def root_ca(v_details):
    """Creates root certificate authority (CA)"""

    cert_dir = os.path.join(v_details['vhome'], 'certificates')
    if not os.path.exists(cert_dir):
        os.mkdir(cert_dir)
        os.mkdir(os.path.join(cert_dir, 'certs'))
        os.mkdir(os.path.join(cert_dir, 'private'))

    return certs.Certs(cert_dir)


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


def create_ca(crts):
    """Creates a root ca cert using the Certs class"""
    defaults = dict(C='US',
                    ST='CA',
                    L='Oakland',
                    O='Acme',
                    OU='Division',
                    CN=DEFAULT_ROOT_CA_CN)
    crts.create_root_ca(**defaults)


def create_certs(crts):
    """
    Creates required certs. These include:
        - root CA (e.g. volttron-ca.crt)
        - RQM server certs
        - client cert
    :param crts:
    :return:
    """
    instance_ca_name = INSTANCE_NAME + '-instance-ca'

    create_ca(crts)

    crts.create_instance_ca(instance_ca_name)

    crts.create_ca_signed_cert(SERVER_NAME, type='server',
                               ca_name=instance_ca_name,
                               fqdn=HOST)

    # admin certificate - used for RMQ web api calls
    crts.create_ca_signed_cert('volttron1-admin', type='client',
                               ca_name=instance_ca_name)


@pytest.fixture(scope='session')
def rmq_fixture(request):
    """
    Writes rabbitmq.conf file for RMQ server and begins RMQ server.
    :param request:
    :return:
    """

    with open(RABBIT_PLUGINS, 'w') as f:
        f.write('[rabbitmq_auth_mechanism_ssl,rabbitmq_management].')

    environ = {
        'RABBITMQ_LOG_BASE': RABBIT_LOG,
        'RABBITMQ_MNESIA_BASE': RABBIT_MNESIA,
        'RABBITMQ_ENABLED_PLUGINS_FILE': RABBIT_PLUGINS,
        'RABBITMQ_NODENAME': NODE_NAME,
        'RABBITMQ_CONFIG_FILE': RMQ_CONF_FILE.replace('.conf', '')
    }

    v_details = volttron_details()

    instance_ca_path = os.path.join(v_details['vhome'], 'certificates/certs', INSTANCE_NAME + 'instance-ca.crt')
    server_cert_path = os.path.join(v_details['vhome'], 'certificates/certs', SERVER_NAME + '.crt')
    server_key_path = os.path.join(v_details['vhome'], 'certificates/private', SERVER_NAME + '.pem')

    rmq_conf = """loopback_users = none
listeners.ssl.default = 5671
ssl_options.cacertfile = {instance_ca}
ssl_options.certfile = {server_cert}
ssl_options.keyfile = {server_key}
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true
ssl_options.depth = 1
auth_mechanisms.1 = EXTERNAL
ssl_cert_login_from = common_name
ssl_options.versions.1 = tlsv1.2
ssl_options.versions.2 = tlsv1.1
ssl_options.versions.3 = tlsv1
log.file.level = debug
log.connection.level = debug
log.channel.level = debug
log.default.level = debug
management.listener.port = 15671
management.listener.ssl = true
management.listener.ssl_opts.cacertfile = {instance_ca}
management.listener.ssl_opts.certfile = {server_cert}
management.listener.ssl_opts.keyfile = {server_key}""".format(instance_ca=instance_ca_path,
                                                              server_cert=server_cert_path,
                                                              server_key=server_key_path)

    with open(RMQ_CONF_FILE, 'w') as conf:
        conf.write(rmq_conf)

    rmq_volttron_config(v_details)

    c = root_ca(v_details)
    create_certs(c)
    rmq = process.RabbitMqExecutor(RMQ_SERVER_LOC, HOST, AMQP_PORT, RMQ_CTL, environ)

    rmq.start()

    def cleanup_and_stop():
        rmq.stop()
        os.remove(RMQ_CONF_FILE)
        shutil.rmtree(v_details['vhome'])

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



