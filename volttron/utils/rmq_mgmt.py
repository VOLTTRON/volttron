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

import logging
import os
import ssl

import grequests
import pika
import requests
from requests.packages.urllib3 import disable_warnings, exceptions
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)

from volttron.platform import certs
from volttron.platform import get_home
from volttron.platform.agent import json as jsonapi
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.utils.persistance import PersistentDict

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

# volttron_rmq_config = os.path.join(get_home(), 'rabbitmq_config.json')


def call_grequest(method_name, url_suffix, ssl_auth=True, **kwargs):
    url = get_url_prefix(ssl_auth) + url_suffix
    kwargs["headers"] = {"Content-Type": "application/json"}
    auth_args = get_authentication_args(ssl_auth)
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
        # print("Exception when trying to make HTTP request "
        #       "to RabbitMQ {}".format(e))
        response = None
    except AttributeError as e:
        print("Exception when trying to make HTTP request "
              "to RabbitMQ {}".format(e))
        response = None
    return response


def get_authentication_args(ssl_auth):
    """
    Return authentication kwargs for request/greqeust
    :param ssl_auth: if True returns cert and verify parameters in addition
     to auth
    :return: dictionary containing auth/cert args need to pass to
    request/grequest methods
    """
    global local_user, local_password, admin_user, admin_password, \
        instance_name

    if ssl_auth:
        if not instance_name:
            instance_name = get_platform_instance_name()
        instance_ca, server_cert, client_cert = certs.Certs.get_cert_names(
            instance_name)
        admin_user = get_user()
        if admin_password is None:
            # prompt = 'What is the password for user({}):'.format(admin_user)
            # TODO: figure out how to manage admin user and password. rabbitmq
            # federation plugin doesn't handle external_auth plugin !!
            # One possible workaround is to use plain username/password auth
            # with guest user with localhost. We still have to persist guest
            # password but at least guest user can only access rmq using
            # localhost
            admin_password = default_pass
        return {'auth': (admin_user, admin_password),
                'verify': crts.cert_file(instance_ca),
                'cert': (crts.cert_file(client_cert),
                         crts.private_key_file(client_cert))}
    else:
        password = local_user
        user = local_password
        return {'auth': (user, password)}


def http_put_request(url_suffix, body=None, ssl_auth=True):
    if body:
        return call_grequest('put', url_suffix, ssl_auth,
                             data=jsonapi.dumps(body))
    else:
        return call_grequest('put', url_suffix, ssl_auth)


def http_delete_request(url, ssl_auth=True):
    return call_grequest('delete', url, ssl_auth)


def http_get_request(url, ssl_auth=True):
    response = call_grequest('get', url, ssl_auth)
    if response and isinstance(response, list):
        response = response[0].json()
    return response


def _load_rmq_config(volttron_home=None):
    """Loads the config file if the path exists."""
    global config_opts, volttron_rmq_config
    if not volttron_home:
        volttron_home = get_home()
    if not os.path.exists(volttron_home):
        os.makedirs(volttron_home)
    volttron_rmq_config = os.path.join(volttron_home, 'rabbitmq_config.json')
    config_opts = PersistentDict(filename=volttron_rmq_config, flag='c',
                                 format='json')


def get_hostname():
    if not config_opts:
        _load_rmq_config()
    # _log.debug("rmq config: {}".format(config_opts))
    return config_opts['host']


def get_amqp_port():
    if not config_opts:
        _load_rmq_config()
    # _log.debug("rmq config: {}".format(config_opts))
    return config_opts['amqp-port']


def get_mgmt_port():
    if not config_opts:
        _load_rmq_config()
    # _log.debug("rmq config: {}".format(config_opts))
    return config_opts['mgmt-port']


def get_vhost():
    if not config_opts:
        _load_rmq_config()
    return config_opts['virtual-host']


def get_user():
    if not config_opts:
        _load_rmq_config()
    return config_opts.get('user')


def get_password():
    if not config_opts:
        _load_rmq_config()
    return config_opts.get('pass')


def create_vhost(vhost='volttron', ssl_auth=None):
    """
    Create a new virtual host
    :param vhost: virtual host
    :param ssl_auth
    :return:
    """
    print "Creating new VIRTUAL HOST: {}".format(vhost)
    ssl_auth = ssl_auth if ssl_auth in [True, False] else is_ssl_connection()
    url = '/api/vhosts/{vhost}'.format(vhost=vhost)
    response = http_put_request(url, body={}, ssl_auth=ssl_auth)
    return response


def get_virtualhost(new_vhost, ssl_auth=None):
    """
    Get properties for this virtual host
    :param new_vhost:
    :param ssl_auth: Flag indicating ssl based connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/vhosts/{vhost}'.format(vhost=new_vhost)
    response = http_get_request(url, ssl_auth)
    return response


def delete_vhost(vhost, ssl_auth=None):
    """
    Delete a virtual host
    :param vhost: virtual host
    :param user: username
    :param password: password
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/vhosts/{vhost}'.format(vhost=vhost)
    response = http_delete_request(url, ssl_auth)


def get_virtualhosts(ssl_auth=None):
    """

    :param ssl_auth:
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/vhosts'
    response = http_get_request(url, ssl_auth)
    vhosts = []
    if response:
        vhosts = [v['name'] for v in response]
    return vhosts


# USER - CREATE, GET, DELETE user, SET/GET Permissions
def create_user(user, password=default_pass, tags="administrator",
                ssl_auth=None):
    """
    Create a new RabbitMQ user
    :param user: Username
    :param password: Password
    :param tags: "adminstrator/management"
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    # print "Creating new USER: {}, ssl {}".format(user, ssl)

    body = dict(password=password, tags=tags)
    url = '/api/users/{user}'.format(user=user)
    response = http_put_request(url, body, ssl_auth)


def get_users(ssl_auth=None):
    """
    Get list of all users
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/users/'
    response = http_get_request(url, ssl_auth)
    users = []
    if response:
        users = [u['name'] for u in response]
    return users


def get_url_prefix(ssl_auth):
    """
    Get URL for http or https based on flag
    :param ssl_auth: Flag for ssl_auth connection
    :return:
    """
    if ssl_auth:
        prefix = 'https://{host}:{port}'.format(host=get_hostname(),
                                                port=get_mgmt_port())
    else:
        prefix = 'http://localhost:{port}'.format(port=get_mgmt_port())
    return prefix


def get_user_props(user, ssl_auth=None):
    """
    Get properties of the user
    :param user: username
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/users/{user}'.format(user=user)
    response = http_get_request(url, ssl_auth)
    return response


def delete_user(user, ssl_auth=None):
    """
    Delete specific user
    :param user: user
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/users/{user}'.format(user=user)
    response = http_delete_request(url, ssl_auth)


def delete_users_in_bulk(users, ssl_auth=None):
    """
    Delete a list of users at once
    :param users:
    :param ssl_auth:
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/users/bulk-delete'
    if users and isinstance(users, list):
        body = dict(users=users)
        response = http_put_request(url, body=body, ssl_auth=ssl_auth)


def get_user_permissions(user, vhost=None, ssl_auth=None):
    """
    Get permissions (configure, read, write) for the user
    :param user: user
    :param password: password
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/permissions/{vhost}/{user}'.format(vhost=vhost,
                                                   user=user)
    response = http_get_request(url, ssl_auth)
    return response


# {"configure":".*","write":".*","read":".*"}
def set_user_permissions(permissions, user, vhost=None, ssl_auth=None):
    """
    Set permissions for the user
    :param permissions: dict containing configure, read and write settings
    :param user: username
    :param password: password
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    _log.debug("Create READ, WRITE and CONFIGURE permissions for the user: "
               "{}".format(user))
    url = '/api/permissions/{vhost}/{user}'.format(vhost=vhost, user=user)
    response = http_put_request(url, body=permissions, ssl_auth=ssl_auth)


def set_topic_permissions_for_user(permissions, user, vhost=None,
                                   ssl_auth=None):
    """
    Set read, write permissions for a topic and user
    :param permissions: dict containing exchange name and read/write permissions
    {"exchange":"volttron", read: ".*", write: "^__pubsub__"}
    :param user: username
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/topic-permissions/{vhost}/{user}'.format(vhost=vhost,
                                                         user=user)
    response = http_put_request(url, body=permissions,
                                ssl_auth=ssl_auth)


def get_topic_permissions_for_user(user, vhost=None, ssl_auth=None):
    """
    Get permissions for all topics
    :param user: user
    :param vhost:
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/topic-permissions/{vhost}/{user}'.format(vhost=vhost, user=user)
    response = http_get_request(url, ssl_auth)
    return response


# GET/SET parameter on a component for example, federation-upstream
def get_parameter(component, vhost=None, ssl_auth=None):
    """
    Get component parameters, namely federation-upstream
    :param component: component name
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/parameters/{component}/{vhost}'.format(component=component,
                                                       vhost=vhost)
    response = http_get_request(url, ssl_auth)
    return response


def delete_parameter(component, parameter_name, vhost=None, ssl_auth=None):
    """
    Delete a component parameter
    :param component: component name
    :param parameter_name: parameter
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/parameters/{component}/{vhost}/{parameter}'.format(
        component=component, vhost=vhost, parameter=parameter_name)
    response = http_delete_request(url, ssl_auth)
    return response


# Get all policies, Get/Set/Delete a specific property
def get_policies(vhost=None, ssl_auth=None):
    """
    Get all policies
    :param vhost: virtual host
    :param ssl_auth_auth: Flag for ssl_auth connection
    :return:
    """
    # TODO: check -  this is the only request call.. others ar grequest calls
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    prefix = get_url_prefix(ssl_auth)

    url = '{prefix}/api/policies/{vhost}'.format(prefix=prefix,
                                                 vhost=vhost)
    kwargs = get_authentication_args(ssl_auth)
    response = requests.get(url, **kwargs)
    return response.json() if response else response


def get_policy(name, vhost=None, ssl_auth=None):
    """
    Get a specific policy
    :param name: policy name
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
    response = http_get_request(url, ssl_auth)
    return response.json() if response else response


# value = {"pattern":"^amq.",
# "definition": {"federation-upstream-set":"all"},
# "priority":0, "apply-to": "all"}
def set_policy(name, value, vhost=None, ssl_auth=None):
    """
    Set a policy. For example a federation policy
    :param name: policy name
    :param value: policy value
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
    response = http_put_request(url, body=value, ssl_auth=ssl_auth)


def delete_policy(name, vhost=None, ssl_auth=None):
    """
    Delete a policy
    :param name: policy name
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
    response = http_delete_request(url, ssl_auth)


# Exchanges - Create/delete/List exchanges
# properties = dict(durable=False, type='topic', auto_delete=True,
# arguments={"alternate-exchange": "aexc"})
# properties = dict(durable=False, type='direct', auto_delete=True)
def create_exchange(exchange, properties, vhost=None, ssl_auth=None):
    """
    Create a new exchange
    :param exchange: exchange name
    :param properties: dict containing properties
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    _log.debug("Create new exchange: {}".format(exchange))
    url = '/api/exchanges/{vhost}/{exchange}'.format(vhost=vhost,
                                                     exchange=exchange)
    response = http_put_request(url, body=properties, ssl_auth=ssl_auth)


def delete_exchange(exchange, vhost=None, ssl_auth=None):
    """
    Delete a exchange
    :param exchange: exchange name
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/exchanges/{vhost}/{exchange}'.format(vhost=vhost,
                                                     exchange=exchange)
    response = http_delete_request(url, ssl_auth)


def get_exchanges(vhost=None, ssl_auth=None):
    """
    List all exchanges
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/exchanges/{vhost}'.format(vhost=vhost)
    response = http_get_request(url, ssl_auth)
    exchanges = []

    if response:
        exchanges = [e['name'] for e in response]
    return exchanges


def get_exchanges_with_props(vhost=None, ssl_auth=None):
    """
    List all exchanges with properties
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/exchanges/{vhost}'.format(vhost=vhost)
    return http_get_request(url, ssl_auth)


# Queues - Create/delete/List queues
# properties = dict(durable=False, auto_delete=True)
def create_queue(queue, properties, vhost=None, ssl_auth=None):
    """
    Create a new queue
    :param queue: queue
    :param properties: dict containing properties
    :param vhost: virtual host
    :param ssl_auth: Flag for SSL connection
    :return:
    """
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}/{queue}'.format(vhost=vhost, queue=queue)
    response = http_put_request(url, body=properties, ssl_auth=ssl_auth)


def delete_queue(queue, user=None, password=None, vhost=None, ssl_auth=None):
    """
    Delete a queue
    :param queue: queue
    :param vhost: virtual host
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}/{queue}'.format(vhost=vhost, queue=queue)
    response = http_delete_request(url, ssl_auth)


def get_queues(user=None, password=None, vhost=None, ssl_auth=None):
    """
    Get list of queues
    :param user: username
    :param password: password
    :param vhost: virtual host
    :param ssl: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}'.format(vhost=vhost)
    response = http_get_request(url, ssl_auth)
    queues = []
    if response:
        queues = [q['name'] for q in response]
    return queues


def get_queues_with_props(vhost=None, ssl_auth=None):
    """
    Get properties of all queues
    :param vhost: virtual host
    :param ssl: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/queues/{vhost}'.format(vhost=vhost)
    return http_get_request(url, ssl_auth)


# List all open connections
def get_connections(vhost=None, ssl_auth=None):
    """
    Get all connections
    :param user: username
    :param password: password
    :param vhost: virtual host
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    vhost = vhost if vhost else get_vhost()
    url = '/api/vhosts/{vhost}/connections'.format(vhost=vhost)
    response = http_get_request(url, ssl_auth)
    return response


def get_connection(name, ssl_auth=None):
    """
    Get status of a connection
    :param name: connection name
    :param ssl: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/connections/{name}'.format(name=name)
    response = http_get_request(url, ssl_auth)
    return response.json() if response else response


def delete_connection(name, ssl_auth=None):
    """
    Delete open connection
    :param name: connection name
    :param ssl: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/connections/{name}'.format(name=name)
    response = http_delete_request(url, ssl_auth)


def list_channels_for_connection(connection, ssl_auth=None):
    """
    List all open channels for a given channel
    :param connection: connnection name
    :param ssl: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/connections/{conn}/channels'.format(conn=connection)
    return http_get_request(url, ssl_auth)


def list_channels_for_vhost(vhost=None, ssl_auth=None):
    """
    List all open channels for a given vhost
    :param vhost: virtual host
    :param ssl: Flag for SSL connection
    :return:
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/vhosts/{vhost}/channels'.format(vhost=vhost)
    response = http_get_request(url, ssl_auth)
    return response.json() if response else response


def get_bindings(exchange, ssl_auth=None):
    """
    List all bindings in which a given exchange is the source
    :param exchange: source exchange
    :param ssl: Flag for SSL connection
    :return: list of bindings
    """
    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    url = '/api/exchanges/{vhost}/{exchange}/bindings/source'.format(
        vhost=get_vhost(), exchange=exchange)
    response = http_get_request(url, ssl_auth)
    return response


# We need http address and port
def init_rabbitmq_setup():
    """
    Create a RabbitMQ setup for VOLTTRON based on the rabbitmq_config.json in
    volttron home.
     - Creates a new virtual host: “volttron”
     - Creates a new topic exchange: “volttron” and
      alternate exchange “undeliverable” to capture unrouteable messages

    :return:
    """
    if not config_opts:
        _load_rmq_config()
    vhost = config_opts['virtual-host']
    # Create a new "volttron" vhost
    response = create_vhost(vhost, ssl_auth=False)
    if not response:
        print("Remove /etc/rabbitmq/rabbitmq.conf, "
              "restart rabbitmq-server and try again")
        return response
    exchange = 'volttron'
    alternate_exchange = 'undeliverable'
    # Create a new "volttron" exchange. Set up alternate exchange to capture
    # all unroutable messages
    properties = dict(durable=True, type='topic',
                      arguments={"alternate-exchange": alternate_exchange})
    create_exchange(exchange, properties=properties, vhost=vhost,
                    ssl_auth=False)

    # Create alternate exchange to capture all unroutable messages.
    # Note: Pubsub messages with no subscribers are also captured which is
    # unavoidable with this approach
    properties = dict(durable=True, type='fanout')
    create_exchange(alternate_exchange, properties=properties, vhost=vhost,
                    ssl_auth=False)
    return True


def is_valid_amqp_port(port):
    try:
        port = int(port)
    except ValueError:
        return False

    return port == 5672 or port == 5671


def is_ssl_connection():
    global config_opts
    if not config_opts:
        _load_rmq_config()
    auth = config_opts.get('ssl', 'true')
    return auth in ('true', 'True', 'TRUE')


def is_valid_mgmt_port(port):
    try:
        port = int(port)
    except ValueError:
        return False

    return port == 15672 or port == 15671


def delete_multiplatform_parameter(component, parameter_name, vhost=None):
    """
    Delete a component parameter
    :param component: component name
    :param parameter_name: parameter
    :param vhost: virtual host
    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()
    delete_parameter(component, parameter_name, vhost,
                     ssl_auth=is_ssl_connection())

    # Delete entry in config
    try:
        params = config_opts[component]  # component can be shovels or
        # federation
        del_list = [x for x in params if parameter_name == x['name']]
        for elem in del_list:
            params.remove(elem)
        config_opts[component] = params
        if not params:
            del config_opts[component]
        config_opts.async_sync()
    except KeyError as ex:
        print("Parameter not found: {}".format(ex))
        return


def build_connection_param(identity, instance_name, ssl_auth=None):
    """
    Build Pika Connection parameters
    :param identity:
    :param instance_name:
    :param ssl:
    :return:
    """
    global config_opts
    if not config_opts:
        _load_rmq_config()

    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    instance_ca_name, server_cert_name, admin_cert_name = \
        certs.Certs.get_cert_names(instance_name)
    crt = certs.Certs()
    try:
        if ssl_auth:
            ssl_options = dict(
                                ssl_version=ssl.PROTOCOL_TLSv1,
                                ca_certs=crt.cert_file(instance_ca_name),
                                keyfile=crt.private_key_file(identity),
                                certfile=crt.cert_file(identity),
                                cert_reqs=ssl.CERT_REQUIRED)
            conn_params = pika.ConnectionParameters(
                host=config_opts['host'],
                port=int(config_opts['amqp-port']),
                virtual_host=config_opts['virtual-host'],
                ssl=True,
                ssl_options=ssl_options,
                credentials=pika.credentials.ExternalCredentials())
        else:
                conn_params = pika.ConnectionParameters(
                    host=config_opts['host'],
                    port=int(config_opts['amqp-port']),
                    virtual_host=config_opts['virtual-host'],
                    credentials=pika.credentials.PlainCredentials(
                        identity, identity))
    except KeyError:
        return None
    return conn_params


def build_rmq_address(ssl_auth=None, config=None):
    global config_opts
    if not config_opts:
        _load_rmq_config()
    if not config:
        config = config_opts

    ssl_auth = ssl_auth if ssl_auth is not None else is_ssl_connection()
    user = get_user()
    if user is None:
        if not ssl_auth:
            user = local_user
        else:
            raise ValueError("No user configured in rabbitmq_config.json")

    rmq_address = None
    try:
        if ssl_auth:
            # Address format to connect to server-name, with SSL and EXTERNAL
            # authentication
            # amqps://server-name?cacertfile=/path/to/cacert.pem&certfile=/path/to/cert.pem&keyfile=/path/to/key.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external
            rmq_address = "amqps://{host}:{port}/{vhost}?" \
                          "{ssl_params}&server_name_indication={host}".format(
                            host=config['host'],
                            port=config['amqp-port'],
                            vhost=config['virtual-host'],
                            ssl_params=get_ssl_url_params())
        else:
            passwd = get_password() if get_password() else local_password
            rmq_address = "amqp://{user}:{pwd}@{host}:{port}/{vhost}".format(
                user=user, pwd=passwd, host=config['host'],
                port=config['amqp-port'],
                vhost=config['virtual-host'])
    except KeyError as e:
        print("Missing entries in rabbitmq config {}".format(e))
        raise

    return rmq_address


def create_user_with_permissions(identity, permissions, ssl_auth=None):
    """
    Create RabbitMQ user for an agent and set permissions for it.
    :param identity: Identity of agent
    :param permissions: Configure+Read+Write permissions
    :param is_ssl: Flag to indicate if SSL connection or not
    :return:
    """
    # If user does not exist, create a new one
    if not ssl_auth:
        ssl_auth = is_ssl_connection()
    if identity not in get_users(ssl_auth):
        create_user(identity, identity, ssl_auth=ssl_auth)
    perms = get_user_permissions(identity, ssl_auth=ssl_auth)
    # Add user permissions if missing
    if not perms:
        # perms = dict(configure='.*', read='.*', write='.*')
        perms = dict(configure=permissions['configure'],
                     read=permissions['read'],
                     write=permissions['write'])
        _log.debug("permissions: {}".format(perms))
        set_user_permissions(perms, identity, ssl_auth=ssl_auth)


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


def get_ssl_url_params():
    global crts, instance_name
    if not instance_name:
        instance_name = get_platform_instance_name()
    instance_ca, server_cert, client_cert = certs.Certs.get_cert_names(
        instance_name)
    ca_file = crts.cert_file(instance_ca)
    cert_file = crts.cert_file(client_cert)
    key_file = crts.private_key_file(client_cert)
    return "cacertfile={ca}&certfile={cert}&keyfile={key}" \
           "&verify=verify_peer&fail_if_no_peer_cert=true" \
           "&auth_mechanism=external&depth=1".format(ca=ca_file,
                                                     cert=cert_file,
                                                     key=key_file)


def create_rmq_volttron_test_setup(volttron_home, host='localhost'):
    global config_opts
    _load_rmq_config(volttron_home)
    # print(config_opts)
    ssl_auth = False
    # Set vhost, username, password, hostname and port
    config_opts['virtual-host'] = 'volttron_test'
    config_opts['user'] = 'test_user'
    config_opts['pass'] = 'test_user'
    config_opts['host'] = host
    config_opts['amqp-port'] = str(5672)
    config_opts['mgmt-port'] = str(15672)
    config_opts['ssl'] = str(ssl_auth)
    config_opts['rmq-address'] = build_rmq_address(ssl_auth=False)
    config_opts.async_sync()
    init_rabbitmq_setup()
    create_user_with_permissions('test_user',
                                 dict(configure=".*", read=".*", write=".*"),
                                 ssl_auth=ssl_auth)


def cleanup_rmq_volttron_test_setup(volttron_home):
    global config_opts
    _load_rmq_config(volttron_home)
    try:
        vhost = config_opts.get('virtual-host', 'volttron_test')
        users = get_users(ssl_auth=False)
        users.remove('guest')
        users_to_remove = []
        for user in users:
            perm = get_user_permissions(user, vhost, ssl_auth=False)
            print perm
            if perm:
                users_to_remove.append(user)
        print("Users to remove: {}".format(users_to_remove))
        # Delete all the users using virtual host
        for user in users_to_remove:
            delete_user(user)
        # Finally delete the virtual host
        delete_vhost(config_opts['virtual-host'])
    except KeyError as e:
        return
