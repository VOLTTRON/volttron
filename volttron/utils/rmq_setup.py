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
RabbitMQ setup script to
1. setup single instance of RabbitMQ VOLTTRON
2. Federation
3. Shovel
"""

import argparse
import logging
import os
import subprocess
import time
from socket import getfqdn
from shutil import copy
import gevent
import yaml

from rmq_mgmt import RabbitMQMgmt
from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent.utils import store_message_bus_config
from volttron.utils.prompt import prompt_response, y, y_or_n
from volttron.platform.agent.utils import get_platform_instance_name
from rmq_config_params import RMQConfig

_log = logging.getLogger(os.path.basename(__file__))


def _start_rabbitmq_without_ssl(rmq_config):
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
            raise ValueError(
                "Missing Key in RabbitMQ config. RabbitMQ is not installed "
                "in default path: \n"
                "~/rabbitmq_server/rabbitmq_server-3.7.7 \n"
                "Set the correct RabbitMQ installation path")
    else:
        if not os.path.exists(rmq_home) or not os.path.exists(os.path.join(
                rmq_home, 'sbin/rabbitmq-server')):
            raise ValueError("Invalid rmq-home value ({}). Please fix rmq-home "
                             "in {} and rerun this script".format(
                rmq_home, rmq_config.volttron_rmq_config))
        else:
            os.environ['RABBITMQ_HOME'] = rmq_home

    rmq_config.set_default_config()

    # attempt to stop
    stop_rabbit(rmq_home, quite=True)
    # mv any existing conf file to backup
    conf = os.path.join(rmq_home, "etc/rabbitmq/rabbitmq.conf")
    if os.path.exists(conf):
        os.rename(conf, os.path.join(rmq_home,
                                     "etc/rabbitmq/rabbitmq.conf_" +
                                     time.strftime("%Y%m%d-%H%M%S")
                                     ))

    if rmq_config.amqp_port != 5672 and rmq_config.mgmt_port != 15672:
        # If ports if non ssl ports are not default write a rabbitmq.conf before
        # restarting
        new_conf = """listeners.tcp.default = 5672
management.listener.port = 15672"""
        with open(os.path.join(rmq_config.rmq_home,
                               "etc/rabbitmq", "rabbitmq.conf"),
                  'w+') as r_conf:
            r_conf.write(new_conf)

    # Start RabbitMQ server
    _log.info("Starting RabbitMQ server")
    start_rabbit(rmq_config.rmq_home)


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

        for host, upstream in federation.iteritems():
            try:
                name = "upstream-{vhost}-{host}".format(vhost=upstream['virtual-host'],
                                                        host=host)
                _log.debug("Upstream Server: {name} ".format(name=name))

                if is_ssl:
                    address = "amqps://{host}:{port}/{vhost}?" \
                              "{ssl_params}&server_name_indication={host}".format(
                        host=host,
                        port=upstream['port'],
                        vhost=upstream['virtual-host'],
                        ssl_params=ssl_params)
                else:
                    address = "amqp://{user}:{pwd}@{host}:{port}/" \
                              "{vhost}".format(
                        user=admin_user,
                        pwd=admin_password,
                        host=host,
                        port=upstream['port'],
                        vhost=upstream['virtual-host'])
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


def _create_shovel_setup(admin_user, admin_password, is_ssl, instance_name, vhost, vhome):
    """
    Create RabbitMQ shovel based on the RabbitMQ config
    :return:
    """
    shovel_config_file = os.path.join(vhome,
                                      'rabbitmq_shovel_config.yml')
    shovel_config = _read_config_file(shovel_config_file)
    shovels = shovel_config.get('shovel', [])

    rmq_mgmt = RabbitMQMgmt()
    src_uri = rmq_mgmt.build_rmq_address(is_ssl)
    ssl_params = None

    if is_ssl:
        ssl_params = rmq_mgmt.get_ssl_url_params()

    try:
        for host, shovel in shovels.iteritems():
            # Build destination address
            if is_ssl:
                dest_uri = "amqps://{host}:{port}/{vhost}?" \
                           "{ssl_params}&server_name_indication={host}".format(
                    host=host,
                    port=shovel['port'],
                    vhost=shovel['virtual-host'],
                    ssl_params=ssl_params)
            else:
                dest_uri = "amqp://{user}:{pwd}@{host}:{port}/{vhost}".format(
                    user=admin_user,
                    pwd=admin_password,
                    host=host,
                    port=shovel['port'],
                    vhost=shovel['virtual-host'])

            pubsub_topics = shovel.get("pubsub-topics", [])
            agent_ids = shovel.get("rpc-agent-identities", [])
            for topic in pubsub_topics:
                _log.debug("Creating shovel to forward PUBSUB topic {}".format(
                    topic))
                name = "shovel-{host}-{topic}".format(host=host,
                                                      topic=topic)
                routing_key = "__pubsub__.{instance}.{topic}.#".format(
                    instance=rmq_mgmt.rmq_config.instance_name,
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
                _log.debug("shovel property: {}".format(prop))
                rmq_mgmt.set_parameter("shovel",
                                       name,
                                       prop)

            for identity in agent_ids:
                _log.info("Creating shovel to make RPC call to remote Agent"
                          ": {}".format(topic))
                name = "shovel-{host}-{identity}".format(host=host,
                                                         identity=identity)
                routing_key = "{instance}.{identity}.#".format(
                    instance=instance_name,
                    identity=identity)
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


def _setup_for_ssl_auth(rmq_config):
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
    instance_ca_name, server_name, admin_client_name = \
        certs.Certs.get_cert_names(rmq_config.instance_name)

    # prompt for host before creating certs as it is needed for server cert
    _create_certs_without_prompt(rmq_config, admin_client_name, server_name)

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
        mgmt_port_ssl=rmq_config.mgmt_port_ssl,
        amqp_port_ssl=rmq_config.amqp_port_ssl,
        ca=rmq_config.crts.cert_file(rmq_config.crts.trusted_ca_name),
        server_cert=rmq_config.crts.cert_file(server_name),
        server_key=rmq_config.crts.private_key_file(server_name)
    )
    vhome = get_home()
    with open(os.path.join(vhome, "rabbitmq.conf"), 'w') as rconf:
        rconf.write(new_conf)

    # Stop server, move new config file with ssl params, start server
    stop_rabbit(rmq_config.rmq_home)

    os.rename(os.path.join(vhome, "rabbitmq.conf"),
              os.path.join(rmq_config.rmq_home,
                           "etc/rabbitmq/rabbitmq.conf"))
    start_rabbit(rmq_config.rmq_home)
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
                         root_ca=rmq_config.crts.cert_file(rmq_config.crts.root_ca_name),
                         trusted_ca=rmq_config.crts.cert_file(rmq_config.crts.trusted_ca_name),
                         vhome=vhome))


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


def check_rabbitmq_running(rmq_home):
    """
        Start RabbitMQ server
        :param rmq_home: RabbitMQ installation path
        :return:
    """
    running = True
    cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"), "status"]

    try:
        subprocess.check_call(cmd,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        running = False
    return running

def start_rabbit(rmq_home):
    """
    Start RabbitMQ server
    :param rmq_home: RabbitMQ installation path
    :return:
    """
    cmd = [os.path.join(rmq_home, "sbin/rabbitmq-server"),
           "-detached"]
    subprocess.check_call(cmd)
    gevent.sleep(5)
    cmd = [os.path.join(rmq_home, "sbin/rabbitmqctl"), "status"]
    i = 5
    started = False
    while not started:
        try:
            subprocess.check_call(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            gevent.sleep(5)  # give a few seconds for all plugins to startup
            started = True
            _log.info("Started rmq server at {}".format(rmq_home))
        except subprocess.CalledProcessError as e:
            if i > 60:  # if more than a minute, may be somthing is wrong
                raise e
            else:
                # sleep for another 5 seconds and check status again
                gevent.sleep(5)
                i = i + 5


def _create_certs_without_prompt(rmq_config, admin_client_name, server_cert_name):
    """
    Utility method to create certificates
    :param client_cert_name: client (agent) cert name
    :param instance_ca_name: VOLTTRON instance name
    :param server_cert_name: RabbitMQ sever name
    :return:
    """

    crts = rmq_config.crts
    if rmq_config.crts.ca_exists():
        prompt = "Found {}\n Creating a new Root CA will invalidate any " \
                 "existing agent certificate. Do you want to create a " \
                 "new Root CA.".format(crts.cert_file(crts.root_ca_name))
        prompt = prompt_response(prompt,
                                 valid_answers=y_or_n,
                                 default='Y')
        if prompt not in y:
            exit(1)

    _log.info('\n Creating root ca for volttron instance: {}'.format(
        crts.cert_file(crts.root_ca_name)))
    cert_data = rmq_config.certificate_data
    if not cert_data or not all(k in cert_data
                                for k in ['country',
                                          'state',
                                          'location',
                                          'organization',
                                          'organization-unit',
                                          'common-name']):
        raise ValueError(
            "No certificate data found in {}. Please refer to example "
            "config at examples/configurations/rabbitmq/rabbitmq_config.yml"
            " to see list of ssl certificate data to be configured".format(
                rmq_config.volttron_rmq_config))
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

    crts.create_ca_signed_cert(server_cert_name, type='server',
                               fqdn=rmq_config.hostname)

    crts.create_ca_signed_cert(admin_client_name, type='client')


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


def setup_rabbitmq_volttron(setup_type, verbose=False, prompt=False):
    """
    Setup VOLTTRON instance to run with RabbitMQ message bus.
    :param setup_type:
            single - Setup to run as single instance
            federation - Setup to connect multiple VOLTTRON instances as
                         a federation
            shovel - Setup shovels to forward local messages to remote instances
    :return:
    """
    instance_name = get_platform_instance_name(prompt=True)
    # Store config this is checked at startup
    store_message_bus_config(message_bus='rmq', instance_name=instance_name)

    rmq_config = RMQConfig()
    if verbose:
        _log.setLevel(logging.DEBUG)
        _log.debug("verbose set to True")
        _log.debug(get_home())

    if prompt:
        # ignore any existing rabbitmq_config.yml in vhome. Prompt user and
        # generate a new rabbitmq_config.yml
        _create_rabbitmq_config(rmq_config, setup_type)

    # Load either the newly created config or config passed
    try:
        rmq_config.load_rmq_config()
    except (IOError, yaml.YAMLError) as exc:
        _log.error("\nFor single setup, configuration file must at least "
                   "contain host and ssl certificate details. For federation "
                   "and shovel setup, config should contain details about the "
                   "volttron instance with which communication needs "
                   "to be established. Please refer to example config file "
                   "at examples/configurations/rabbitmq/rabbitmq_config.yml")
        return exc

    invalid = True
    if setup_type in ["all", "single"]:
        invalid = False
        _start_rabbitmq_without_ssl(rmq_config)
        _log.debug("Creating rabbitmq virtual hosts and required users for "
                   "volttron")
        # Create local RabbitMQ setup - vhost, exchange etc.
        # should be called after _start_rabbitmq_without_ssl
        rmq_mgmt = RabbitMQMgmt()
        success = rmq_mgmt.init_rabbitmq_setup()
        if success and rmq_config.is_ssl:
            _setup_for_ssl_auth(rmq_config)

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
                                "rabbit@" +
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
        _create_shovel_setup(rmq_config.admin_user,
                             rmq_config.admin_pwd,
                             rmq_config.is_ssl,
                             rmq_config.instance_name,
                             rmq_config.virtual_host,
                             rmq_config.volttron_home)
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

        rmq_config.is_ssl = _prompt_ssl()

        if rmq_config.is_ssl:
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
            prompt = '\tCommon Name:'
            cert_data['common-name'] = prompt_response(
                prompt, default=rmq_config.instance_name + '-root-ca')
            rmq_config.certificate_data = cert_data

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

            if rmq_config.is_ssl == "true":
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
    federation_config_file = os.path.join(vhome, 'rabbitmq_federation_config.yml')
    federation_config = _read_config_file(federation_config_file)

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
    shovel_config = _read_config_file(shovel_config_file)

    shovels = shovel_config.get('shovels', {})
    prompt = 'Number of destination hosts to configure:'
    count = prompt_response(prompt, default=1)
    count = int(count)
    i = 0

    for i in range(0, count):
        prompt = 'Hostname of the destination server: '
        host = prompt_response(prompt, mandatory=True)
        prompt = 'Port of the destination server: '
        port = prompt_response(prompt, default=5671)
        prompt = 'Virtual host of the destination server: '
        vhost = prompt_response(prompt, default='volttron')
        shovels[host] = {'port': port,
                         'virtual-host': vhost}
        prompt = prompt_response('\nDo you want shovels for '
                                 'PUBSUB communication? ',
                                 valid_answers=y_or_n,
                                 default='N')

        if prompt in y:
            prompt = 'List of PUBSUB topics to publish to ' \
                     'this remote instance (comma seperated)'
            topics = prompt_response(prompt, mandatory=True)
            topics = topics.split(",")
            shovels[host]['pubsub-topics'] = topics
        prompt = prompt_response(
            '\nDo you want shovels for RPC communication? ',
            valid_answers=y_or_n, default='N')
        if prompt in y:
            prompt = 'List of identities of remote agents (comma separated)'
            agent_ids = prompt_response(prompt, mandatory=True)
            agent_ids = agent_ids.split(",")
            shovels[host]['rpc-agent-identities'] = agent_ids

    shovel_config['shovel'] = shovels
    _write_to_config_file(shovel_config_file, shovel_config)


def _read_config_file(filename):
    data = {}
    try:
        with open(filename, 'r') as yaml_file:
            data = yaml.load(yaml_file)
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
