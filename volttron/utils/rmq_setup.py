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

"""
RabbitMQ setup script to
1. setup single instance of RabbitMQ VOLTTRON
2. Federation
3. Shovel
"""

import argparse
import logging
import os
from socket import getfqdn
from shutil import copy
import gevent
import yaml
import time

from . rmq_mgmt import RabbitMQMgmt
from . rmq_config_params import RMQConfig

from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent.utils import (store_message_bus_config,
                                           execute_command)
from volttron.utils.prompt import prompt_response, y, y_or_n
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.platform import jsonapi
from volttron.platform import instance_setup
from urllib.parse import urlparse

_log = logging.getLogger(os.path.basename(__file__))


class RabbitMQStartError(BaseException):
    pass


class RabbitMQSetupAlreadyError(BaseException):
    pass


def _start_rabbitmq_without_ssl(rmq_config, conf_file, env=None):
    """
    Check if basic RabbitMQ configuration is available. Start RabbitMQ in
    non ssl mode so that we can login as guest to create volttron users,
    exchanges, and vhost.
    :return:
    """
    if not rmq_config.volttron_home:
        rmq_config.volttron_home = get_home()

    rmq_home = rmq_config.rmq_home
    if not rmq_home:
        rmq_home = os.path.join(os.path.expanduser("~"),
                                "rabbitmq_server/rabbitmq_server-3.7.7")
        if os.path.exists(rmq_home):
            os.environ['RABBITMQ_HOME'] = rmq_home
        else:
            print("\nERROR:\n"
                  "Missing key 'rmq_home' in RabbitMQ config and RabbitMQ is "
                  "not installed in default path: \n"
                  "~/rabbitmq_server/rabbitmq_server-3.7.7 \n"
                  "Please set the correct RabbitMQ installation path in "
                  "rabbitmq_config.yml")
            exit(1)
    else:
        if not os.path.exists(rmq_home) or not os.path.exists(os.path.join(
                rmq_home, 'sbin/rabbitmq-server')):
            print("\nERROR:\n"
                  "Invalid rmq-home value ({}). Please fix rmq-home "
                  "in {} and rerun this script".format(
                rmq_home, rmq_config.volttron_rmq_config))
            exit(1)
        else:
            os.environ['RABBITMQ_HOME'] = rmq_home

    # attempt to stop
    stop_rabbit(rmq_home, env, quite=True)

    if rmq_config.amqp_port != 5672 and rmq_config.mgmt_port != 15672:
        # If ports if non ssl ports are not default write a rabbitmq.conf before
        # restarting
        new_conf = """listeners.tcp.default = {}
management.listener.port = {}""".format(rmq_config.amqp_port, rmq_config.mgmt_port)

        with open(conf_file, 'w+') as r_conf:
            r_conf.write(new_conf)

    # Need to write env file even when starting without ssl mode since env file will provide the right node name,
    # tcp port and conf file to use. This is essential for tests as we don't use default port, paths or node name.
    # TODO - we should probably not use default node name even for non test use case to avoid node name class when
    #        you have more than one instance of RMQ on the same machine
    write_env_file(rmq_config, conf_file, env)

    # Start RabbitMQ server
    _log.info("Starting RabbitMQ server")
    start_rabbit(rmq_config.rmq_home, env=env)


def write_env_file(rmq_config, conf_file, env=None):
    """
    Write rabbitmq-env.conf file
    :param conf_file:
    :param env: Environment to get the RABBITMQ_CONF_ENV_FILE out of.
    :param rmq_config:
    :return:
    """

    if not env:
        env = os.environ

    # If there is a custom node name then we need to write a env file, set amqp port in this env file, and
    # point to conf file path
    if rmq_config.node_name != 'rabbit':
        nodebase = os.path.dirname(conf_file)
        # Creating a custom node name with custome port. Create a env file and add entry to point to conf file in
        # the env file
        env_entries = """NODENAME={}
NODE_PORT={}
MNESIA_DIR={}
CONFIG_FILE={}
LOG_BASE={}
PLUGINS_EXPAND_DIR={}
PID_FILE={}
RABBITMQ_GENERATED_CONFIG_DIR={}""".format(rmq_config.node_name,
                                           rmq_config.amqp_port,
                                           os.path.join(nodebase, 'mnesia'),
                                           conf_file,
                                           os.path.join(nodebase, 'logs'),
                                           os.path.join(nodebase, 'plugins-expand'),
                                           os.path.join(nodebase, 'rabbitmq.pid'),
                                           os.path.join(nodebase, 'generated_config'))

        with open(env.get('RABBITMQ_CONF_ENV_FILE'), 'w+') as env_conf:
            env_conf.write(env_entries)


def _create_federation_setup(admin_user, admin_password, is_ssl, vhost, vhome):
    """
    Creates a RabbitMQ federation of multiple VOLTTRON instances based on
    rabbitmq config.
        - Builds AMQP/S address for each upstream server
        - Creates upstream servers
        - Adds policy to make "volttron" exchange "federated".

    :return:
    """
    rmq_mgmt = RabbitMQMgmt()

    federation_config_file = os.path.join(vhome,
                                          'rabbitmq_federation_config.yml')
    federation_config = _read_config_file(federation_config_file)
    federation = federation_config.get('federation-upstream')

    if federation:
        ssl_params = None
        if is_ssl:
            ssl_params = rmq_mgmt.get_ssl_url_params()

        for host, upstream in federation.items():
            try:
                name = "upstream-{vhost}-{host}".format(vhost=upstream['virtual-host'],
                                                        host=host)
                _log.debug("Upstream Server: {name} ".format(name=name))

                address = rmq_mgmt.build_rmq_address(admin_user,
                                                     admin_password, host,
                                                     upstream['port'],
                                                     upstream['virtual-host'],
                                                     is_ssl,
                                                     ssl_params)
                prop = dict(vhost=vhost,
                            component="federation-upstream",
                            name=name,
                            value={"uri": address})
                rmq_mgmt.set_parameter('federation-upstream',
                                       name,
                                       prop,
                                       vhost)

                policy_name = 'volttron-federation'
                policy_value = {"pattern": "^volttron",
                                "definition": {"federation-upstream-set": "all"},
                                "priority": 0,
                                "apply-to": "exchanges"}
                rmq_mgmt.set_policy(policy_name,
                                    policy_value,
                                    vhost)
            except KeyError as ex:
                _log.error("Federation setup  did not complete. "
                           "Missing Key {key} in upstream config "
                           "{upstream}".format(key=ex, upstream=upstream))


def _create_shovel_setup(instance_name, local_host, port, vhost, vhome, is_ssl):
    """
    Create RabbitMQ shovel based on the RabbitMQ config
    :return:
    """
    shovel_config_file = os.path.join(vhome,
                                      'rabbitmq_shovel_config.yml')
    shovel_config = _read_config_file(shovel_config_file)
    shovels = shovel_config.get('shovel', {})

    ssl_params = None
    rmq_mgmt = RabbitMQMgmt()
    _log.debug("shovel config: {}".format(shovel_config))
    try:
        for remote_host, shovel in shovels.items():
            pubsub_config = shovel.get("pubsub", {})
            _log.debug("shovel parameters: {}".format(shovel))
            for identity, topics in pubsub_config.items():
                # Build source address
                rmq_user = instance_name + '.' + identity
                src_uri = rmq_mgmt.build_shovel_connection(rmq_user,
                                                           local_host, port,
                                                           vhost, is_ssl)
                is_csr = False
                certs_dict = None
                if 'certificates' in shovel:
                    _log.debug("shovel parameters under destination: {}".format(shovel))
                    is_csr = shovel['certificates']['csr']
                    if is_csr:
                        certs_dict = dict()
                        certs_dict['ca_file'] = shovel['certificates']['remote_ca']
                        certs_dict['cert_file'] = shovel['certificates']['public_cert']
                        certs_dict['key_file'] = shovel['certificates']['private_cert']
                        rmq_user = shovel['shovel-user']
                        _log.debug("certs parameters: {}".format(certs_dict))
                else:
                    # destination key not found in shovel config
                    _log.debug("ERROR: Destination key not found in shovel config. Cannot make connection to remote server without remote certificates")
                    continue
                # Build destination address
                dest_uri = rmq_mgmt.build_shovel_connection(rmq_user,
                                                            remote_host, shovel['port'],
                                                            shovel['virtual-host'],
                                                            is_ssl, certs_dict=certs_dict)

                if not isinstance(topics, list):
                    topics = [topics]
                for topic in topics:
                    _log.debug("Creating shovel to forward PUBSUB topic {}".format(
                        topic))
                    name = "shovel-{host}-{topic}".format(host=remote_host,
                                                          topic=topic)
                    routing_key = "__pubsub__.{instance}.{topic}.#".format(
                        instance=instance_name,
                        topic=topic)
                    prop = dict(vhost=vhost,
                                component="shovel",
                                name=name,
                                value={"src-uri": src_uri,
                                       "src-exchange": "volttron",
                                       "src-exchange-key": routing_key,
                                       "dest-uri": dest_uri,
                                       "dest-exchange": "volttron"}
                                )
                    _log.info("SHOVEL ***** property: {}".format(prop))
                    rmq_mgmt.set_parameter("shovel",
                                            name,
                                            prop)
            rpc_config = shovel.get("rpc", {})
            _log.debug("RPC config: {}".format(rpc_config))
            for remote_instance, agent_ids in rpc_config.items():
                for ids in agent_ids:
                    local_identity = ids[0]
                    remote_identity = ids[1]
                    src_uri = rmq_mgmt.build_shovel_connection(local_identity, instance_name,
                                                               local_host, port, vhost, is_ssl)
                    # This certificates information need to be fed now
                    # dest_uri = rmq_mgmt.build_shovel_connection(local_identity, instance_name,
                    #                                             remote_host, shovel['port'],
                    #                                             shovel['virtual-host'], is_ssl)
                    rmq_user = instance_name + '.' + local_identity
                    is_csr = False
                    certs_dict = None
                    if 'certificates' in shovel:
                        _log.debug("shovel parameters under destination: {}".format(shovel))
                        is_csr = shovel['certificates']['csr']
                        if is_csr:
                            certs_dict = dict()
                            certs_dict['ca_file'] = shovel['certificates']['remote_ca']
                            certs_dict['cert_file'] = shovel['certificates']['public_cert']
                            certs_dict['key_file'] = shovel['certificates']['private_cert']
                            rmq_user = shovel['shovel-user']
                            _log.debug("certs parameters: {}".format(certs_dict))

                    # Build destination address
                    dest_uri = rmq_mgmt.build_shovel_connection(rmq_user,
                                                                remote_host, shovel['port'],
                                                                shovel['virtual-host'],
                                                                is_ssl, certs_dict=certs_dict)
                    _log.info("Creating shovel to make RPC call to remote Agent"
                              ": {}".format(remote_identity))

                    name = "shovel-{host}-{identity}".format(host=remote_host,
                                                             identity=local_identity)
                    routing_key = "{instance}.{identity}.#".format(
                        instance=remote_instance,
                        identity=remote_identity)
                    prop = dict(vhost=vhost,
                                component="shovel",
                                name=name,
                                value={"src-uri": src_uri,
                                       "src-exchange": "volttron",
                                       "src-exchange-key": routing_key,
                                       "dest-uri": dest_uri,
                                       "dest-exchange": "volttron"}
                                )

                    rmq_mgmt.set_parameter("shovel",
                                            name,
                                            prop)
    except KeyError as exc:
        _log.error("Shovel setup  did not complete. Missing Key: {}".format(
            exc))


def _setup_for_ssl_auth(rmq_config, rmq_conf_file, env=None):
    """
    Utility method to create
    1. Root CA
    2. RabbitMQ server certificates (public and private)
    3. RabbitMQ config with SSL setting
    4. Admin user to connect to RabbitMQ management Web interface

    :param instance_name: Instance name
    :return:
    """
    _log.info('\nChecking for CA certificate\n')
    root_ca_name, server_name, admin_client_name = \
        certs.Certs.get_admin_cert_names(rmq_config.instance_name)
    vhome = get_home()
    white_list_dir = os.path.join(vhome, "certificates", "whitelist")
    if not os.path.exists(white_list_dir):
        os.mkdir(white_list_dir)

    _create_certs(rmq_config, admin_client_name, server_name)

    # if all was well, create the rabbitmq.conf file for user to copy
    # /etc/rabbitmq and update VOLTTRON_HOME/rabbitmq_config.json
    new_conf = """listeners.tcp.default = {tcp_port}
management.listener.port = {mgmt_port}
listeners.ssl.default = {amqp_port_ssl}
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
management.listener.ssl_opts.keyfile = {server_key}
trust_store.directory={ca_dir}
trust_store.refresh_interval=0""".format(
        tcp_port=rmq_config.amqp_port,
        mgmt_port=rmq_config.mgmt_port,
        mgmt_port_ssl=rmq_config.mgmt_port_ssl,
        amqp_port_ssl=rmq_config.amqp_port_ssl,
        ca=rmq_config.crts.cert_file(rmq_config.crts.trusted_ca_name),
        server_cert=rmq_config.crts.cert_file(server_name),
        server_key=rmq_config.crts.private_key_file(server_name),
        ca_dir=white_list_dir
    )

    with open(rmq_conf_file, 'w') as rconf:
        rconf.write(new_conf)

    write_env_file(rmq_config, rmq_conf_file, env)

    # Stop server, move new config file with ssl params, start server
    stop_rabbit(rmq_config.rmq_home, env=env)

    start_rabbit(rmq_config.rmq_home, env=env)

    default_vhome = os.path.abspath(
        os.path.normpath(
            os.path.expanduser(
                os.path.expandvars('~/.volttron'))))

    additional_to_do = ""
    if vhome != default_vhome:
        additional_to_do = "\n - Please set environment variable " \
                           "VOLTTRON_HOME " \
                           "to {vhome} before starting volttron"

    msg = "\n\n#######################\n\nSetup complete for volttron home " \
          "{vhome} " \
          "with instance name={}\nNotes:" + additional_to_do + \
          "\n - On production environments, restrict write access to {" \
          "root_ca} to only admin user. For example: " \
          "sudo chown root {root_ca} and {trusted_ca}" \
          "\n - A new admin user was created with user name: {} and " \
          "password={}.\n   You could change this user's password by logging " \
          "into https://{}:{}/ Please update {} if you change password" \
          "\n\n#######################"
    _log.info(msg.format(rmq_config.instance_name,
                         rmq_config.admin_user,
                         rmq_config.admin_pwd,
                         rmq_config.hostname,
                         rmq_config.mgmt_port_ssl,
                         rmq_config.volttron_rmq_config,
                         root_ca=rmq_config.crts.cert_file(
                             rmq_config.crts.root_ca_name),
                         trusted_ca=rmq_config.crts.cert_file(
                             rmq_config.crts.trusted_ca_name),
                         vhome=vhome))


def _create_certs(rmq_config, admin_client_name, server_cert_name):
    """
    Utility method to create certificates
    :param client_cert_name: client (agent) cert name
    :param instance_ca_name: VOLTTRON instance name
    :param server_cert_name: RabbitMQ sever name
    :return:
    """

    crts = rmq_config.crts

    if rmq_config.crts.ca_exists():
        if rmq_config.use_existing_certs is None:
            attributes = crts.get_cert_subject(crts.root_ca_name)
            prompt_str = "Found {} with the following attributes. \n {} \n Do " \
                         "you want to use this certificate: ".format(
                crts.cert_file(crts.root_ca_name), attributes)
            prompt = prompt_response(prompt_str,
                                     valid_answers=y_or_n,
                                     default='Y')
            if prompt in y:
                return

        elif rmq_config.use_existing_certs:
            return

        if rmq_config.use_existing_certs is None:
            prompt_str = "\n**IMPORTANT:**\nCreating a new Root CA will " \
                         "invalidate " \
                         "any existing agent certificate and hence any existing " \
                         "certificates will be deleted. If you have federation " \
                         "or shovel setup, you will have to share the new " \
                         "certificate with the other volttron instance(s) for " \
                         "the shovel/federation connections to work. " \
                         "Do you want to create a new Root CA."
            prompt = prompt_response(prompt_str,
                                     valid_answers=y_or_n,
                                     default='N')
            if prompt not in y:
                return

    # We are creating new CA cert so delete any existing certs.  The user has
    # already been warned
    for d in [crts.cert_dir, crts.private_dir, crts.ca_db_dir]:
        for x in os.listdir(d):
            os.remove(os.path.join(d, x))

    _log.info('\n Creating root ca for volttron instance: {}'.format(
        crts.cert_file(crts.root_ca_name)))
    cert_data = rmq_config.certificate_data
    if not cert_data or \
            not (all(k in cert_data for k in ['country',
                                              'state',
                                              'location',
                                              'organization',
                                              'organization-unit',
                                              'common-name']) or
                 all(
                  k in cert_data for k in ['ca-public-key', 'ca-private-key'])):
        print(
            "\nERROR:\n"
            "No certificate data found in {} or certificate data is "
            "incomplete. certificate-data should either contain all "
            "the details necessary to create a self signed CA or "
            "point to the file path of an existing CA's public and "
            "private key. Please refer to example "
            "config at examples/configurations/rabbitmq/rabbitmq_config.yml"
            " to see list of ssl certificate data to be configured".format(
                rmq_config.volttron_rmq_config))
        exit(1)
    if cert_data.get('ca-public-key'):
        # using existing CA
        copy(cert_data['ca-public-key'],
             rmq_config.crts.cert_file(crts.root_ca_name))
        copy(cert_data['ca-private-key'],
             rmq_config.crts.private_key_file(crts.root_ca_name))
    else:
        data = {'C': cert_data.get('country'),
                'ST': cert_data.get('state'),
                'L': cert_data.get('location'),
                'O': cert_data.get('organization'),
                'OU': cert_data.get('organization-unit'),
                'CN': cert_data.get('common-name')}
        _log.info("Creating root ca with the following info: {}".format(data))
        crts.create_root_ca(overwrite=False, **data)

    # create a copy of the root ca as instance_name-trusted-cas.crt.
    copy(rmq_config.crts.cert_file(crts.root_ca_name),
         rmq_config.crts.cert_file(crts.trusted_ca_name))

    crts.create_signed_cert_files(server_cert_name, cert_type='server',
                                  fqdn=rmq_config.hostname)

    crts.create_signed_cert_files(admin_client_name, cert_type='client')


def _verify_and_save_instance_ca(rmq_config, instance_ca_path, instance_ca_key):
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
        rmq_config.crts.save_cert(instance_ca_path)
        rmq_config.crts.save_key(instance_ca_key)
    return found


def setup_rabbitmq_volttron(setup_type, verbose=False, prompt=False, instance_name=None,
                            rmq_conf_file=None, env=None):
    """
    Setup VOLTTRON instance to run with RabbitMQ message bus.
    :param setup_type:
            single - Setup to run as single instance
            federation - Setup to connect multiple VOLTTRON instances as
                         a federation
            shovel - Setup shovels to forward local messages to remote instances
    :param verbose
    :param prompt
    :raises RabbitMQSetupAlreadyError
    """
    if not instance_name:
        instance_name = get_platform_instance_name(prompt=True)
    # Store config this is checked at startup
    store_message_bus_config(message_bus='rmq', instance_name=instance_name)

    rmq_config = RMQConfig()
    if verbose:
        _log.setLevel(logging.DEBUG)
        _log.debug("verbose set to True")
        _log.debug(get_home())
        logging.getLogger("requests.packages.urllib3.connectionpool"
                          "").setLevel(logging.DEBUG)
    else:
        _log.setLevel(logging.INFO)
        logging.getLogger("requests.packages.urllib3.connectionpool"
                          "").setLevel(logging.WARN)

    if prompt:
        # ignore any existing rabbitmq_config.yml in vhome. Prompt user and
        # generate a new rabbitmq_config.yml
        _create_rabbitmq_config(rmq_config, setup_type)

    # Load either the newly created config or config passed
    try:
        rmq_config.load_rmq_config()

    except (yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.YAMLError) as exc:
        _log.error("Error: YAML file cannot parsed properly. Check the contents of the file")
        return exc

    except IOError as exc:
        _log.error("Error opening {}. Please create a rabbitmq_config.yml "
                   "file in your volttron home. If you want to point to a "
                   "volttron home other than {} please set it as the "
                   "environment variable VOLTTRON_HOME".format(
            rmq_config.volttron_rmq_config, rmq_config.volttron_home))
        _log.error("\nFor single setup, configuration file must at least "
                   "contain host and ssl certificate details. For federation "
                   "and shovel setup, config should contain details about the "
                   "volttron instance with which communication needs "
                   "to be established. Please refer to example config file "
                   "at examples/configurations/rabbitmq/rabbitmq_config.yml")
        raise

    if not rmq_conf_file:
        rmq_conf_file = os.path.join(rmq_config.rmq_home, "etc/rabbitmq/rabbitmq.conf")

    invalid = True
    if setup_type in ["all", "single"]:
        invalid = False
        # Verify that the rmq_conf_file if exists is removed before continuing.
        message = f"A rabbitmq conf file {rmq_conf_file} already exists.\n" \
                  "In order for setup to proceed it must be removed.\n"
        if os.path.exists(rmq_conf_file):
            print(message)
            while os.path.exists(rmq_conf_file):
                value = prompt_response(f"Remove {rmq_conf_file}? ", y_or_n)
                if value in y:
                    os.remove(rmq_conf_file)

        _start_rabbitmq_without_ssl(rmq_config, rmq_conf_file, env=env)
        _log.debug("Creating rabbitmq virtual hosts and required users for "
                   "volttron")
        # Create local RabbitMQ setup - vhost, exchange etc.
        # should be called after _start_rabbitmq_without_ssl
        rmq_mgmt = RabbitMQMgmt()
        success = rmq_mgmt.init_rabbitmq_setup()
        if success and rmq_config.is_ssl:
            _setup_for_ssl_auth(rmq_config, rmq_conf_file, env=env)

        # Create utility scripts
        script_path = os.path.dirname(os.path.realpath(__file__))
        src_home = os.path.dirname(os.path.dirname(script_path))
        start_script = os.path.join(src_home, 'start-rabbitmq')
        with open(start_script, 'w+') as f:
            f.write(os.path.join(rmq_config.rmq_home, 'sbin',
                                 'rabbitmq-server') + ' -detached')
            f.write(os.linesep)
            f.write("sleep 5")  # give a few seconds for all plugins to be ready
        os.chmod(start_script, 0o755)

        stop_script = os.path.join(src_home, 'stop-rabbitmq')
        with open(stop_script, 'w+') as f:
            f.write(os.path.join(rmq_config.rmq_home, 'sbin',
                                 'rabbitmqctl') + ' stop')
        os.chmod(stop_script, 0o755)

        # symlink to rmq log
        log_name = os.path.join(src_home, 'rabbitmq.log')
        if os.path.lexists(log_name):
            os.unlink(log_name)

        os.symlink(os.path.join(rmq_config.rmq_home,
                                'var/log/rabbitmq',
                                rmq_config.node_name + "@" +
                                rmq_config.hostname.split('.')[0] + ".log"),
                   log_name)

    if setup_type in ["all", "federation"]:
        # Create a multi-platform federation setup
        invalid = False
        _create_federation_setup(rmq_config.admin_user,
                                 rmq_config.admin_pwd,
                                 rmq_config.is_ssl,
                                 rmq_config.virtual_host,
                                 rmq_config.volttron_home)
    if setup_type in ["all", "shovel"]:
        # Create shovel setup
        invalid = False
        if rmq_config.is_ssl:
            port = rmq_config.amqp_port_ssl
        else:
            port = rmq_config.amqp_port
        _create_shovel_setup(rmq_config.instance_name,
                             rmq_config.hostname,
                             port,
                             rmq_config.virtual_host,
                             rmq_config.volttron_home,
                             rmq_config.is_ssl)
    if invalid:
        _log.error("Unknown option. Exiting....")


def _create_rabbitmq_config(rmq_config, setup_type):
    """
    Prompt user for required details and create a rabbitmq_config.yml file in
    volttron home
    :param setup_type: type of rmq setup - single, federation, shovel or all
    """

    if setup_type == 'single' or setup_type == 'all':
        if os.path.exists(rmq_config.volttron_rmq_config):
            prompt = "rabbitmq_config.yml exists in {} Do you wish to " \
                     "use this file to configure the instance".format(
                get_home())
            prompt = prompt_response(prompt,
                                     valid_answers=y_or_n,
                                     default='Y')
            if prompt in y:
                return
            else:
                _log.info("New input data will be used to overwrite existing "
                          "{}".format(rmq_config.volttron_rmq_config))
                # TODO: ideally we can load existing file and set values in it
                # default and the compare what changed. If rmq-home changed
                # and existing config those should get cleared. If cert details
                # get changed - overwrite ca, server, admin cert and delete all
                # other certs.

        rmq_config.rmq_home = _prompt_rmq_home(rmq_config.rabbitmq_server)

        prompt = 'Fully qualified domain name of the system:'
        new_host = prompt_response(prompt, default=getfqdn())
        rmq_config.hostname = new_host

        rmq_config.is_ssl = True

        if rmq_config.is_ssl:
            prompt = "Would you like to create a new self signed root CA" \
                     "certificate for this instance:"
            prompt = prompt_response(prompt,
                                     valid_answers=y_or_n,
                                     default='Y')
            if prompt in y:
                cert_data = {}
                print(
                    "\nPlease enter the following details for root CA certificate")
                prompt = '\tCountry:'
                cert_data['country'] = prompt_response(prompt, default='US')
                prompt = '\tState:'
                cert_data['state'] = prompt_response(prompt, mandatory=True)
                prompt = '\tLocation:'
                cert_data['location'] = prompt_response(prompt, mandatory=True)
                prompt = '\tOrganization:'
                cert_data['organization'] = prompt_response(prompt, mandatory=True)
                prompt = '\tOrganization Unit:'
                cert_data['organization-unit'] = prompt_response(prompt,
                                                                 mandatory=True)
                cert_data['common-name'] = rmq_config.instance_name + '-root-ca'
                rmq_config.certificate_data = cert_data
            else:
                error = True
                while error:
                    while True:
                        prompt = 'Enter the root CA certificate public key file:'
                        root_public = prompt_response(prompt, mandatory=True)
                        if is_file_readable(root_public):
                            break
                    while True:
                        prompt =\
                            'Enter the root CA certificate private key file:'
                        root_key = prompt_response(prompt, mandatory=True)
                        if is_file_readable(root_key):
                            break
                    if certs.Certs.validate_key_pair(root_public, root_key):
                        error = False
                        cert_data = {
                            'ca-public-key': root_public,
                            'ca-private-key': root_key
                        }
                        rmq_config.certificate_data = cert_data
                    else:
                        print("Error: Given public key and private key do not "
                              "match or is invalid. public and private key "
                              "files should be PEM encoded and private key "
                              "should use RSA encryption")

        prompt = "Do you want to use default values for RabbitMQ home, " \
                 "ports, and virtual host:"
        prompt = prompt_response(prompt,
                                 valid_answers=y_or_n,
                                 default='Y')
        if prompt in y:
            rmq_config.amqp_port = '5672'
            rmq_config.mgmt_port = '15672'
            rmq_config.amqp_port_ssl = '5671'
            rmq_config.mgmt_port_ssl = '15671'
            rmq_config.virtual_host = 'volttron'
        else:
            rmq_config.virtual_host = _prompt_vhost(rmq_config.config_opts)

            prompt = 'AMQP port for RabbitMQ:'
            rmq_config.amqp_port = prompt_port(5672, prompt)

            prompt = 'http port for the RabbitMQ management plugin:'
            rmq_config.mgmt_port = prompt_port(15672, prompt)

            if rmq_config.is_ssl:
                prompt = 'AMQPS (SSL) port RabbitMQ address:'
                rmq_config.amqp_port_ssl = prompt_port(5671, prompt)

                prompt = 'https port for the RabbitMQ management plugin:'
                rmq_config.mgmt_port_ssl = prompt_port(15671, prompt)

        # Write the new config options back to config file
        rmq_config.write_rmq_config()
    if setup_type in ['federation', 'all']:
        # if option was all then config_opts would be not null
        # if this was called with just setup_type = federation, load existing
        # config so that we don't overwrite existing federation configs
        prompt_upstream_servers(rmq_config.volttron_home)
    if setup_type in ['shovel', 'all']:
        # if option was all then config_opts would be not null
        # if this was called with just setup_type = shovel, load existing
        # config so that we don't overwrite existing list
        prompt_shovels(rmq_config.volttron_home)


def is_file_readable(file_path):
    file_path = os.path.expanduser(os.path.expandvars(file_path))
    if os.path.exists(file_path) and os.access(file_path, os.R_OK):
        return True
    else:
        print("\nInvalid file path. Path does not exists or is not readable")
        return False


def prompt_port(default_port, prompt):
    valid_port = False
    while not valid_port:
        port = prompt_response(prompt, default=default_port)
        try:
            port = int(port)
            return port
        except ValueError:
            _log.error("Invalid port. Port should be an integer")


def _prompt_rmq_home(rabbitmq_server):
    default_dir = os.path.join(os.path.expanduser("~"),
                               "rabbitmq_server", rabbitmq_server)
    valid_dir = False
    while not valid_dir:
        prompt = 'RabbitMQ server home:'
        rmq_home = prompt_response(prompt, default=default_dir)
        if os.path.exists(rmq_home) and \
                os.path.exists(os.path.join(rmq_home, 'sbin/rabbitmq-server')):
            return rmq_home
        else:
            _log.error("Invalid install directory. Unable to find {} ".format(
                os.path.join(rmq_home, 'sbin/rabbitmq-server')))
            return None


def _prompt_vhost(config_opts):
    vhost = config_opts.get('virtual-host', 'volttron')
    prompt = 'Name of the virtual host under which RabbitMQ ' \
             'VOLTTRON will be running:'
    new_vhost = prompt_response(prompt, default=vhost)
    return new_vhost


def _prompt_ssl():
    prompt = prompt_response('\nEnable SSL Authentication:',
                             valid_answers=y_or_n,
                             default='Y')
    if prompt in y:
        return True
    else:
        return False


def prompt_upstream_servers(vhome):
    """
    Prompt for upstream server configurations and save in
    rabbitmq_federation_config.yml
    :return:
    """
    federation_config_file = os.path.join(vhome,
                                          'rabbitmq_federation_config.yml')

    if os.path.exists(federation_config_file):
        federation_config = _read_config_file(federation_config_file)
    else:
        federation_config = {}

    upstream_servers = federation_config.get('federation-upstream', {})
    prompt = 'Number of upstream servers to configure:'
    count = prompt_response(prompt, default=1)
    count = int(count)
    i = 0

    for i in range(0, count):
        prompt = 'Hostname of the upstream server: '
        host = prompt_response(prompt, mandatory=True)
        prompt = 'Port of the upstream server: '
        port = prompt_response(prompt, default=5671)
        prompt = 'Virtual host of the upstream server: '
        vhost = prompt_response(prompt, default='volttron')
        upstream_servers[host] = {'port': port,
                                  'virtual-host': vhost}

    federation_config['federation-upstream'] = upstream_servers
    _write_to_config_file(federation_config_file, federation_config)


def prompt_shovels(vhome):
    """
    Prompt for shovel configuration and save in rabbitmq_shovel_config.yml
    :return:
    """
    shovel_config_file = os.path.join(vhome, 'rabbitmq_shovel_config.yml')

    if os.path.exists(shovel_config_file):
        shovel_config = _read_config_file(shovel_config_file)
    else:
        shovel_config = {}

    shovels = shovel_config.get('shovels', {})
    prompt = 'Number of destination hosts to configure:'
    count = prompt_response(prompt, default=1)
    count = int(count)
    i = 0

    try:
        for i in range(0, count):
            prompt = 'Hostname of the destination server: '
            host = prompt_response(prompt, mandatory=True)
            prompt = 'Port of the destination server: '
            port = prompt_response(prompt, default=5671)
            prompt = 'Virtual host of the destination server: '
            vhost = prompt_response(prompt, default='volttron')
            shovels[host] = {'port': port,
                             'virtual-host': vhost}
            shovel_user = 'shovel{}'.format(host)
            rmq_mgmt = RabbitMQMgmt()
            instance_name = get_platform_instance_name()
            rmq_mgmt.build_agent_connection(shovel_user, instance_name)
            import time
            time.sleep(20)
            shovels[host]['shovel-user'] = instance_name + "." + shovel_user
            #_log.debug("shovel_user: {}".format(shovel_user))
            prompt = prompt_response('\nDo you have certificates signed by remote CA? ',
                                     valid_answers=y_or_n,
                                     default='N')

            if prompt in y:
                prompt = 'Full path to remote CA certificate: '
                ca_file = prompt_response(prompt, default='')
                shovels[host]['certificates'] = {}
                shovels[host]['certificates']['csr'] = True

                # ca cert
                shovels[host]['certificates']['remote_ca'] = ca_file
                if not os.path.exists(ca_file):
                    _log.debug("path does not exist {}".format(ca_file))
                prompt = 'Full path to remote CA signed public certificate: '
                certfile = prompt_response(prompt, default='')
                # public cert
                shovels[host]['certificates']['public_cert'] = certfile
                if not os.path.exists(certfile):
                    _log.debug("path does not exist {}".format(certfile))
                prompt = 'Full path to private certificate: '
                private_cert = prompt_response(prompt, default='')
                # private_key
                shovels[host]['certificates']['private_cert'] = private_cert
                if not os.path.exists(private_cert):
                    _log.debug("path does not exist {}".format(private_cert))
            else:
                remote_https_address = "https://{}:8443".format(host)
                prompt = 'Path to remote web interface: '

                remote_addr = prompt_response(prompt, default=remote_https_address)
                valid_address = instance_setup.is_valid_url(remote_addr, ['https'])
                if not valid_address:
                    print("Address is not valid.")
                else:
                    remote_addr = remote_addr
                # request shovel CSR from remote host
                ca_file, certfile, prvtfile = _request_csr(shovel_user, remote_addr)
                if ca_file is not None and certfile is not None and prvtfile is not None:
                    shovels[host]['certificates'] = {}
                    shovels[host]['certificates']['csr'] = True
                    #_log.debug("shovel ca file path: {}".format(ca_file))
                    shovels[host]['certificates']['remote_ca'] = ca_file

                    # public cert
                    shovels[host]['certificates']['public_cert'] = certfile
                    #_log.debug("shovel public cert path: {}".format(certfile))

                    # private_key
                    crts = certs.Certs()
                    shovels[host]['certificates']['private_cert'] = prvtfile
                    #_log.debug("shovel private cert path: {}".format(prvtfile))

            prompt = prompt_response('\nDo you want shovels for '
                                     'PUBSUB communication? ',
                                     valid_answers=y_or_n,
                                     default='N')

            if prompt in y:
                prompt = 'Name of the agent publishing the topic:'
                agent_id = prompt_response(prompt, mandatory=True)

                prompt = 'List of PUBSUB topics to publish to ' \
                         'this remote instance (comma seperated)'
                topics = prompt_response(prompt, mandatory=True)
                topics = topics.split(",")
                shovels[host]['pubsub'] = {agent_id : topics}
            prompt = prompt_response(
                '\nDo you want shovels for RPC communication? ',
                valid_answers=y_or_n, default='N')
            if prompt in y:
                prompt = 'Name of the remote instance: '
                remote_instance = prompt_response(prompt, mandatory=True)
                prompt = 'Number of Local to Remote pairs:'
                agent_count = prompt_response(prompt, default=1)
                agent_count = int(agent_count)
                agent_ids = []
                for r in range(0, agent_count):
                    prompt = 'Local agent that wants to make RPC'
                    local_agent_id = prompt_response(prompt, mandatory=True)
                    prompt = 'Remote agent on which to make the RPC'
                    remote_agent_id = prompt_response(prompt, mandatory=True)
                    agent_ids.append([local_agent_id, remote_agent_id])
                shovels[host]['rpc'] = {remote_instance: agent_ids}
    except ValueError as e:
        _log.error("Invalid choice in the configuration: {}".format(e))
    else:
        shovel_config['shovel'] = shovels
        _write_to_config_file(shovel_config_file, shovel_config)


def _request_csr(shovel_user, remote_addr):
    ca_file = None
    certfile = None
    prvtfile = None

    response = request_cert_for_shovel(shovel_user=shovel_user,
                                       remote_address=remote_addr)
    #_log.debug("Shovel certs response: {}".format(response))
    success = False
    retry_attempt = 0
    if response is None:
        # Error /status is pending
        _log.error("Error occured, couldn't connect to server: {}".format(remote_addr))
    elif isinstance(response, tuple):

        if response[0] == 'PENDING':
            while not success and retry_attempt < 3:
                response = request_cert_for_shovel(shovel_user=shovel_user,
                                                   remote_address=remote_addr)
                if response is None:
                    break
                elif response[0] == 'PENDING':
                    sleep_period = 30
                    time.sleep(sleep_period)
                    _log.info("Attempting CSR for shovel: {} again after {} seconds".format(shovel_user, sleep_period))
                    retry_attempt += 1
                else:
                    success = True
    else:
        success = True
    if retry_attempt >= 3 and not success:
        _log.error("Maximum retry attempts for CSR reached. Please check the connection and the admin of the remote connection")

    if success:
        # remote cert file for shovels will be in $VOLTTRON_HOME/certificates/shovels dir
        cert_dir = None
        filename = None
        if os.path.exists(response):
            certfile = response
            cert_dir, filename = os.path.split(certfile)
        else:
            # Error occured
            pass
        metafile = certfile[:-4] + ".json"
        metadata = jsonapi.loads(open(metafile).read())
        local_keyfile = metadata['local_keyname']
        ca_name = metadata['remote_ca_name']
        # remote ca
        ca_file = '/'.join((get_remote_shovel_certs_dir(shovel_user), ca_name + '.crt'))
        #_log.debug("shovel ca file path: {}".format(ca_file))

        # private_key
        crts = certs.Certs()
        prvtfile = crts.private_key_file(name=local_keyfile)
        #_log.debug("shovel prvtfile path: {}".format(prvtfile))

    return ca_file, certfile, prvtfile


def _read_config_file(filename):
    data = {}
    try:
        with open(filename, 'r') as yaml_file:
            data = yaml.safe_load(yaml_file)
    except IOError as exc:
        _log.error("Error reading from file: {}".format(filename))
    except yaml.YAMLError as exc:
        _log.error("Yaml Error: {}".format(filename))
    return data


def _write_to_config_file(filename, data):
    try:
        with open(filename, 'w') as yaml_file:
            yaml.dump(data, yaml_file, default_flow_style=False)
    except IOError as exc:
        _log.error("Error writing to file: {}".format(filename))
    except yaml.YAMLError as exc:
        _log.error("Yaml Error: {}".format(filename))


def stop_rabbit(rmq_home, env=None, quite=False):
    """
    Stop RabbitMQ Server
    :param rmq_home: RabbitMQ installation path
    :param env: Environment to run the RabbitMQ command.
    :param quite:
    :return:
    """
    try:
        if env:
            _log.debug("Stop RMQ: {}".format(env.get('VOLTTRON_HOME')))
        cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"), "stop"]
        execute_command(cmd, env=env)
        gevent.sleep(2)
        if not quite:
            _log.info("**Stopped rmq server")
    except RuntimeError as e:
        if not quite:
            raise e


def restart_ssl(rmq_home, env=None):
    """
    Runs rabbitmqctl eval "ssl:stop(), ssl:start()." to make rmq reload ssl certificates. Client connection will get
    dropped and client should reconnect.
    :param rmq_home:
    :param env: Environment to run the RabbitMQ command.
    :return:
    """
    cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"), "eval", "ssl:stop(), ssl:start()."]
    execute_command(cmd, err_prefix="Error reloading ssl certificates", env=env, logger=_log)


def get_remote_shovel_certs_dir(shovel_user):
    shovel_base_dir = os.path.join(get_home(), 'certificates', 'shovels')
    if not os.path.exists(shovel_base_dir):
        os.makedirs(shovel_base_dir)
    shovel_path = os.path.join(shovel_base_dir)
    if not os.path.exists(shovel_path):
        os.makedirs(shovel_path)
    return shovel_path


def request_shovel_cert(shovel_user, csr_server, fully_qualified_local_identity, discovery_info):
    import grequests

    # from volttron.platform.web import DiscoveryInfo
    config = RMQConfig()

    if not config.is_ssl:
        raise ValueError("Only can create csr for rabbitmq based platform in ssl mode.")

    rmq_mgmt = RabbitMQMgmt()
    crts = certs.Certs()
    csr_request = crts.create_csr(fully_qualified_local_identity, discovery_info.instance_name)
    # The csr request requires the fully qualified identity that is
    # going to be connected to the external instance.
    #
    # The remote instance id is the instance name of the remote platform
    # concatenated with the identity of the local fully quallified identity.
    remote_cert_name = "{}.{}".format(discovery_info.instance_name,
                                      fully_qualified_local_identity)
    remote_ca_name = discovery_info.instance_name + "_ca"

    # if certs.cert_exists(remote_cert_name, True):
    #     return certs.cert(remote_cert_name, True)

    json_request = dict(
        csr=csr_request.decode("utf-8"),
        identity=remote_cert_name,
        hostname=config.hostname
    )
    request = grequests.post(csr_server + "/csr/request_new",
                             json=jsonapi.dumps(json_request),
                             verify=False)
    response = grequests.map([request])

    if response and isinstance(response, list):
        response[0].raise_for_status()
    response = response[0]

    print("The response: {}".format(response))

    j = response.json()
    status = j.get('status')
    cert = j.get('cert')
    message = j.get('message', '')
    remote_certs_dir = get_remote_shovel_certs_dir(shovel_user)
    if status == 'SUCCESSFUL' or status == 'APPROVED':
        crts.save_agent_remote_info(remote_certs_dir,
                                     fully_qualified_local_identity,
                                     remote_cert_name, cert.encode("utf-8"),
                                     remote_ca_name,
                                     discovery_info.rmq_ca_cert.encode("utf-8"))
        os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(remote_certs_dir, "requests_ca_bundle")
        print("Set os.environ requests ca bundle to {}".format(os.environ['REQUESTS_CA_BUNDLE']))
    elif status == 'PENDING':
        print("Pending CSR request for {}".format(remote_cert_name))
    elif status == 'DENIED':
        print("Denied CSR request for {}".format(remote_cert_name))
        return status, None
    elif status == 'ERROR':
        err = "Error retrieving certificate from {}\n".format(
            config.hostname)
        err += "{}".format(message)
        raise ValueError(err)
    else:  # No response
        print("No response CSR request for {}".format(remote_cert_name))
        return None

    certfile = os.path.join(remote_certs_dir, remote_cert_name + ".crt")
    if os.path.exists(certfile):
        return certfile
    else:
        return status, message


def request_cert_for_shovel(shovel_user, remote_address):
    value = None
    parsed_address = urlparse(remote_address)
    if parsed_address.scheme in ('https',):
        from volttron.platform.web import DiscoveryInfo
        from volttron.platform.web import DiscoveryError
        from volttron.platform.agent.utils import get_platform_instance_name, get_fq_identity, get_messagebus
        info = DiscoveryInfo.request_discovery_info(remote_address)

        # This is if both remote and local are rmq message buses.
        if info.messagebus_type == 'rmq':
            fqid_local = get_fq_identity(shovel_user)

            # Check if we already have the cert, if so use it instead of requesting cert again
            remote_certs_dir = get_remote_shovel_certs_dir(shovel_user)
            remote_cert_name = "{}.{}".format(info.instance_name, fqid_local)
            certfile = os.path.join(remote_certs_dir, remote_cert_name + ".crt")

            if os.path.exists(certfile):
                value = certfile
            else:
                # request for new CSR
                response = request_shovel_cert(shovel_user, remote_address, fqid_local, info)
                if response is None:
                    _log.error("there was no response from the server")
                    value = None
                elif isinstance(response, tuple):
                    if response[0] == 'PENDING':
                        _log.info("Waiting for administrator to accept a CSR request.")
                    if response[0] == 'DENIED':
                        _log.info("CSR request has been denied")
                    value = response
                elif os.path.exists(response):
                    value = response
    return value

def check_rabbit_status(rmq_home=None, env=None):
    status = True
    if not rmq_home:
        rmq_cfg = RMQConfig()
        rmq_home = rmq_cfg.rmq_home

    status_cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"), "shovel_status"]
    try:
        execute_command(status_cmd, env=env)
    except RuntimeError:
        status = False
    return status


def start_rabbit(rmq_home, env=None):
    """
    Start RabbitMQ server.

    The function assumes that rabbitmq.conf in rmq_home/etc/rabbitmq is setup before
    this funciton is called.

    If the function cannot detect that rabbit was started within roughly 60 seconds
    then `class:RabbitMQStartError` will be raised.

    :param rmq_home: RabbitMQ installation path
    :param env: Environment to start RabbitMQ with.

    :raises RabbitMQStartError:
    """

    # rabbitmqctl status returns true as soon as the erlang vm and does not wait
    # for all the plugins and database to be initialized and rmq is ready to
    # accept incoming connection.
    # Nor does rabbitmqctl wait, rabbitmqctl await_online_nodes work for this
    #  purpose. shovel_status comes close...

    status_cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"), "shovel_status"]
    start_cmd = [os.path.join(rmq_home, "sbin/rabbitmq-server"), "-detached"]

    i = 0
    started = False
    start = True
    while not started:
        try:
            # we expect this call to raise a RuntimeError until the rabbitmq server
            # is up and running.
            execute_command(status_cmd, env=env)
            if not start:
                # if we have attempted started already
                gevent.sleep(1)  # give a second just to be sure
            started = True
            _log.info("Rmq server at {} is running at ".format(rmq_home))
        except RuntimeError as e:
            # First time this exception block we are going to attempt to start
            # the rabbitmq server.
            if start:
                _log.debug("Rabbitmq is not running. Attempting to start")
                msg = "Error starting rabbitmq at {}".format(rmq_home)
                # attempt to start once
                execute_command(start_cmd, env=env,  err_prefix=msg, logger=_log)
                start = False
            else:
                if i > 60:  # if more than 60 tries we assume something failed
                    raise RabbitMQStartError("Unable to verify rabbitmq server has started in a resonable time.")
                else:
                    # sleep for another 2 seconds and check status again
                    gevent.sleep(2)
                    i = i + 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('setup_type',
                        help='Instance type: all, single, federation or shovel')
    parser.add_argument('prompt', default=False,
                        help='Instance type: all, single, federation or shovel')
    args = parser.parse_args()
    try:
        setup_rabbitmq_volttron(args.setup_type, args.prompt)
    except KeyboardInterrupt:
        _log.info("Exiting setup process")



