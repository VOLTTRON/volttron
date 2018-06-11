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
    RabbitMQ HTTP management utility methods to
    1. Create/Delete virtual hosts for each platform
    2. Create/Delete user for each agent
    3. Set/Get permissions for each user
    4. Create/Delete exchanges
    5. Create/Delete queues
    6. Create/List/Delete federation upstream servers
    7. Create/List/Delete federation upstream policies
    8. and shovel setup for multi-platform deployment.
    9. Set topic permissions for protected topics
    10. List the status of
        Open Connections
        Exchanges
        Queues
        Queue to exchange bindings
"""

import argparse
import logging
import os
import ssl
from socket import getfqdn

import grequests
import pika
import requests
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)

from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent import json as jsonapi
from volttron.platform.agent.utils import load_platform_config, \
    store_message_bus_config, get_platform_instance_name
from volttron.platform.packaging import create_ca
from volttron.utils.persistance import PersistentDict
from volttron.utils.prompt import prompt_response, y, n, y_or_n
from volttron.platform.certs import ROOT_CA_NAME

_log = logging.getLogger(__name__)

config_opts = {}
default_pass = "default_passwd"
crts = certs.Certs()
instance_name = None
local_user ="guest"
local_password="guest"
admin_user= None # User to prompt for if we go the docker route
admin_password= None

volttron_rmq_config = os.path.join(get_home(), 'rabbitmq_config.json')

def call_grequest(method_name, url_suffix, ssl=True, **kwargs):
    global crts, instance_name
    url = get_url_prefix(ssl) + url_suffix
    kwargs["headers"] = {"Content-Type": "application/json"}
    auth_args = get_authentication_args(ssl)
    kwargs.update(auth_args)
    try:
        fn = getattr(grequests, method_name)
        request = fn(url, **kwargs)
        response = grequests.map([request])
        if response and isinstance(response, list):
            response[0].raise_for_status()
    except (ConnectionError, NewConnectionError):
        print ("Connection to {} not available".format(url))
        response = None
    except requests.exceptions.HTTPError as e:
        print("Exception when trying to make HTTP request "
              "to RabbitMQ {}".format(e))
        response = None
    return response

def get_authentication_args(ssl):
    '''
    Return authentication kwargs for request/greqeust
    :param ssl: if True returns cert and verify parameters in addition to auth
    :return: dictionary containing auth/cert args need to pass to
    request/grequest methods
    '''
    global local_user, local_password, admin_user, admin_password, instance_name

    if ssl:
        instance_ca, server_cert, client_cert = get_cert_names(instance_name)
        admin_user = config_opts.get("user")
        if admin_password is None:
            prompt = 'What is the password for user({}):'
            admin_password = prompt_response(prompt)
        return {'auth': (admin_user, admin_password), 'verify': crts.cert_file(
            instance_ca),
                'cert': (crts.cert_file(client_cert),
                         crts.private_key_file(client_cert))}
    else:
        password = local_user
        user = local_password
        return {'auth': (user, password)}

def http_put_request(url_suffix, body=None, ssl=True):
    if body:
        return call_grequest('put', url_suffix, ssl, data=jsonapi.dumps(body))
    else:
        return call_grequest('put', url_suffix, ssl)

def http_delete_request(url, ssl=True):
    return call_grequest('delete',url, ssl)

def http_get_request(url, ssl=True):
    response = call_grequest('get', url, ssl)
    if response and isinstance(response, list):
        response = response[0].json()
    return response

def _load_rmq_config():
    """Loads the config file if the path exists."""
    global config_opts, volttron_rmq_config
    if not os.path.exists(get_home()):
        os.makedirs(get_home())
    config_opts = PersistentDict(filename=volttron_rmq_config, flag='c',
                                 format='json')

def get_hostname():
    if not config_opts:
        _load_rmq_config()
    _log.debug("rmq config: {}".format(config_opts))
    return config_opts['host']

def get_amqp_port():
    if not config_opts:
        _load_rmq_config()
    _log.debug("rmq config: {}".format(config_opts))
    return config_opts['amqp_port']


def get_port():
    if not config_opts:
        _load_rmq_config()
    _log.debug("rmq config: {}".format(config_opts))
    return config_opts['port']


def get_vhost():
    if not config_opts:
        _load_rmq_config()
    return config_opts['virtual-host']


def get_user():
    if not config_opts:
        _load_rmq_config()
    return config_opts['user']


def get_password():
    if not config_opts:
        _load_rmq_config()
    return config_opts['pass']


def create_vhost(vhost='volttron', ssl=True):
    """
    Create a new virtual host
    :param vhost: virtual host
    :return:
    """
    print "Creating new VIRTUAL HOST: {}".format(vhost)
    url = '/api/vhosts/{vhost}'.format(vhost=vhost)
    response = http_put_request(url, body={}, ssl=ssl)


def get_virtualhost(new_vhost, ssl=True):
    url = '/api/vhosts/{vhost}'.format(vhost=new_vhost)
    response = http_get_request(url, ssl)
    return response

def delete_vhost(vhost, ssl=True):
    """
    Delete a virtual host
    :param vhost: virtual host
    :param user: username
    :param password: password
    :return:
    """
    url = '/api/vhosts/{2}'.format(vhost=vhost)
    response = http_delete_request(url, ssl)

def get_virtualhosts(ssl=True):
    url = '/api/vhosts'
    response = http_get_request(url, ssl)
    vhosts = []
    if response:
        vhosts = [v['name'] for v in response]
    return vhosts


#USER - CREATE, GET, DELETE user, SET/GET Permissions
def create_user(user, password=default_pass, tags="administrator", ssl=True):
    """
    Create a new RabbitMQ user
    :param user:
    :param password:
    :param tags:
    :param ssl:
    :return:
    """
    print "Creating new USER: {}".format(user)
    body = dict(password=password, tags=tags)
    url = '/api/users/{user}'.format(user=user)
    response = http_put_request(url, body, ssl)


def get_url_prefix(ssl):
    if ssl:
        prefix = 'https://{host}:{port}'.format(host=get_hostname(),
                                                port=get_port())
    else:
        prefix = 'http://localhost:{port}'.format(port=get_port())
    return prefix


def get_user_props(user, ssl=True):
    """
    Get properties of the user
    :param user: username
    :return:
    """
    url = '/api/users/{user}'.format(user=user)
    response = http_get_request(url, ssl)
    return response

def delete_user(user, ssl=True):
    """
    Delete specific user
    :param user: user
    :return:
    """
    url = '/api/users/{user}'.format(user=user)
    response = http_delete_request(url, ssl)

def get_user_permissions(user, vhost=None, ssl=True):
    """
    Get permissions (configure, read, write) for the user
    :param user: user
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/permissions/{vhost}/{user}'.format(vhost=vhost,
                                                   user=user)
    response = http_get_request(url, ssl)
    return response


# {"configure":".*","write":".*","read":".*"}
def set_user_permissions(permissions, user, vhost=None, ssl=True):
    """
    Set permissions for the user
    :param permissions: dict containing configure, read and write settings
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    print "Create READ, WRITE and CONFIGURE permissions for the user: " \
          "{}".format(user)
    url = '/api/permissions/{vhost}/{user}'.format(vhost=vhost, user=user)
    response = http_put_request(url, body=permissions, ssl=ssl)



# SET permissions on topic
def set_topic_permissions(permissions, user, vhost=None, ssl=True):
    """
    Set read, write permissions for a topic
    :param permissions: dict containing exchange name and read/write permissions
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/topic-permissions/{vhost}/{user}'.format(vhost=vhost,
                                                         user=user)
    response = http_put_request(url, body=permissions, ssl=ssl)

def get_topic_permissions(user, vhost=None, ssl=True):
    """
    Get permissions for all topics
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/topic-permissions/{vhost}/{user}'.format(vhost=vhost, user=user)
    response = http_get_request(url, ssl)
    return response.json() if response else response


# GET/SET parameter on a component for example, federation-upstream
def get_parameter(component, vhost=None, ssl=True):
    """
    Get component parameters, namely federation-upstream
    :param component: component name
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/parameters/{component}/{vhost}'.format(component=component,
                                                       vhost=vhost)
    response = http_get_request(url, ssl)
    return response

def set_parameter(component, parameter_name, parameter_properties,
                  vhost=None, ssl=True):
    """
    Set parameter on a component
    :param component: component name (for example, federation-upstream)
    :param parameter_name: parameter name
    :param parameter_properties: parameter properties
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    #print "SET PARAMETER. NAME: {0}, properties: {1}, component: {2}".
    # format(parameter_name, parameter_properties, component)
    # user = user if user else get_user()
    # password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = '/api/parameters/{component}/{vhost}/{param}'.format(
        component=component, vhost=vhost, param=parameter_name)
    response = http_put_request(url, body=parameter_properties, ssl=ssl)


def delete_parameter(component, parameter_name, vhost=None, ssl=True):
    """
    Delete a component parameter
    :param component: component name
    :param parameter_name: parameter
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/parameters/{component}/{vhost}/{parameter}'.format(
        component=component, vhost=vhost, parameter=parameter_name)
    response = http_delete_request(url, ssl)
    return response

# Get all policies, Get/Set/Delete a specific property
def get_policies(vhost=None, ssl=True):
    """
    Get all policies
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    # TODO: check -  this is the only request call.. others ar grequest calls
    vhost = vhost if vhost else get_vhost()
    prefix = get_url_prefix(ssl)
    user, password = get_authentication_args(ssl)
    url = '{prefix}/api/policies/{vhost}'.format(prefix=prefix,
                                                 vhost=vhost)
    kwargs = get_authentication_args(ssl)
    response = requests.get(url, **kwargs)
    return response.json() if response else response


def get_policy(name, vhost=None, ssl=True):
    """
    Get a specific policy
    :param name: policy name
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
    response = http_get_request(url, ssl)
    if response:
        return response.json()
    else:
        return response

# value = {"pattern":"^amq.", "definition": {"federation-upstream-set":"all"}, "priority":0, "apply-to": "all"}
def set_policy(name, value, vhost=None, ssl=True):
    """
    Set a policy. For example a federation policy
    :param name: policy name
    :param value: policy value
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    # user = user if user else get_user()
    # password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
    response = http_put_request(url, body=value, ssl=ssl)

def delete_policy(name, vhost=None, ssl=True):
    vhost = vhost if vhost else get_vhost()
    url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
    response = http_delete_request(url, ssl)

# Exchanges - Create/delete/List exchanges
#properties = dict(durable=False, type='topic', auto_delete=True, arguments={"alternate-exchange": "aexc"})
# properties = dict(durable=False, type='direct', auto_delete=True)
def create_exchange(exchange, properties, vhost=None, ssl=True):
    """
    Create a new exchange
    :param exchange: exchange name
    :param properties: dict containing properties
    :param vhost: virtual host
    :param ssl:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    print "Create new exchange: {}".format(exchange)
    url = '/api/exchanges/{vhost}/{exchange}'.format(vhost=vhost,
                                                     exchange=exchange)
    response = http_put_request(url, body=properties, ssl=ssl)


def delete_exchange(exchange, vhost=None, ssl=True):
    """
    Delete a exchange
    :param exchange: exchange name
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/exchanges/{vhost}/{exchange}'.format(vhost=vhost,
                                                     exchange=exchange)
    response = http_delete_request(url, ssl)

def get_exchanges(vhost=None, ssl=True):
    """
    List all exchanges
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/exchanges/{vhost}'.format(vhost=vhost)
    response = http_get_request(url, ssl)
    exchanges = []

    if response:
        exchanges = [e['name'] for e in response]
    return exchanges

def get_exchanges_with_props(vhost=None, ssl=True):
    """
    List all exchanges with properties
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/exchanges/{vhost}'.format(vhost=vhost)
    return http_get_request(url, ssl)

# Queues - Create/delete/List queues
#properties = dict(durable=False, auto_delete=True)
def create_queue(queue, properties, vhost=None, ssl=True):
    """
    Create a new queue
    :param queue: queue
    :param properties: dict containing properties
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}/{queue}'.format(vhost=vhost, queue=queue)
    response = http_put_request(url, body=properties, ssl=ssl)


def delete_queue(queue, user=None, password=None, vhost=None, ssl=True):
    """
    Delete a queue
    :param queue: queue
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}/{queue}'.format(vhost=vhost, queue=queue)
    response = http_delete_request(url, ssl)

def get_queues(user=None, password=None, vhost=None, ssl=True):
    """
    Get list of queues
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}'.format(vhost=vhost)
    response = http_get_request(url, ssl)
    queues = []
    if response:
        queues = [q['name'] for q in response]
    return queues

def get_queues_with_props(vhost=None, ssl=True):
    """
    Get properties of all queues
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}'.format(vhost=vhost)
    return http_get_request(url, ssl)

# List all open connections
def get_connections(vhost=None, ssl=True):
    """
    Get all connections
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/vhosts/{vhost}/connections'.format(vhost=vhost)
    response = http_get_request(url, ssl)
    return response

def get_connection(name, ssl=True):
    """
    Get status of a connection
    :param name: connection name
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    url = '/api/connections/{name}'.format(name=name)
    response = http_get_request(url, ssl)
    return response.json() if response else response

def delete_connection(name, ssl=True):
    """
    Delete open connection
    :param host:
    :param port:
    :param name:
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    url = '/api/connections/{name}'.format(name=name)
    response = http_delete_request(url, ssl)


# List all open channels for a given channel
def list_channels_for_connection(connection, ssl=True):
    url = '/api/connections/{conn}/channels'.format(conn=connection)
    return http_get_request(url, ssl)

def list_channels_for_vhost(vhost=None, ssl=True):
    """
    List all open channels for a given vhost
    :param host:
    :param port:
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    url = '/api/vhosts/{vhost}/channels'.format(vhost=vhost)
    response = http_get_request(url, ssl)
    return response.json() if response else response

def get_bindings(exchange):
    """
    List all bindings in which a given exchange is the source
    :param exchange: source exchange
    :param user: user id
    :param password: password
    :param vhost: virtual host
    :return: list of bindings
    """
    url = '/api/exchanges/{binding}/{exchange}/bindings/source'.format(
        vhost=get_vhost(), exchange=exchange)
    response = http_get_request(url)
    # if isinstance(response, list):
    #     response = response[0]
    return response

# We need http address and port
def init_rabbitmq_setup():
    """
    Create a RabbitMQ setup for VOLTTRON
     - Creates a new virtual host: “volttron”
     - Creates a new topic exchange: “volttron” and
      alternate exchange “undeliverable” to capture unrouteable messages

    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()
    vhost = config_opts['virtual-host']

    # Create a new "volttron" vhost
    create_vhost(vhost, ssl=False)

    exchange = 'volttron'
    alternate_exchange = 'undeliverable'
    # Create a new "volttron" exchange. Set up alternate exchange to capture
    # all unroutable messages
    properties = dict(durable=True, type='topic',
                      arguments={"alternate-exchange": alternate_exchange})
    create_exchange(exchange, properties=properties, vhost=vhost, ssl=False)

    # Create alternate exchange to capture all unroutable messages.
    # Note: Pubsub messages with no subscribers are also captured which is
    # unavoidable with this approach
    properties = dict(durable=True, type='fanout')
    create_exchange(alternate_exchange, properties=properties, vhost=vhost,
                    ssl=False)

def create_federation_setup():
    """
    Creates a RabbitMQ federation of multiple VOLTTRON instances
        - Firstly, we need to identify upstream servers (publisher nodes)
          and downstream servers (collector nodes)
        - On the downstream server node, we will have run this script
        - Creates upstream server federation parameters.

    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()

    federation = config_opts['federation']

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

def is_valid_port(port):
    try:
        port = int(port)
    except ValueError:
        return False

    return port == 5672 or port == 5671

def set_initial_rabbit_config(instance_name):
    global config_opts
    _load_rmq_config()
    # Get vhost
    vhost = config_opts.get('virtual-host', 'volttron')
    prompt = 'What is the name of the virtual host under which Rabbitmq VOLTTRON will be running?'
    new_vhost = prompt_response(prompt, default=vhost)
    config_opts['virtual-host'] = new_vhost
    prompt = prompt_response('\nUse default rabbitmq configuration ',
                             valid_answers=y_or_n,
                             default='Y')
    if prompt in y:
        config_opts['user'] = "guest"
        config_opts['pass'] = "guest"
        config_opts['host'] = 'localhost'
        config_opts['amqp_port'] = '5672'
        config_opts['port'] = '15672'
        config_opts['rmq-address'] = build_rmq_address(ssl=False)
        config_opts.sync()
    else:
        config_opts['user'] = "guest"
        prompt = 'What is the password for RabbitMQ default guest user?'
        new_pass = prompt_response(prompt, default="guest")
        config_opts['user'] = "guest"
        config_opts['pass'] = new_pass

        # TODO - How to configure port other than 5671 for ssl - validate should
        # check if port is not 5672.
        port = config_opts.get('amqp_port', 5672)
        prompt = 'What is the instance port for the RabbitMQ address?'
        valid_port = False
        while not valid_port:
            port = prompt_response(prompt, default=port)
            valid_port = is_valid_port(port)
            if not valid_port:
                print("Port is not valid")
        config_opts['amqp_port'] = str(port)

        port = config_opts.get('port', 15672)
        prompt = 'What is the instance port for the RabbitMQ management plugin?'
        valid_port = False
        while not valid_port:
            port = prompt_response(prompt, default=port)
            valid_port = is_valid_port(port)
            if not valid_port:
                print("Port is not valid")
        config_opts['port'] = str(port)

        config_opts['rmq-address'] = build_rmq_address(ssl=False)
        config_opts.sync()
        #print config_opts


def build_connection_param(instance_name):
    global config_opts
    if not config_opts:
        _load_rmq_config()

    # ssl_options = {"ca_certs": "/home/velo/.volttron_r/certificates/certs"
    #                            "/volttron-ca.crt",
    #                "ssl_version": ssl.PROTOCOL_TLSv1}
    ssl_options = dict(
                        ssl_version=ssl.PROTOCOL_TLSv1_2,
                        ca_certs=os.path.join(certs.DEFAULT_CERTS_DIR,
                                              "certs",
                                              instance_name+"-ca.crt"),
                        keyfile=os.path.join(certs.DEFAULT_CERTS_DIR,
                                             "private",
                                             config_opts['user']+".pem"),
                        certfile=os.path.join(certs.DEFAULT_CERTS_DIR,
                                              "certs",
                                              config_opts['user']+".crt"),
                        cert_reqs=ssl.CERT_REQUIRED)
    conn_params = pika.ConnectionParameters(
        host=config_opts['host'],
        port=int(config_opts['port']),
        virtual_host=config_opts['virtual-host'],
        ssl=True,
        ssl_options=ssl_options,
        credentials=pika.credentials.ExternalCredentials())
    return conn_params

def build_rmq_address(ssl=True):
    global config_opts
    if not config_opts:
        _load_rmq_config()

    user = get_user()
    pwd = get_password()
    rmq_address = None
    try:
        if ssl:
            # Address format to connect to server-name, with SSL and EXTERNAL
            # authentication
            # amqps://server-name?cacertfile=/path/to/cacert.pem&certfile=/path/to/cert.pem&keyfile=/path/to/key.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external
            rmq_address = "amqps://{host}:{port}/{vhost}?{ssl_params}".format(
                host=config_opts['host'],
                port=config_opts['amqp_port'],
                vhost=config_opts['virtual-host'],
                ssl_params=get_ssl_url_params())
        else:
            rmq_address = "amqp://{0}:{1}@{2}:{3}/{4}".format(
                user, pwd, config_opts['host'], config_opts['amqp_port'],
                config_opts[ 'virtual-host'])
    except KeyError:
        print "Missing entries in rabbitmq config"
        raise

    return rmq_address


def _is_valid_rmq_url():
    """
    upstream-address: "amqps://<user1>:<password1>@<host1>:<port1>/<vhost1>"

    #amqps://username:password@host:port/<virtual_host>[?query-string]
    #Ensure that the virtual host is URI encoded when specified. For example if
    you are using the default "/" virtual host, the value should be `%2f`
    #
    :return:
    """
    pass


def _get_upstream_servers():
    """
    Build RabbitMQ URIs for upstream servers
    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()
    federation = config_opts.get('federation', dict())
    multi_platform = True
    ssl_params = get_ssl_url_params()
    prompt = 'How many upstream servers do you want to configure?'
    count = prompt_response(prompt, default=1)
    count = int(count)
    i = 0
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
        prompt = 'Instance name of upstream server: '
        instance = prompt_response(prompt)
        address = "amqps://{host}:{port}/{vhost}?" \
                  "{ssl_params}".format(instance=instance,
            host=host, port=port, vhost=vhost, ssl_params=ssl_params)
        federation[name] = address
    config_opts['federation'] = federation
    print config_opts
    config_opts.sync()
    return multi_platform


def _get_shovel_settings():
    global config_opts, crts
    if not config_opts:
        _load_rmq_config()
    shovels = []
    shovels = config_opts.get('shovels', [])
    ssl_params = get_ssl_url_params()
    prompt = 'How many shovels do you want to configure?'
    count = prompt_response(prompt, default=1)
    count = int(count)
    i = 0
    for i in range(0, count):
        prompt = 'Name of the shovel: '
        default_name = 'shovel-' + str(count)
        name = prompt_response(prompt, default=default_name)
        prompt = 'Hostname of the destination instance: '
        host = prompt_response(prompt, default='localhost')
        prompt = 'Port of the upstream server: '
        port = prompt_response(prompt, default=5671)
        prompt = 'Virtual host of the destination server: '
        vhost = prompt_response(prompt, default='volttron')
        # prompt = 'Username of the destination server: '
        # user = prompt_response(prompt, default='volttron')
        # prompt = 'Password of the destination server: '
        # pwd = prompt_response(prompt, default='volttron')
        # TODO- Currently using instancename user for all shovel connection to a
        # single volttron instance. Change based on authorization
        prompt = 'Instance name of upstream server: '
        inst = prompt_response(prompt)
        address = "amqps://{host}:{port}/{vhost}?{params}".format(
            host=host, port=port, vhost=vhost,
            params=ssl_params)
        prompt = 'List of pubsub topics to publish to remote instance (comma seperated)'
        topics = prompt_response(prompt, default="")
        topics = topics.split(",")
        shovels.append(dict(shovel_name=name, remote_address=address, topics=topics))
    config_opts['shovels'] = shovels
    config_opts.sync()

def get_ssl_url_params():
    global crts, instance_name
    platform_config = load_platform_config()
    instance_ca, server_cert, client_cert = get_cert_names(instance_name)
    ca_file = crts.cert_file(instance_ca)
    cert_file = crts.cert_file(client_cert)
    key_file = crts.private_key_file(client_cert)
    return "cacertfile={ca}&certfile={cert}&keyfile={key}" \
           "&verify=verify_peer&fail_if_no_peer_cert=true" \
           "&auth_mechanism=external&depth=1".format(ca=ca_file,
                                                     cert=cert_file,
                                                     key=key_file)


def create_shovel_setup():
    global instance_name
    if not config_opts:
        _load_rmq_config()
        return
    platform_config = load_platform_config()
    shovels = config_opts.get('shovels', [])
    src_uri = build_rmq_address(ssl=True)
    for shovel in shovels:
        name = shovel['shovel_name']
        dest_uri = shovel['remote_address']
        topics = shovel['topics']
        for topic in topics:
            pubsub_key = "__pubsub__.{0}.{1}.#".format(instance_name, topic)
            property = dict(vhost=config_opts['virtual-host'],
                        component="shovel",
                        name=name,
                        value={"src-uri":  src_uri,
                                "src-exchange":  "volttron",
                                "src-exchange-key": pubsub_key,
                                "dest-uri": dest_uri,
                                "dest-exchange": "volttron"}
                            )
            set_parameter("shovel",
                          name,
                          property,
                          config_opts['user'],
                          config_opts['pass'],
                          config_opts['virtual-host'])


def wizard(type):
    global instance_name
    # TODO check if rabbitmq-server is running
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
        # # Get vhost from the user
        set_initial_rabbit_config(instance_name)
        # Create local RabbitMQ setup
        init_rabbitmq_setup()
        setup_for_ssl_auth(instance_name)

    elif type == 'federation':
        # Create a federation setup
        federation_needed = _get_upstream_servers()
        if federation_needed:
            create_federation_setup()
    elif type == 'shovel':
        shovel_needed = _get_shovel_settings()
        if shovel_needed:
            create_shovel_setup()
    else:
        print "Unknown option. Exiting...."


def setup_for_ssl_auth(instance_name):
    global config_opts
    print('\nChecking for CA certificate\n')
    instance_ca_name, server_cert_name, client_cert_name = get_cert_names(
        instance_name)

    host = config_opts.get('host', 'localhost')
    prompt = 'What is the fully qualified domain name of the system?'
    new_host = prompt_response(prompt, default=getfqdn())
    config_opts['host'] = new_host

    # prompt for host before creating certs as it is needed for server cert
    create_certs(client_cert_name, instance_ca_name, server_cert_name)

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
        server_cert=crts.cert_file(server_cert_name),
        server_key=crts.private_key_file(server_cert_name)
    )
    with open(os.path.join(get_home(), "rabbitmq.conf"), 'w') as rconf:
        rconf.write(new_conf)



    prompt = 'What is the admin user name:'
    user = prompt_response(prompt, default=instance_name)

    # updated rabbitmq_config.json
    config_opts['user'] = user
    config_opts['pass'] = ""
    config_opts['amqp_port'] = '5671'
    config_opts['port'] = '15671'
    config_opts['rmq-address'] = build_rmq_address(ssl=True)
    config_opts.sync()


    print("\n\n Please do the following to complete setup"
          "\n  1. Provide read access to rabbitmq "
          "user to the certificates and private key files in "
          "VOLTTRON_HOME/certificates/"
          "\n  2. Move the rabbitmq.conf file"
          "in VOLTTRON_HOME directory into your rabbitmq configuration "
          "directory (/etc/rabbitmq in RPM/Debian systems) "
          "\n  3. For custom ssl ports: Generated configuration uses "
          "default rabbitmq ssl ports. Modify both rabbitmq.conf and "
          "VOLTTRON_HOME/rabbitmq_config.json if using different ports. "
          "\n  4. Restart rabbitmq-server. ")


def create_certs(client_cert_name, instance_ca_name, server_cert_name):
    global config_opts
    create_instance_ca = False
    # create ca cert in default dir if needed
    if crts.ca_exists():
        print('\n Found {}'.format(crts.cert_file(ROOT_CA_NAME)))
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
            create_ca(override=False)
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

        found = verify_and_save_instance_ca(instance_ca_path, instance_ca_key)
        while not found:
            if instance_ca_path is not None or instance_ca_key is not None:
                print("\nInvalid instance CA certificate or instance CA "
                      "private key file")
            instance_ca_path = prompt_response('\n Enter path to intermediate '
                                               'CA certificate of this '
                                               'volttron instance:')
            instance_ca_key = prompt_response('\n Enter path to private key '
                                              'file for this instance CA:')
            found = verify_and_save_instance_ca(instance_ca_path,
                                                instance_ca_key)
    crts.create_ca_signed_cert(server_cert_name, type='server',
                               ca_name=instance_ca_name,
                               fqdn=config_opts.get('host'))
    # permissions = dict(configure=".*", read=".*", write=".*")
    # set_user_permissions(permissions, server_cert_name)
    crts.create_ca_signed_cert(client_cert_name, type='client',
                               ca_name=instance_ca_name)
    create_user(client_cert_name, ssl=False)
    permissions = dict(configure=".*", read=".*", write=".*")
    set_user_permissions(permissions, client_cert_name, ssl=False)


def verify_and_save_instance_ca(instance_ca_path, instance_ca_key):
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


def get_cert_names(instance_name=None):
    if not instance_name:
        instance_name = get_platform_instance_name()
    return instance_name + '-ca', instance_name+"-server", instance_name

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('type', help='Instance type: single, federation or shovel')
    args = parser.parse_args()
    type = args.type
    try:
        wizard(type)
    except KeyboardInterrupt:
        print "Exiting setup process"




