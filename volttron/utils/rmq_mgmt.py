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
from ConfigParser import ConfigParser

import grequests
import requests
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)

from volttron.platform import get_home
from volttron.platform.agent import json as jsonapi
from volttron.platform.agent.utils import load_platform_config, \
    store_message_bus_config
from volttron.platform.instance_setup import is_valid_port
from volttron.utils.persistance import PersistentDict
from volttron.utils.prompt import prompt_response, y, n, y_or_n
from volttron.platform.packaging import create_ca
_log = logging.getLogger(__name__)
from volttron.platform.certs import DEFAULT_CERTS_DIR

config_opts = {}

def http_put_request(url, body=None, user=None, password=None):
    user = user if user else get_user()
    password = password if password else get_password()

    try:
        headers = {"Content-Type": "application/json"}
        if body:
            req = grequests.put(url, data=jsonapi.dumps(body), headers=headers, auth=(user, password))
        else:
            req = grequests.put(url, headers=headers, auth=(user, password))
        response = grequests.map([req])
        #print response
        response[0].raise_for_status()
    except (ConnectionError, NewConnectionError):
        print ("Connection to {} not available".format(url))
        response = None
    except requests.exceptions.HTTPError as e:
        print("Exception when trying to make HTTP request to RabbitMQ {}".format(e))
        response = None
    return response

def http_delete_request(url, user=None, password=None):
    user = user if user else get_user()
    password = password if password else get_password()
    response = None
    try:
        headers = {"Content-Type": "application/json"}
        req = grequests.delete(url, headers=headers, auth=(user, password))
        response = grequests.map([req])
        if response and isinstance(response, list):
            response[0].raise_for_status()
    except (ConnectionError, NewConnectionError):
        print("Connection to {} not available".format(url))
    except requests.exceptions.HTTPError as e:
        print("Exception when trying to make HTTP request to RabbitMQ {}".format(e))
    return response

def http_get_request(url, user=None, password=None):
    user = user if user else get_user()
    password = password if password else get_password()
    response = None
    try:
        headers = {"Content-Type": "application/json"}
        req = grequests.get(url, headers=headers, auth=(user, password))
        response = grequests.map([req])

        if response and isinstance(response, list):
            response[0].raise_for_status()
            response = response[0].json()

    except (ConnectionError, NewConnectionError):
        print("Connection to {} not available".format(url))
    except requests.exceptions.HTTPError as e:
        print("Exception when trying to make HTTP request to RabbitMQ {}".format(e))
    return response

def http_get_rrrrequest(url, user, password):
    response = None
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.get(url, headers=headers, auth=(user, password))
        print response
    except (ConnectionError, NewConnectionError):
        print("Connection to {} not available".format(url))
    except requests.exceptions.HTTPError as e:
        print("Exception when trying to make HTTP request to RabbitMQ {}".format(e))
    return response


def _load_rmq_config():
    """Loads the config file if the path exists."""
    global config_opts
    if not os.path.exists(get_home()):
        os.makedirs(get_home())
    config_file = os.path.join(get_home(), 'rabbitmq_config.json')
    config_opts = PersistentDict(filename=config_file, flag='c', format='json')

def get_hostname():
    if not config_opts:
        _load_rmq_config()
    _log.debug("rmq config: {}".format(config_opts))
    return config_opts['host']

def get_port():
    return 15672

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

def create_vhost(vhost='volttron'):
    """
    Create a new virtual host
    :param vhost: virtual host
    :return:
    """
    print "Creating new VIRTUAL HOST: {}".format(vhost)
    url = 'http://localhost:{0}/api/vhosts/{1}'.format(get_port(), vhost)
    response = http_put_request(url, body={}, user='guest', password='guest')

def get_virtualhost(new_vhost, user=None, password=None):
    user = user if user else get_user()
    password = password if password else get_password()
    url = 'http://{0}:{1}/api/vhosts/{2}'.format(get_hostname(), get_port(), new_vhost)
    response = http_get_request(url, user, password)
    return response

def delete_vhost(vhost, user=None, password=None):
    """
    Delete a virtual host
    :param vhost: virtual host
    :param user: username
    :param password: password
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    url = 'http://{0}:{1}/api/vhosts/{2}'.format(get_hostname(), get_port(), vhost)
    response = http_delete_request(url, user, password)

def get_virtualhosts(user=None, password=None):
    user = user if user else get_user()
    password = password if password else get_password()
    url = 'http://{0}:{1}/api/vhosts'.format(get_hostname(), get_port())
    response = http_get_request(url, user, password)
    vhosts = []
    if response:
        vhosts = [v['name'] for v in response]
    return vhosts

#USER - CREATE, GET, DELETE user, SET/GET Permissions
def create_user(user=None, password=None):
    """
    Create a new RabbitMQ user
    :param user: username
    :param password: password
    :return:
    """
    print "Creating new USER: {}".format(user)
    body = dict(password=password, tags="administrator")
    url = 'http://localhost:{0}/api/users/{1}'.format(get_port(), user)
    response = http_put_request(url, body, 'guest', 'guest')

def get_user_props(user):
    """
    Get properties of the user
    :param user: username
    :return:
    """
    url = 'http://{0}:{1}/api/users/{2}'.format(get_hostname(), get_port(), user)
    response = http_get_request(url)
    return response

def delete_user(user):
    """
    Delete specific user
    :param user: user
    :return:
    """
    url = 'http://{0}:{1}/api/users/{2}'.format(get_hostname(), get_port(), user)
    response = http_delete_request(url)

def get_user_permissions(user, password, vhost=None):
    """
    Get permissions (configure, read, write) for the user
    :param user: user
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/permissions/{2}/{3}'.format(get_hostname(), get_port(), vhost, user)
    response = http_get_request(url, )
    return response


# {"configure":".*","write":".*","read":".*"}
def set_user_permissions(permissions, user, password, vhost=None):
    """
    Set permissions for the user
    :param permissions: dict containing configure, read and write settings
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    print "Create READ, WRITE and CONFIGURE permissions for the user: {}".format(user)
    url = 'http://{0}:{1}/api/permissions/{2}/{3}'.format(get_hostname(), get_port(), vhost, user)
    response = http_put_request(url, body=permissions, user=user, password=password)

# SET permissions on topic
def set_topic_permissions(permissions, user, password, vhost=None):
    """
    Set read, write permissions for a topic
    :param permissions: dict containing exchange name and read/write permissions
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/topic-permissions/{2}/{3}'.format(get_hostname(), get_port(), vhost, user)
    response = http_put_request(url, body=permissions, user=user, password=password)

def get_topic_permissions(user, password, vhost=None):
    """
    Get permissions for all topics
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/topic-permissions/{2}/{3}'.format(get_hostname(), get_port(), vhost, user)
    response = http_get_request(url, user, password)
    return response.json() if response else response


# GET/SET parameter on a component for example, federation-upstream
def get_parameter(component, user=None, password=None, vhost=None):
    """
    Get component parameters, namely federation-upstream
    :param component: component name
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/parameters/{2}/{3}'.format(get_hostname(), get_port(), component, vhost)
    response = http_get_request(url, user, password)
    return response

def set_parameter(component, parameter_name, parameter_properties,
                  user=None, password=None, vhost=None):
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
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/parameters/{2}/{3}/{4}'.format(get_hostname(),
                                                             get_port(),
                                                             component,
                                                             vhost,
                                                             parameter_name)
    response = http_put_request(url, body=parameter_properties, user=user, password=password)

def delete_parameter(component, parameter_name,
                     user=None, password=None, vhost=None):
    """
    Delete a component parameter
    :param component: component name
    :param parameter_name: parameter
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/parameters/{2}/{3}/{4}'.format(get_hostname(),
                                                             get_port(),
                                                             component,
                                                             vhost,
                                                             parameter_name)
    response = http_delete_request(url, user, password)
    return response

# Get all policies, Get/Set/Delete a specific property
def get_policies(user=None, password=None, vhost=None):
    """
    Get all policies
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/policies/{2}'.format(get_hostname(),
                                                   get_port(),
                                                   vhost)
    response = requests.get(url, auth=(user, password))
    return response.json() if response else response


def get_policy(name, user=None, password=None, vhost=None):
    """
    Get a specific policy
    :param name: policy name
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/policies/{2}/{3}'.format(get_hostname(),
                                                       get_port(),
                                                       vhost,
                                                       name)
    response = http_get_request(url, user, password)
    if response: return response.json()
    else: return response

# value = {"pattern":"^amq.", "definition": {"federation-upstream-set":"all"}, "priority":0, "apply-to": "all"}
def set_policy(name, value, user=None, password=None, vhost=None):
    """
    Set a policy. For example a federation policy
    :param name: policy name
    :param value: policy value
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/policies/{2}/{3}'.format(get_hostname(), get_port(), vhost, name)
    response = http_put_request(url, body=value, user=user, password=password)

def delete_policy(name, user=None, password=None, vhost=None):
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/policies/{2}/{3}'.format(get_hostname(), get_port(), vhost, name)
    response = http_delete_request(url, user, password)

# Exchanges - Create/delete/List exchanges
#properties = dict(durable=False, type='topic', auto_delete=True, arguments={"alternate-exchange": "aexc"})
# properties = dict(durable=False, type='direct', auto_delete=True)
def create_exchange(exchange, properties, user=None, password=None, vhost=None):
    """
    Create a new exchange
    :param exchange: exchange name
    :param properties: dict containing properties
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    print "Create new exchange: {}".format(exchange)
    url = 'http://%s:%s/api/exchanges/%s/%s' % (get_hostname(), get_port(), vhost, exchange)
    response=http_put_request(url, body=properties, user=user, password=password)

def delete_exchange(exchange, user=None, password=None, vhost=None):
    """
    Delete a exchange
    :param exchange: exchange name
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://%s:%s/api/exchanges/%s/%s' % (get_hostname(), get_port(), vhost, exchange)
    response = http_delete_request(url)

def get_exchanges(user=None, password=None, vhost=None):
    """
    List all exchanges
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://%s:%s/api/exchanges/%s' % (get_hostname(), get_port(), vhost)
    response = http_get_request(url, user, password)
    exchanges = []

    if response:
        exchanges = [e['name'] for e in response]
    return exchanges

def get_exchanges_with_props(user=None, password=None, vhost=None):
    """
    List all exchanges with properties
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://%s:%s/api/exchanges/%s' % (get_hostname(), get_port(), vhost)
    return http_get_request(url, user, password)

# Queues - Create/delete/List queues
#properties = dict(durable=False, auto_delete=True)
def create_queue(queue, properties, user=None, password=None, vhost=None):
    """
    Create a new queue
    :param queue: queue
    :param properties: dict containing properties
    :param vhost:
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/queues/{2}/{3}'.format(get_hostname(), get_port(), vhost, queue)
    response = http_put_request(url, body=properties, user=user, password=password)


def delete_queue(queue, user=None, password=None, vhost=None):
    """
    Delete a queue
    :param queue: queue
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/queues/{2}/{3}'.format(get_hostname(), get_port(), vhost, queue)
    response = http_delete_request(url, user, password)

def get_queues(user=None, password=None, vhost=None):
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
    url = 'http://%s:%s/api/queues/%s' % (get_hostname(), get_port(), vhost)
    response = http_get_request(url, user, password)
    queues = []
    if response:
        queues = [q['name'] for q in response]
    return queues

def get_queues_with_props(user=None, password=None, vhost=None):
    """
    Get properties of all queues
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://%s:%s/api/queues/%s' % (get_hostname(), get_port(), vhost)
    return http_get_request(url, user, password)

# List all open connections
def get_connections(user=None, password=None, vhost=None):
    """
    Get all connections
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    vhost = vhost if vhost else get_vhost()
    url = 'http://{0}:{1}/api/vhosts/{2}/connections'.format(get_hostname(), get_port(), vhost)
    response = http_get_request(url, user, password)
    return response

def get_connection(name, user=None, password=None):
    """
    Get status of a connection
    :param name: connection name
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()

    url = 'http://{0}:{1}/api/connections/{2}'.format(get_hostname(), get_port(), name)
    response = http_get_request(url, user, password)
    return response.json() if response else response

def delete_connection(name, user=None, password=None):
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
    user = user if user else get_user()
    password = password if password else get_password()
    url = 'http://{0}:{1}/api/connections/{2}'.format(get_hostname(), get_port(), name)
    response = http_delete_request(url, user, password)


# List all open channels for a given channel
def list_channels_for_connection(connection, user=None, password=None):
    user = user if user else get_user()
    password = password if password else get_password()
    url = 'http://{0}:{1}/api/connections/{2}/channels'.format(get_hostname(), get_port(), connection)
    return http_get_request(url, user, password)

def list_channels_for_vhost(host, port, user=None, password=None, vhost=None):
    """
    List all open channels for a given vhost
    :param host:
    :param port:
    :param user:
    :param password:
    :param vhost:
    :return:
    """
    user = user if user else get_user()
    password = password if password else get_password()
    url = 'http://{0}:{1}/api/vhosts/{2}/channels'.format(host, port, vhost)
    response = http_get_request(url, user, password)
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
    url = 'http://%s:%s/api/exchanges/%s/%s/bindings/source' % (get_hostname(), get_port(), get_vhost(), exchange)
    response = http_get_request(url)
    # if isinstance(response, list):
    #     response = response[0]
    return response

# We need http address and port
def create_rabbitmq_setup():
    """
    Create a RabbitMQ setup for VOLTTRON
     - Creates a new virtual host: “volttron”
     - Creates a new admin user: “volttron”
     - Creates a new topic exchange: “volttron” and
      alternate exchange “undeliverable” to capture unrouteable messages

    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()
    vhost = config_opts['virtual-host']
    user= config_opts['user']
    password = config_opts['pass']

    # Create a new "volttron" vhost
    create_vhost(vhost)
    # Create a new "volttron" user within this vhost
    create_user(user, password)
    # Set permissions (Configure, read, write) for the user
    permissions = dict(configure=".*", read=".*", write=".*")
    set_user_permissions(permissions, user, password, vhost)
    # we may need to restart RabbitMQ app

    exchange = 'volttron'
    alternate_exchange = 'undeliverable'
    # Create a new "volttron" exchange. Set up alternate exchange to capture all unroutable messages
    properties = dict(durable=True, type='topic', arguments={"alternate-exchange": alternate_exchange})
    create_exchange(exchange, properties=properties, vhost=vhost)

    # Create alternate exchange to capture all unroutable messages.
    # Note: Pubsub messages with no subscribers are also captured which is unavoidable with this approach
    properties = dict(durable=True, type='fanout')
    create_exchange(alternate_exchange, properties=properties, vhost=vhost)

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
    parametrs = get_parameter('federation-upstream')

    for upstream in federation:
        name = upstream['upstream_name']

        address = upstream['upstream_address']
        property = dict(vhost=config_opts['virtual_host'],
                        component="federation-upstream",
                        name=name,
                        value={"uri":address})
        set_parameter('federation-upstream', name, property,
                  config_opts['user'], config_opts['pass'], config_opts['virtual-host']
                  )

    policy_name = 'volttron-federation'
    policy_value = {"pattern":"^volttron",
                    "definition": {"federation-upstream-set":"all"},
                    "priority":0,
                    "apply-to": "exchanges"}
    set_policy(policy_name, policy_value,
              config_opts['user'], config_opts['pass'], config_opts['virtual-host'])

def is_valid_port(port):
    try:
        port = int(port)
    except ValueError:
        return False

    return port == 5672 or port == 5671


def _get_vhost_user_address():
    global config_opts
    _load_rmq_config()
    # Get vhost
    vhost = config_opts.get('virtual-host', 'volttron')
    prompt = 'What is the name of the virtual host under which Rabbitmq VOLTTRON will be running?'
    new_vhost = prompt_response(prompt, default=vhost)
    config_opts['virtual-host'] = new_vhost
    config_opts.async_sync()
    # Get username
    user = config_opts.get('user', 'volttron')
    pwd = config_opts.get('pass', 'volttron')

    prompt = 'What is the username for RabbitMQ VOLTTRON instance?'
    new_user = prompt_response(prompt, default=user)
    config_opts['user'] = new_user
    config_opts.async_sync()

    prompt = 'What is password?'
    new_pwd = prompt_response(prompt, default=pwd)
    config_opts['pass'] = new_pwd
    config_opts.async_sync()

    # Check if host and port is already available
    host = config_opts.get('host', 'localhost')
    port = config_opts.get('port', 5672)

    prompt = 'What is the hostname of system?'
    new_host = prompt_response(prompt, default=host)
    prompt = 'What is the instance port for the RabbitMQ address?'
    valid_port = False
    while not valid_port:
        port = prompt_response(prompt, default=port)
        valid_port = is_valid_port(port)
        if not valid_port:
            print("Port is not valid")
    config_opts['host'] = new_host
    config_opts['port'] = str(port)
    config_opts['rmq-address'] = build_rmq_address(new_user, new_pwd)
    config_opts.async_sync()
    #print config_opts


def build_rmq_address(user=None, pwd=None):
    global config_opts
    if not config_opts:
        _load_rmq_config()
    user = user if user else get_user()
    pwd = pwd if pwd else get_password()
    try:
        rmq_address = "amqp://{0}:{1}@{2}:{3}/{4}".format(user,
                                                          pwd,
                                                          config_opts['host'],
                                                          config_opts['port'],
                                                          config_opts['virtual-host'])
    except KeyError:
        print "Missing entries in rabbitmq config"

    return rmq_address


def _is_valid_rmq_url():
    """
    upstream-address: "amqp://<user1>:<password1>@<host1>:<port1>/<vhost1>"

    #amqp://username:password@host:port/<virtual_host>[?query-string]
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
    federation = config_opts.get('federation', [])
    multi_platform = True

    prompt = prompt_response('\nDo you want a multi-platform federation setup? ',
                                valid_answers=y_or_n,
                                default='N')
    if prompt in n:
        multi_platform = False
    if multi_platform:
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
            port = prompt_response(prompt, default=5672)
            prompt = 'Virtual host of the upstream server: '
            vhost = prompt_response(prompt, default='volttron')
            prompt = 'Username of the upstream server: '
            user = prompt_response(prompt, default='volttron')
            prompt = 'Password of the upstream server: '
            pwd = prompt_response(prompt, default='volttron')
            address = "amqp://{0}:{1}@{2}:{3}/{4}".format(user, pwd, host, port, vhost)
            federation.append(dict(upstream_name=name, upstream_address=address))
        config_opts['federation'] = federation
        print config_opts
        config_opts.sync()
    return multi_platform


def _get_shovel_settings():
    global config_opts
    if not config_opts:
        _load_rmq_config()
    shovels = []
    shovels = config_opts.get('shovels', [])
    multi_platform = True
    prompt = prompt_response('\nDo you want a multi-platform shovel setup? ',
                                         valid_answers=y_or_n,
                                         default='N')
    if prompt in n:
        multi_platform = False
    if multi_platform:
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
            port = prompt_response(prompt, default=5672)
            prompt = 'Virtual host of the destination server: '
            vhost = prompt_response(prompt, default='volttron')
            prompt = 'Username of the destination server: '
            user = prompt_response(prompt, default='volttron')
            prompt = 'Password of the destination server: '
            pwd = prompt_response(prompt, default='volttron')
            address = "amqp://{0}:{1}@{2}:{3}/{4}".format(user, pwd, host, port, vhost)
            prompt = 'List of pubsub topics to publish to remote instance (comma seperated)'
            topics = prompt_response(prompt, default="")
            topics = topics.split(",")
            shovels.append(dict(shovel_name=name, remote_address=address, topics=topics))
        config_opts['shovels'] = shovels
        config_opts.sync()
    return multi_platform


def create_shovel_setup():
    if not config_opts:
        _load_rmq_config()
        return
    platform_config = load_platform_config()
    try:
        instance_name = platform_config['instance-name'].strip('"')
        print(instance_name)
    except KeyError as exc:
        print("Unknown instance name. Please set instance-name in VOLTTRON_HOME/config")
        return
    shovels = config_opts.get('shovels', [])
    src_uri = build_rmq_address()
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
    print('\nYour VOLTTRON_HOME currently set to: {}'.format(get_home()))
    prompt = '\nIs this the volttron instance you are attempting to ' \
             'configure rabbitmq for? '
    if not prompt_response(prompt, valid_answers=y_or_n, default='Y') in y:
        print(
            '\nPlease execute with VOLTRON_HOME=/your/path python '
            'volttron/utils/rmq_mgmt.py to  '
            'modify VOLTTRON_HOME.\n')
        return

    store_message_bus_config()
    print('\nChecking for CA certificate\n')
    # create ca cert in default dir if it doesn't exists
    create_ca(override=False)

    if type == 'single':
        # # Get vhost from the user
        _get_vhost_user_address()
        # Create local RabbitMQ setup
        create_rabbitmq_setup()
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('type', help='Instance type: single, federation or shovel')
    args = parser.parse_args()
    type = args.type
    try:
        wizard(type)
    except KeyboardInterrupt:
        print "Exiting setup process"




