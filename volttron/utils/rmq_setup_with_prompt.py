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

"""
    Rabbitmq setup script to setup single instance, federation and shovel
"""

import argparse
import logging
import os
import subprocess
import time
from socket import getfqdn

import gevent
import wget

from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent.utils import load_platform_config, \
    store_message_bus_config, get_platform_instance_name
from volttron.platform.packaging import _create_ca
from volttron.utils.persistance import PersistentDict
from volttron.utils.prompt import prompt_response, y, n, y_or_n
from rmq_mgmt import is_ssl_connection, get_vhost, http_put_request, \
    set_policy, build_rmq_address, is_valid_amqp_port, \
    is_valid_mgmt_port, init_rabbitmq_setup, get_ssl_url_params, create_user, \
    set_user_permissions, set_parameter

#disable_warnings(exceptions.SecurityWarning)

_log = logging.getLogger(__name__)

config_opts = {}
default_pass = "default_passwd"
crts = certs.Certs()
instance_name = None
local_user = "guest"
local_password = "guest"
admin_user = None  # User to prompt for if we go the docker route
admin_password = None
rabbitmq_server = 'rabbitmq_server-3.7.7'

def _load_rmq_config(volttron_home=None):
    """
    Load RabbitMQ config from VOLTTRON_HOME
    :param volttron_home: VOLTTRON_HOME path
    :return:
    """
    """Loads the config file if the path exists."""
    global config_opts, volttron_rmq_config
    if not volttron_home:
        volttron_home = get_home()
    if not os.path.exists(volttron_home):
        os.makedirs(volttron_home)
    volttron_rmq_config = os.path.join(volttron_home, 'rabbitmq_config.json')
    config_opts = PersistentDict(filename=volttron_rmq_config, flag='c',
                                 format='json')


def _create_federation_setup():
    """
    Creates a RabbitMQ federation of multiple VOLTTRON instances.
    That means it creates upstream servers and sets "volttron" exchange to be "federated".

    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()

    federation = config_opts['federation-upstream']

    for name, address in federation.iteritems():

        property = dict(vhost='volttron',
                        component="federation-upstream",
                        name=name,
                        value={"uri":address})
        set_parameter('federation-upstream', name, property,
                      config_opts['virtual-host'])

    policy_name = 'volttron-federation'
    policy_value = {"pattern":"^volttron",
                    "definition": {"federation-upstream-set":"all"},
                    "priority":0,
                    "apply-to": "exchanges"}
    set_policy(policy_name, policy_value,
               config_opts['virtual-host'])


def _set_initial_rabbit_config(instance_name):
    """
    Build rabbitmq config for a single instance based on user input
    :param instance_name:
    :return:
    """
    global config_opts
    _load_rmq_config()

    rmq_home = config_opts.get("rmq-home")
    default_dir = os.path.join(os.path.expanduser("~"), "rabbitmq_server")
    if rmq_home:
        rmq_install_dir = os.path.dirname(rmq_home)
    else:
        rmq_install_dir = default_dir
    valid_dir = False
    while not valid_dir:
        prompt = 'Rabbitmq install directory:'
        rmq_install_dir = prompt_response(prompt, default=rmq_install_dir)
        if rmq_install_dir == default_dir and not os.path.exists(default_dir):
            os.mkdir(default_dir)
        valid_dir = os.access(rmq_install_dir, os.W_OK)
        if not valid_dir:
            print ("Invalid install directory. Directory should exist and "
                   "should have write access to user")

    rmq_home = os.path.join(rmq_install_dir, rabbitmq_server)
    if os.path.exists(rmq_home) and \
            os.path.exists(os.path.join(rmq_home, 'sbin/rabbitmq-server')):
        print("Given directory already contains {}. "
              "Skipping rabbitmq server install".format(rabbitmq_server))
        # if existing server attempt to stop
        stop_rabbit(rmq_home, quite=True)
        # mv any existing conf file to backup
        conf = os.path.join(rmq_home, "etc/rabbitmq/rabbitmq.conf")
        if os.path.exists(conf):
            os.rename(conf, os.path.join(rmq_home,
                                         "etc/rabbitmq/rabbitmq.conf_"+
                                         time.strftime("%Y%m%d-%H%M%S")
                                         ))
    else:
        filename = wget.download(
            "https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.7.7/rabbitmq-server-generic-unix-3.7.7.tar.xz",
            out=os.path.expanduser("~"))
        print("\nDownloaded rabbbitmq server")
        print("\nExtracting {} to {}".format(filename, rmq_install_dir))
        cmd = ["tar",
               "-xf",
               filename,
               "--directory="+rmq_install_dir]

        subprocess.check_call(cmd)

    config_opts['rmq-home'] = rmq_home


    # Get vhost
    vhost = config_opts.get('virtual-host', 'volttron')
    prompt = 'What is the name of the virtual ' \
             'host under which Rabbitmq VOLTTRON will be running?'
    new_vhost = prompt_response(prompt, default=vhost)
    config_opts['virtual-host'] = new_vhost
    prompt = prompt_response('\nDo you want SSL Authentication',
                             valid_answers=y_or_n,
                             default='Y')
    if prompt in y:
        config_opts['ssl'] = "true"
    else:
        config_opts['ssl'] = "false"
    config_opts['user'] = "guest"
    config_opts['pass'] = "guest"
    config_opts['host'] = 'localhost'

    prompt = prompt_response('\nUse default rabbitmq ports ',
                             valid_answers=y_or_n,
                             default='Y')
    if prompt in y:
        config_opts['amqp-port'] = '5672'
        config_opts['mgmt-port'] = '15672'
        config_opts['amqp-port-ssl'] = '5671'
        config_opts['mgmt-port-ssl'] = '15671'
        config_opts['rmq-address'] = build_rmq_address(ssl_auth=False,
                                                       config=config_opts)
        config_opts.sync()
    else:
        prompt = 'What is the instance port for the RabbitMQ address?'
        prompt_port(config_opts, 'amqp-port', 5672, prompt)

        prompt = 'What is the instance port for the RabbitMQ management plugin?'
        prompt_port(config_opts, 'mgmt-port', 15672, prompt)
        valid_port = False

        config_opts.sync()
        new_conf = """listeners.tcp.default = {}
        management.listener.port = {}""".format(config_opts['amqp-port'],
                                                config_opts['mgmt-port'])
        with open(os.path.join(config_opts['rmq-home'],
                               "etc/rabbitmq", "rabbitmq.conf"),
                  'w+') as r_conf:
            r_conf.write(new_conf)


    # Start rabbitmq server
    start_rabbit(config_opts['rmq-home'])

    #enable plugins
    cmd =[os.path.join(config_opts['rmq-home'], "sbin/rabbitmq-plugins"),
                       "enable", "rabbitmq_management",
                       "rabbitmq_federation",
                       "rabbitmq_federation_management",
                       "rabbitmq_shovel",
                       "rabbitmq_auth_mechanism_ssl"]
    subprocess.check_call(cmd)
    print("**enabled plugins")


def prompt_port(config_opts, config_key, default_port, prompt):
    # TODO - How to configure port other than 5671 for ssl - validate should
    # check if port is not 5672.
    port = config_opts.get(config_key, default_port)
    valid_port = False
    while not valid_port:
        port = prompt_response(prompt, default=port)
        if config_key == 'amqp-port':
            valid_port = is_valid_amqp_port(port)
        elif config_key == 'mgmt-port':
            valid_port = is_valid_mgmt_port(port)
        if not valid_port:
            print("Port is not valid")
    config_opts[config_key] = str(port)


def _get_upstream_servers():
    """
    Build AMQP/S URIs for upstream servers
    :return:
    """
    global config_opts, instance_name
    if not config_opts:
        _load_rmq_config()
    federation = config_opts.get('federation-upstream', dict())
    multi_platform = True
    ssl_params = get_ssl_url_params()
    prompt = 'How many upstream servers do you want to configure?'
    count = prompt_response(prompt, default=1)
    count = int(count)
    i = 0
    is_ssl = is_ssl_connection()
    for i in range(0, count):
        prompt = 'Name of the upstream server {}: '.format(i+1)
        default_name = 'upstream-' + str(i+1)
        name = prompt_response(prompt, default=default_name)
        prompt = 'Hostname of the upstream server: '
        host = prompt_response(prompt, default='localhost')
        prompt = 'Port of the upstream server: '
        port = prompt_response(prompt, default=5671)
        prompt = 'Virtual host of the upstream server: '
        vhost = prompt_response(prompt, default='volttron')
        if is_ssl:
            address = "amqps://{host}:{port}/{vhost}?" \
                  "{ssl_params}&server_name_indication={host}".format(
                    host=host, port=port, vhost=vhost, ssl_params=ssl_params)
        else:
            address = "amqp://{user}:{pwd}@{host}:{port}/{vhost}".format(
                user=instance_name, pwd=instance_name, host=host, port=port,
                vhost=vhost)
        federation[name] = address
    config_opts['federation-upstream'] = federation
    config_opts.sync()
    return multi_platform


def _get_shovel_settings():
    """
    Prompt user for shovel information
    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()

    platform_config = load_platform_config()
    try:
        instance_name = platform_config['instance-name'].strip('"')
        print(instance_name)
    except KeyError as exc:
        print("Unknown instance name. Please set instance-name in VOLTTRON_HOME/config")
        return

    shovels = config_opts.get('shovels', [])
    multi_platform = False
    prompt = prompt_response('\nDo you want a multi-platform shovel setup? ',
                                         valid_answers=y_or_n,
                                         default='N')
    if prompt in y:
        is_ssl = is_ssl_connection()
        multi_platform = True
        prompt = prompt_response('\nDo you want shovels for multi-platform RPC? ',
                                 valid_answers=y_or_n,
                                 default='N')
        if prompt in y:
            prompt = 'How many RPC shovels do you want to configure? You will need to create one for each remote platform'
            count = prompt_response(prompt, default=1)
            for i in range(0, int(count)):
                name = 'shovel-rpc-{}'.format(i + 1)
                print("Configuring RPC Shovel {}".format(i+1))
                prompt = 'Hostname of the destination instance: '
                host = prompt_response(prompt, default='localhost')
                prompt = 'Port of the upstream server: '
                port = prompt_response(prompt, default=5672)
                prompt = 'Virtual host of the destination server: '
                vhost = prompt_response(prompt, default='volttron')
                prompt = 'Username of the destination server: '
                user = prompt_response(prompt, default='volttron')
                prompt = 'Password of the destination server: '
                pwd = prompt_response(prompt, default='volttron')
                prompt = 'Instance name of the destination server: '
                platform = prompt_response(prompt, default='')
                if is_ssl:
                    ssl_params = get_ssl_url_params()
                    address = "amqps://{host}:{port}/{vhost}?" \
                    "{ssl_params}&server_name_indication={host}".format(
                        host=host, port=port, vhost=vhost, ssl_params=ssl_params)
                else:
                    address = "amqp://{0}:{1}@{2}:{3}/{4}".format(user, pwd, host, port, vhost)
                rpc_key = platform + '.*'
                shovels.append(dict(name=name, remote_address=address, topics=rpc_key))

        prompt = prompt_response('\nDo you want shovels for multi-platform PUBSUB? ',
                                 valid_answers=y_or_n,
                                 default='N')
        if prompt in y:
            prompt = 'How many remote instances do you want to publish topic? '
            count = prompt_response(prompt, default=1)
            for i in range(0, int(count)):
                print("Configuring Remote instance {}".format(i + 1))
                prompt = 'Hostname of the destination instance: '
                host = prompt_response(prompt, default='localhost')
                prompt = 'Port of the upstream server: '
                port = prompt_response(prompt, default=5672)
                prompt = 'Virtual host of the destination server: '
                vhost = prompt_response(prompt, default='volttron')
                prompt = 'Username of the destination server: '
                user = prompt_response(prompt, default='volttron')
                prompt = 'Password of the destination server: '
                pwd = prompt_response(prompt, default='volttron')
                if is_ssl:
                    ssl_params = get_ssl_url_params()
                    address = "amqps://{host}:{port}/{vhost}?" \
                              "{ssl_params}&server_name_indication={host}".format(
                        host=host, port=port, vhost=vhost, ssl_params=ssl_params)
                else:
                    address = "amqp://{user}:{pwd}@{host}:{port}/{vhost}".format(
                    user=user, pwd=pwd, host=host, port=port, vhost=vhost)
                prompt = 'List of PUBSUB topics to publish to this remote instance (comma seperated)'
                topics = prompt_response(prompt, default="")
                topics = topics.split(",")
                name = "shovel-pubsub-{host}".format(host=host)
                subkeys = []
                for topic in topics:
                    subkeys.append("__pubsub__.{0}.{1}.#".format(instance_name, topic))
                pubsub_key = "|".join(subkeys)
                shovels.append(dict(name=name, remote_address=address, topics=pubsub_key))
        config_opts['shovel'] = shovels
        config_opts.sync()

    return multi_platform


def _create_shovel_setup():
    """
    Create RabbitMQ shovel based on the information provided by user
    :return:
    """
    global instance_name
    if not config_opts:
        _load_rmq_config()
        return
    platform_config = load_platform_config()
    shovels = config_opts.get('shovel', [])
    print shovels
    src_uri = build_rmq_address()
    for shovel in shovels:
        name = shovel['name']
        dest_uri = shovel['remote_address']
        pubsub_keys = shovel['topics']
        property = dict(vhost=config_opts['virtual-host'],
                        component="shovel",
                        name=name,
                        value={"src-uri": src_uri,
                                "src-exchange":  "volttron",
                                "src-exchange-key": pubsub_keys,
                                "dest-uri": dest_uri,
                                "dest-exchange": "volttron"}
                            )
        print("shovel property: {}", property)
        set_parameter("shovel",
                      name,
                      property)


def wizard(type):
    """
    Setup VOLTTRON instance to run with RabbitMQ message bus.
    :param type:
            single - Setup to run as single instance
            federation - Setup to connect multiple VOLTTRON instances as a federation
            shovel - Setup shovels to forward local messages to remote instances
    :return:
    """
    global instance_name
    # First things first. Confirm VOLTTRON_HOME
    print('\nYour VOLTTRON_HOME currently set to: {}'.format(get_home()))
    prompt = '\nIs this the volttron instance you are attempting to ' \
             'configure rabbitmq for? '
    if not prompt_response(prompt, valid_answers=y_or_n, default='Y') in y:
        print(
            '\nPlease execute with VOLTRON_HOME=/your/path python '
            'volttron/utils/rmq_mgmt.py to  '
            'modify VOLTTRON_HOME.\n')
        return

    instance_name = get_platform_instance_name(prompt=True)
    # Store config this is checked at startup
    store_message_bus_config(message_bus='rmq', instance_name=instance_name)

    if type == 'single':
        # Get vhost from the user
        _set_initial_rabbit_config(instance_name)
        # Create local RabbitMQ setup
        response = init_rabbitmq_setup() #should be called after config
        # changes are written to disk.
        ssl_auth = config_opts.get('ssl', "true")
        if response and ssl_auth in ('true', 'True', 'TRUE'):
            _setup_for_ssl_auth(instance_name)
    elif type == 'federation':
        _load_rmq_config()
        # Create a federation setup
        federation_needed = _get_upstream_servers()
        if federation_needed:
            _create_federation_setup()
    elif type == 'shovel':
        _load_rmq_config()
        shovel_needed = _get_shovel_settings()
        if shovel_needed:
            _create_shovel_setup()
    else:
        print "Unknown option. Exiting...."


def _setup_for_ssl_auth(instance_name):
    """
    Utility method to create
    1. Root CA
    2. instance CA
    3. RabbitMQ server certificates (public and private)
    4. RabbitMQ config with SSL setting
    5. Admin user to connect to RabbitMQ management Web interface

    :param instance_name: Instance name
    :return:
    """
    global config_opts
    print('\nChecking for CA certificate\n')
    instance_ca_name, server_name, admin_client_name = \
        certs.Certs.get_cert_names(instance_name)

    host = config_opts.get('host', 'localhost')
    prompt = 'What is the fully qualified domain name of the system?'
    new_host = prompt_response(prompt, default=getfqdn())
    config_opts['host'] = new_host

    # prompt for host before creating certs as it is needed for server cert
    _create_certs(admin_client_name, instance_ca_name, server_name)

    # if all was well, create the rabbitmq.conf file for user to copy
    # /etc/rabbitmq and update VOLTTRON_HOME/rabbitmq_config.json
    new_conf = """listeners.ssl.default = 5671
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
management.listener.port = 15671
management.listener.ssl = true
management.listener.ssl_opts.cacertfile = {instance_ca}
management.listener.ssl_opts.certfile = {server_cert}
management.listener.ssl_opts.keyfile = {server_key}""".format(
        instance_ca=crts.cert_file(instance_ca_name),
        server_cert=crts.cert_file(server_name),
        server_key=crts.private_key_file(server_name)
    )
    with open(os.path.join(get_home(), "rabbitmq.conf"), 'w') as rconf:
        rconf.write(new_conf)

    # updated rabbitmq_config.json
    config_opts['user'] = admin_client_name
    config_opts['pass'] = ""
    config_opts['amqp-port-ssl'] = '5671'
    config_opts['mgmt-port-ssl'] = '15671'
    config_opts.sync()

    # Stop server, move new config file with ssl params, start server
    stop_rabbit(config_opts['rmq-home'])

    os.rename(os.path.join(get_home(), "rabbitmq.conf"),
              os.path.join(config_opts.get("rmq-home"),
                           "etc/rabbitmq/rabbitmq.conf"))
    start_rabbit(config_opts['rmq-home'])
    print("\n#######################"
          "\nSetup complete. A new admin user was created with user name: "
          "{} and password={}.\nYou could change this user's password by "
          "logging into https://{}:{}/"
          "\n#######################".format(config_opts['user'],
                                             default_pass, config_opts['host'],
                                             config_opts['mgmt-port-ssl']))


def stop_rabbit(rmq_home, quite=False):
    try:
        cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"),
               "stop"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        gevent.sleep(2)
        if not quite:
            print("**Stopped rmq server")
    except subprocess.CalledProcessError as e:
        if not quite:
            raise e


def start_rabbit(rmq_home):
    cmd = [os.path.join(rmq_home, "sbin/rabbitmq-server"),
           "-detached"]
    subprocess.check_call(cmd)
    gevent.sleep(4)
    print("**Started rmq server")


def _create_certs(client_cert_name, instance_ca_name, server_cert_name):
    """
    Utility method to create certificates
    :param client_cert_name:
    :param instance_ca_name:
    :param server_cert_name:
    :return:
    """
    global config_opts
    create_instance_ca = False
    # create ca cert in default dir if needed
    if crts.ca_exists():
        print('\n Found {}'.format(crts.cert_file(crts.root_ca_name)))
        r = prompt_response('\n Is this the root CA used to sign all volttron '
                            'instances\' CA in this setup:',
                            valid_answers=y_or_n, default='Y')
        if r in y:
            create_instance_ca = True
    else:
        r = prompt_response("Do you want to create a self-signed root CA "
                            "certificate that can sign all volttron instance "
                            "CA in your setup:", valid_answers=y_or_n,
                            default='N')
        if r in y:
            _create_ca(override=False)
            create_instance_ca = True
    instance_ca_path = None
    instance_ca_key = None
    if crts.cert_exists(instance_ca_name):
        r = prompt_response(
            '\n Found {}. Is this the instance CA signed by '
            'volttron root CA:'.format(crts.cert_file(instance_ca_name)),
            valid_answers=y_or_n, default='Y')
        if r in y:
            create_instance_ca = False
            instance_ca_path = crts.cert_file(instance_ca_name)
            instance_ca_key = crts.private_key_file(instance_ca_name)
    # create instance CA (intermediate CA) if root CA exists and instance cert
    # doesn't exist
    if create_instance_ca:
        crts.create_instance_ca(instance_ca_name)
    else:

        found = _verify_and_save_instance_ca(instance_ca_path, instance_ca_key)
        while not found:
            if instance_ca_path is not None or instance_ca_key is not None:
                print("\nInvalid instance CA certificate or instance CA "
                      "private key file")
            instance_ca_path = prompt_response('\n Enter path to intermediate '
                                               'CA certificate of this '
                                               'volttron instance:')
            instance_ca_key = prompt_response('\n Enter path to private key '
                                              'file for this instance CA:')
            found = _verify_and_save_instance_ca(instance_ca_path,
                                                 instance_ca_key)
            # get instance cert name
            filename = os.path.basename(instance_ca_path)
            instance_ca_name = os.path.splitext(filename)[0]
    crts.create_ca_signed_cert(server_cert_name, type='server',
                               ca_name=instance_ca_name,
                               fqdn=config_opts.get('host'))
    # permissions = dict(configure=".*", read=".*", write=".*")
    # set_user_permissions(permissions, server_cert_name)
    crts.create_ca_signed_cert(client_cert_name, type='client',
                               ca_name=instance_ca_name)
    create_user(client_cert_name, ssl_auth=False)
    permissions = dict(configure=".*", read=".*", write=".*")
    set_user_permissions(permissions, client_cert_name, ssl_auth=False)


def _verify_and_save_instance_ca(instance_ca_path, instance_ca_key):
    """
    Save instance CA in VOLTTRON HOME
    :param instance_ca_path:
    :param instance_ca_key:
    :return:
    """
    found = False
    if instance_ca_path and os.path.exists(instance_ca_path) and \
            instance_ca_key and os.path.exists(instance_ca_key):
        found = True
        # TODO: check content of file
        # openssl crl2pkcs7 -nocrl -certfile volttron2-ca.crt | openssl pkcs7 -print_certs  -noout
        # this should list subject, issuer of both root CA and
        # intermediate CA
        crts.save_cert(instance_ca_path)
        crts.save_key(instance_ca_key)
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('type',
                        help='Instance type: single, federation or shovel')
    args = parser.parse_args()
    type = args.type
    try:
        wizard(type)
    except KeyboardInterrupt:
        print "Exiting setup process"

