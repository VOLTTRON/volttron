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
from volttron.platform.packaging import create_ca
from volttron.utils.persistance import PersistentDict
from volttron.utils.prompt import prompt_response, y, n, y_or_n
from volttron.platform.certs import ROOT_CA_NAME
from rmq_mgmt import is_ssl_connection, get_vhost, http_put_request, \
    set_policy, build_rmq_address, is_valid_amqp_port, \
    is_valid_mgmt_port, init_rabbitmq_setup, get_ssl_url_params, create_user, \
    set_user_permissions, set_parameter

try:
    import yaml
except ImportError:
    raise RuntimeError('PyYAML must be installed before running this script ')

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(os.path.basename(__file__))


config_opts = {}
default_pass = "default_passwd"
crts = certs.Certs()
instance_name = None
local_user = "guest"
local_password = "guest"
admin_user = None  # User to prompt for if we go the docker route
admin_password = None
rabbitmq_server = 'rabbitmq_server-3.7.7'
volttron_home = get_home()
volttron_rmq_config = os.path.join(volttron_home, 'rabbitmq_config.yml')


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
    try:
        with open(volttron_rmq_config, 'r') as yaml_file:
            config_opts = yaml.load(yaml_file)
    except IOError as exc:
        _log.error("Error opening {}. Please create a rabbitmq_config.yml " \
              "file in your volttron home. If you want to point to a volttron " \
              "home other than {} please set it as the environment variable " \
              "VOLTTRON_HOME".format(volttron_rmq_config, volttron_home))
        return exc
    except yaml.YAMLError as exc:
        return exc


def _start_rabbitmq_without_ssl():
    """
    Check if basic rabbitmq configuration is available. Start rabbitmq in
    non ssl mode so that we can login as guest to create volttron users,
    exchanges, and vhost.
    :return:
    """
    global config_opts, volttron_home, volttron_rmq_config
    if not volttron_home:
        volttron_home = get_home()

    rmq_home = config_opts.get("rmq-home")
    if not rmq_home:
        rmq_home = os.path.join(os.path.expanduser("~"), "rabbitmq_server/rabbitmq_server-3.7.7")
        if os.path.exists(rmq_home):
            config_opts.setdefault("rmq-home", rmq_home)
        else:
            raise ValueError("Missing Key in RabbitMQ config. RabbitMQ is not "
                     "installed "
                  "in default path: \n"
                  "~/rabbitmq_server/rabbitmq_server-3.7.7 \n"
                  "Set the correct RabbitMQ installation path")
    else:
        if not os.path.exists(rmq_home) or not os.path.exists(os.path.join(
                rmq_home, 'sbin/rabbitmq-server')):
            raise ValueError("Invalid rmq-home value ({}). Please fix rmq-home "
                             "in {} and rerun this script".format(
                                rmq_home, volttron_rmq_config))


    # Check if basic configuration is available in the config file, if not set default.
    config_opts.setdefault('host',"localhost")
    config_opts.setdefault("ssl", "true")
    config_opts.setdefault('amqp-port', 5672)
    config_opts.setdefault('amqp-port-ssl', 5671)
    config_opts.setdefault('mgmt-port', 15672)
    config_opts.setdefault('mgmt-port-ssl', 15671)
    config_opts.setdefault('virtual-host', 'volttron')
    config_opts.setdefault('user', local_user)
    config_opts.setdefault('pass', local_password)
    with open(volttron_rmq_config, 'w') as \
            yaml_file:
        yaml.dump(config_opts, yaml_file, default_flow_style=False)

    #  attempt to stop
    stop_rabbit(rmq_home, quite=True)
    # mv any existing conf file to backup
    conf = os.path.join(rmq_home, "etc/rabbitmq/rabbitmq.conf")
    if os.path.exists(conf):
        os.rename(conf, os.path.join(rmq_home,
                                     "etc/rabbitmq/rabbitmq.conf_" +
                                     time.strftime("%Y%m%d-%H%M%S")
                                     ))

    if config_opts['amqp-port'] != 5672 and config_opts['mgmt-port'] != 15672:
        # If ports if non ssl ports are not default write a rabbitmq.conf before
        # restarting
        new_conf = """listeners.tcp.default = 5672
            management.listener.port = 15672"""
        with open(os.path.join(config_opts['rmq-home'],
                               "etc/rabbitmq", "rabbitmq.conf"),
                  'w+') as r_conf:
            r_conf.write(new_conf)

    # Start rabbitmq server
    _log.info("Starting rabbitmq server")
    start_rabbit(config_opts['rmq-home'])



def _create_federation_setup():
    """
    Creates a RabbitMQ federation of multiple VOLTTRON instances based on rabbitmq config.
        - Builds AMQP/S address for each upstream server
        - Creates upstream servers
        - Adds policy to make "volttron" exchange "federated".

    :return:
    """
    global instance_name, config_opts
    if not config_opts:
        _load_rmq_config()

    federation = config_opts.get('federation-upstream')
    if federation:
        is_ssl = is_ssl_connection()
        if is_ssl:
            ssl_params = get_ssl_url_params()

        for upstream in federation:
            try:
                _log.debug("Upstream Server: {host} ".format(upstream['host']))
                name = "upstream-{host}".format(host=upstream['host'])
                if is_ssl:
                    address = "amqps://{host}:{port}/{vhost}?" \
                              "{ssl_params}&server_name_indication={host}".format(
                                host=upstream['host'],
                                port=upstream['port'],
                                vhost=upstream['virtual-host'],
                                ssl_params=ssl_params)
                else:
                    address = "amqp://{user}:{pwd}@{host}:{port}/" \
                              "{vhost}".format(
                                user=config_opts.get("user",
                                                     instance_name+"-admin"),
                                pwd=config_opts.get("pass", default_pass),
                                host=upstream['host'],
                                port=upstream['port'],
                                vhost=upstream['virtual-host'])
                prop = dict(vhost=config_opts['virtual-host'],
                                component="federation-upstream",
                                name=name,
                                value={"uri":address})
                set_parameter('federation-upstream',
                              name,
                              prop,
                              config_opts['virtual-host'])

                policy_name = 'volttron-federation'
                policy_value = {"pattern":"^volttron",
                                "definition":{"federation-upstream-set":"all"},
                                "priority":0,
                                "apply-to": "exchanges"}
                set_policy(policy_name, policy_value, config_opts['virtual-host'])
            except KeyError as ex:
                _log.error("Federation setup  did not complete. "
                           "Missing Key {key} in upstream config "
                           "{upstream}".format(key=ex, upstream=upstream))
                return ex


def _create_shovel_setup():
    """
    Create RabbitMQ shovel based on the RabbitMQ config
    :return:
    """
    global instance_name
    if not config_opts:
        _load_rmq_config()

    shovels = config_opts.get('shovel', [])
    is_ssl = is_ssl_connection()
    src_uri = build_rmq_address(is_ssl)
    if is_ssl:
        ssl_params = get_ssl_url_params()
    _log.debug("Shovels: {}".format(shovels))
    try:
        for shovel in shovels:
            # Build destination address
            if is_ssl:
                dest_uri = "amqps://{host}:{port}/{vhost}?" \
                           "{ssl_params}&server_name_indication={host}".format(
                           host=shovel['host'],
                           port=shovel['port'],
                           vhost=shovel['virtual-host'],
                           ssl_params=ssl_params)
            else:
                dest_uri = "amqp://{user}:{pwd}@{host}:{port}/{vhost}".format(
                    user=config_opts.get("user", instance_name + "-admin"),
                    pwd=config_opts.get("pwd", default_pass),
                    host=shovel['host'],
                    port=shovel['port'],
                    vhost=shovel['virtual-host'])

            pubsub_topics = shovel.get("pubsub-topics", [])
            agent_ids = shovel.get("rpc-agent-identities", [])
            for topic in pubsub_topics:
                _log.debug("Creating shovel to forward PUBSUB topic {}".format(
                    topic))
                name = "shovel-{host}-{topic}".format(host=shovel['host'],
                                                      topic=topic)
                routing_key = "__pubsub__.{instance}.{topic}.#".format(instance=instance_name,
                                                                       topic=topic)
                prop = dict(vhost=config_opts['virtual-host'],
                                component="shovel",
                                name=name,
                                value={"src-uri": src_uri,
                                        "src-exchange":  "volttron",
                                        "src-exchange-key": routing_key,
                                        "dest-uri": dest_uri,
                                        "dest-exchange": "volttron"}
                            )
                _log.debug("shovel property: {}".format(prop))
                # set_parameter("shovel",
                #               name,
                #               prop)

            for identity in agent_ids:
                _log.info("Creating shovel to make RPC call to remote Agent"
                           ": {}".format(topic))
                name = "shovel-{host}-{identity}".format(host=shovel['host'],
                                                         identity=identity)
                routing_key = "{instance}.{identity}.#".format(instance=instance_name,
                                                               identity=identity)
                prop = dict(vhost=config_opts['virtual-host'],
                                component="shovel",
                                name=name,
                                value={"src-uri": src_uri,
                                        "src-exchange":  "volttron",
                                        "src-exchange-key": routing_key,
                                        "dest-uri": dest_uri,
                                        "dest-exchange": "volttron"}
                                )
                _log.debug("shovel property: {}".format(prop))
                # set_parameter("shovel",
                #               name,
                #               prop)
    except KeyError as exc:
        _log.error("Shovel setup  did not complete. Missing Key: {}".format(
            exc))


def _setup_for_ssl_auth(instance_name):
    """
    Utility method to create
    1. Root CA
    2. Instance CA
    3. RabbitMQ server certificates (public and private)
    4. Admin user to connect to RabbitMQ management web interface

    :param instance_name: Instance name
    :return:
    """
    global config_opts, volttron_rmq_config
    _log.info('\nChecking for CA certificate\n')
    instance_ca_name, server_name, admin_client_name = \
        certs.Certs.get_cert_names(instance_name)

    # prompt for host before creating certs as it is needed for server cert
    _create_certs_without_prompt(admin_client_name, instance_ca_name, server_name)

    # if all was well, create the rabbitmq.conf file for user to copy
    # /etc/rabbitmq and update VOLTTRON_HOME/rabbitmq_config.json
    new_conf = """listeners.ssl.default = {amqp_port_ssl}
ssl_options.cacertfile = {ca}
ssl_options.certfile = {server_cert}
ssl_options.keyfile = {server_key}
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true
auth_mechanisms.1 = EXTERNAL
ssl_cert_login_from = common_name
ssl_options.versions.1 = tlsv1.2
ssl_options.versions.2 = tlsv1.1
ssl_options.versions.3 = tlsv1
management.listener.port = {mgmt_port_ssl}
management.listener.ssl = true
management.listener.ssl_opts.cacertfile = {ca}
management.listener.ssl_opts.certfile = {server_cert}
management.listener.ssl_opts.keyfile = {server_key}""".format(
        mgmt_port_ssl=config_opts.get('mgmt-port-ssl', 15671),
        amqp_port_ssl=config_opts.get('amqp-port-ssl', 5671),
        ca=crts.cert_file(ROOT_CA_NAME),
        server_cert=crts.cert_file(server_name),
        server_key=crts.private_key_file(server_name)
    )
    with open(os.path.join(get_home(), "rabbitmq.conf"), 'w') as rconf:
        rconf.write(new_conf)

    # Stop server, move new config file with ssl params, start server
    stop_rabbit(config_opts['rmq-home'])

    # Add VOLTTRON admin user. This is needed to connect to web interface, multi-platform federation, shovel
    # TODO: Could we use guest instead for all local mgmt plugin tasks and
    # use ssl auth for others. To test.
    config_opts["user"] = admin_client_name
    config_opts["pass"] = default_pass

    with open(volttron_rmq_config, 'w') as yaml_file:
        yaml.dump(config_opts, yaml_file, default_flow_style=False)

    os.rename(os.path.join(get_home(), "rabbitmq.conf"),
              os.path.join(config_opts.get("rmq-home"),
                           "etc/rabbitmq/rabbitmq.conf"))
    start_rabbit(config_opts['rmq-home'])
    _log.info("\n#######################"
          "\nSetup complete. A new admin user was created with user name: "
          "{} and password={}.\nYou could change this user's password by "
          "logging into https://{}:{}/ Please update {} if you change password"
          "\n#######################".format(config_opts['user'],
                                             default_pass,
                                             config_opts['host'],
                                             config_opts['mgmt-port-ssl'],
                                             volttron_rmq_config))


def stop_rabbit(rmq_home, quite=False):
    """
    Stop RabbitMQ Server
    :param rmq_home: RabbitMQ installation path
    :param quite:
    :return:
    """
    try:
        cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"),
               "stop"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        gevent.sleep(2)
        if not quite:
            _log.info("**Stopped rmq server")
    except subprocess.CalledProcessError as e:
        if not quite:
            raise e


def start_rabbit(rmq_home):
    """
    Start RabbitMQ server
    :param rmq_home: RabbitMQ installation path
    :return:
    """
    cmd = [os.path.join(rmq_home, "sbin/rabbitmq-server"),
           "-detached"]
    subprocess.check_call(cmd)
    gevent.sleep(10)
    _log.info("**Started rmq server at {}".format(rmq_home))


def _create_certs_without_prompt(admin_client_name, instance_ca_name, server_cert_name):
    """
    Utility method to create certificates
    :param client_cert_name: client (agent) cert name
    :param instance_ca_name: VOLTTRON instance name
    :param server_cert_name: RabbitMQ sever name
    :return:
    """

    global config_opts

    if crts.ca_exists():
        _log.info('\n Root CA Found {}'.format(crts.cert_file(ROOT_CA_NAME)))

    else:
        _log.info('\n Root CA ({}) NOT Found. Creating root ca for '
              'volttron instance'.format(crts.cert_file(ROOT_CA_NAME)))
        cert_data = config_opts.get('certificate-data')
        if not cert_data or not all(k in cert_data for k in ['country',
                                                             'state',
                                                             'location',
                                                             'organization',
                                                             'organization-unit',
                                                             'common-name']):
            raise ValueError("No certificate data found in {}. Please refer "
                             "to example config at "
                             "examples/configs/rabbitmq_config.yml to see "
                             "list of ssl certificate data to be configured"
                             "".format(volttron_rmq_config))
        data = {'C': cert_data.get('country'),
                'ST': cert_data.get('state'),
                'L': cert_data.get('location'),
                'O': cert_data.get('organization'),
                'OU': cert_data.get('organization-unit'),
                'CN': cert_data.get('common-name')}

        create_ca(override=False, data=data)

    crts.create_ca_signed_cert(server_cert_name, type='server',
                               fqdn=config_opts.get('host'))

    crts.create_ca_signed_cert(admin_client_name, type='client')
    create_user(admin_client_name, ssl_auth=False)
    permissions = dict(configure=".*", read=".*", write=".*")
    set_user_permissions(permissions, admin_client_name, ssl_auth=False)


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


def                                                                         setup_rabbitmq_volttron(type):
    """
    Setup VOLTTRON instance to run with RabbitMQ message bus.
    :param type:
            single - Setup to run as single instance
            federation - Setup to connect multiple VOLTTRON instances as a federation
            shovel - Setup shovels to forward local messages to remote instances
    :return:
    """
    global instance_name

    instance_name = get_platform_instance_name(prompt=True)
    # Store config this is checked at startup
    store_message_bus_config(message_bus='rmq', instance_name=instance_name)

    error = _load_rmq_config()
    if error:
        _log.error("\nFor single setup, configuration file must at least "
                 "contain  "
              "host and ssl certificate details. For federation and shovel "
              "setup please refer to example config files under "
              "examples/configs/rabbitmq_config.yml")
        return error

    invalid = True
    if type in ["all", "single"]:
        invalid = False
        _start_rabbitmq_without_ssl()

        # Create local RabbitMQ setup - vhost, exchange etc.
        success = init_rabbitmq_setup() # should be called after _start_rabbitmq_without_ssl
        ssl_auth = config_opts.get('ssl', "true")
        if success and ssl_auth in ('true', 'True', 'TRUE'):
            _setup_for_ssl_auth(instance_name)

    if type in ["all", "federation"]:
        # Create a multi-platform federation setup
        invalid = False
        _create_federation_setup()
    if type in ["shovel", "shovel"]:
        # Create shovel setup
        invalid = False
        _create_shovel_setup()
    if invalid:
        _log.error("Unknown option. Exiting....")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('type',
                        help='Instance type: all, single, federation or shovel')
    args = parser.parse_args()
    type = args.type
    try:
        setup_rabbitmq_volttron(type)
    except KeyboardInterrupt:
        _log.info("Exiting setup process")
