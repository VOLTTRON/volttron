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

import logging
import ssl

from volttron.platform import is_rabbitmq_available

if is_rabbitmq_available():
    import pika

from volttron.platform.agent.utils import get_fq_identity

import grequests
import gevent
import requests
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from volttron.platform import certs
from volttron.platform import jsonapi
from . rmq_config_params import RMQConfig

try:
    import yaml
except ImportError:
    raise RuntimeError('PyYAML must be installed before running this script ')


_log = logging.getLogger(__name__)

"""
    RabbitMQ Management class that contains HTTP management utility methods to
    1. Create/Delete virtual hosts for each platform
    2. Create/Delete user for each agent
    3. Set/Get permissions for each user
    4. Create/Delete exchanges
    5. Create/Delete queues
    6. Create/List/Delete federation upstream servers
    7. Create/List/Delete federation upstream policies
    8. Create shovels for multi-platform deployment.
    9. Set topic permissions for protected topics
    10. List the status of
        Open Connections
        Exchanges
        Queues
        Queue to exchange bindings
"""


class RabbitMQMgmt(object):
    def __init__(self):
        self.rmq_config = RMQConfig()
        self.is_ssl = self.rmq_config.is_ssl
        self.certs = self.rmq_config.crts

    def _call_grequest(self, method_name, url_suffix, ssl_auth=True, **kwargs):
        """
        Make grequest calls to RabbitMQ management
        :param method_name: method type - put/get/delete
        :param url_suffix: http URL suffix
        :param ssl_auth: If True, it's SSL based connection
        :param kwargs: Additional arguments for http request
        :return:
        """
        url = self._get_url_prefix(ssl_auth) + url_suffix
        kwargs["headers"] = {"Content-Type": "application/json"}
        auth_args = self._get_authentication_args(ssl_auth)
        kwargs.update(auth_args)

        try:
            fn = getattr(grequests, method_name)
            request = fn(url, **kwargs)
            response = grequests.map([request])

            if response and isinstance(response, list):
                response[0].raise_for_status()
        except (ConnectionError, NewConnectionError) as e:
            _log.debug("Error connecting to {} with "
                       "args {}: {}".format(url, kwargs, e))
            raise e
        except requests.exceptions.HTTPError as e:
            _log.debug("Exception when trying to make HTTP request to {} with "
                       "args {} : {}".format(url, kwargs, e))
            raise e
        except AttributeError as e:
            _log.debug("Exception when trying to make HTTP request to {} with "
                       "args {} : {}".format(url, kwargs, e))
            raise e
        return response

    
    def _get_authentication_args(self, ssl_auth):
        """
        Return authentication kwargs for request/greqeust
        :param ssl_auth: if True returns cert and verify parameters in addition
         to auth
        :return: dictionary containing auth/cert args need to pass to
        request/grequest methods
        """

        if ssl_auth:
            root_ca_name, server_cert, client_cert = \
                certs.Certs.get_admin_cert_names(self.rmq_config.instance_name)

            # TODO: figure out how to manage admin user and password. rabbitmq
            # federation plugin doesn't handle external_auth plugin !!
            # One possible workaround is to use plain username/password auth
            # with guest user with localhost. We still have to persist guest
            # password but at least guest user can only access rmq using
            # localhost

            return {
                # TODO create guest cert and use localhost and guest cert instead
                # when connecting to management apis. Because management api
                # won't honour external auth the same way amqps does :(
                'auth': (self.rmq_config.admin_user, self.rmq_config.admin_pwd),
                'verify': self.rmq_config.crts.cert_file(self.rmq_config.crts.trusted_ca_name),
                'cert': (self.rmq_config.crts.cert_file(client_cert),
                         self.rmq_config.crts.private_key_file(client_cert))}
        else:
            password = self.rmq_config.local_user
            user = self.rmq_config.local_password
            return {'auth': (user, password)}

    def _http_put_request(self, url_suffix, body=None, ssl_auth=True):
        if body:
            return self._call_grequest('put', url_suffix, ssl_auth,
                                       data=jsonapi.dumps(body))
        else:
            return self._call_grequest('put', url_suffix, ssl_auth)

    def _http_delete_request(self, url, ssl_auth=True):
        return self._call_grequest('delete', url, ssl_auth)

    def _http_get_request(self, url, ssl_auth=True):
        response = self._call_grequest('get', url, ssl_auth)
        if response and isinstance(response, list):
            response = response[0].json()
        return response

    def create_vhost(self, vhost='volttron', ssl_auth=None):
        """
        Create a new virtual host
        :param vhost: virtual host
        :param ssl_auth
        :return:
        """
        _log.debug("Creating new VIRTUAL HOST: {}".format(vhost))
        ssl_auth = ssl_auth if ssl_auth in [True, False] else self.is_ssl
        url = '/api/vhosts/{vhost}'.format(vhost=vhost)
        response = self._http_put_request(url, body={}, ssl_auth=ssl_auth)
        return response

    def get_virtualhost(self, vhost, ssl_auth=None):
        """
        Get properties for this virtual host
        :param vhost:
        :param ssl_auth: Flag indicating ssl based connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/vhosts/{vhost}'.format(vhost=vhost)
        response = self._http_get_request(url, ssl_auth)
        return response

    def delete_vhost(self, vhost, ssl_auth=None):
        """
        Delete a virtual host
        :param vhost: virtual host
        :param user: username
        :param password: password
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/vhosts/{vhost}'.format(vhost=vhost)
        response = self._http_delete_request(url, ssl_auth)

    def get_virtualhosts(self, ssl_auth=None):
        """

        :param ssl_auth:
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/vhosts'
        response = self._http_get_request(url, ssl_auth)
        vhosts = []
        if response:
            vhosts = [v['name'] for v in response]
        return vhosts

    # USER - CREATE, GET, DELETE user, SET/GET Permissions
    def create_user(self, user, password=None, tags="administrator",
                    ssl_auth=None):
        """
        Create a new RabbitMQ user
        :param user: Username
        :param password: Password
        :param tags: "adminstrator/management"
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        if not password:
            password = self.rmq_config.default_pass
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl

        body = dict(password=password, tags=tags)

        url = '/api/users/{user}'.format(user=user)
        response = self._http_put_request(url, body, ssl_auth)

    def get_users(self, ssl_auth=None):
        """
        Get list of all users
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/users/'
        response = self._http_get_request(url, ssl_auth)
        users = []
        if response:
            users = [u['name'] for u in response]
        return users

    def _get_url_prefix(self, ssl_auth):
        """
        Get URL for http or https based on flag
        :param ssl_auth: Flag for ssl_auth connection
        :return:
        """
        if ssl_auth:
            prefix = 'https://{host}:{port}'.format(host=self.rmq_config.hostname,
                                                    port=self.rmq_config.mgmt_port_ssl)
        else:
            prefix = 'http://localhost:{port}'.format(port=self.rmq_config.mgmt_port)
        return prefix

    def get_user_props(self, user, ssl_auth=None):
        """
        Get properties of the user
        :param user: username
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/users/{user}'.format(user=user)
        response = self._http_get_request(url, ssl_auth)
        return response

    def delete_user(self, user, ssl_auth=None):
        """
        Delete specific user
        :param user: user
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/users/{user}'.format(user=user)
        try:
            response = self._http_delete_request(url, ssl_auth)
        except requests.exceptions.HTTPError as e:
            if not e.message.startswith("404 Client Error"):
                raise

    def delete_users_in_bulk(self, users, ssl_auth=None):
        """
        Delete a list of users at once
        :param users:
        :param ssl_auth:
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/users/bulk-delete'
        if users and isinstance(users, list):
            body = dict(users=users)
            response = self._http_put_request(url, body=body, ssl_auth=ssl_auth)

    def get_user_permissions(self, user, vhost=None, ssl_auth=None):
        """
        Get permissions (configure, read, write) for the user
        :param user: user
        :param password: password
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/permissions/{vhost}/{user}'.format(vhost=vhost,
                                                       user=user)
        try:
            response = self._http_get_request(url, ssl_auth)
            return response
        except requests.exceptions.HTTPError as e:
            if e.message.startswith("404 Client Error"):
                # No permissions are set for this user yet. Return none
                # so caller can try to set permissions
                return None
            else:
                raise e

    # {"configure":".*","write":".*","read":".*"}
    def set_user_permissions(self, permissions, user, vhost=None, ssl_auth=None):
        """
        Set permissions for the user
        :param permissions: dict containing configure, read and write settings
        :param user: username
        :param password: password
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        _log.debug("Create READ, WRITE and CONFIGURE permissions for the user: "
                   "{}".format(user))
        url = '/api/permissions/{vhost}/{user}'.format(vhost=vhost, user=user)
        response = self._http_put_request(url, body=permissions, ssl_auth=ssl_auth)

    def set_topic_permissions_for_user(self, permissions, user, vhost=None,
                                       ssl_auth=None):
        """
        Set read, write permissions for a topic and user
        :param permissions: dict containing exchange name and read/write permissions
        {"exchange":"volttron", read: ".*", write: "^__pubsub__"}
        :param user: username
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/topic-permissions/{vhost}/{user}'.format(vhost=vhost,
                                                             user=user)
        response = self._http_put_request(url, body=permissions,
                                          ssl_auth=ssl_auth)

    def get_topic_permissions_for_user(self, user, vhost=None, ssl_auth=None):
        """
        Get permissions for all topics
        :param user: user
        :param vhost:
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/topic-permissions/{vhost}/{user}'.format(vhost=vhost, user=user)
        response = self._http_get_request(url, ssl_auth)
        return response

    # GET/SET parameter on a component for example, federation-upstream
    def get_parameter(self, component, vhost=None, ssl_auth=None):
        """
        Get component parameters, namely federation-upstream
        :param component: component name
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/parameters/{component}/{vhost}'.format(component=component,
                                                           vhost=vhost)
        response = self._http_get_request(url, ssl_auth)
        return response

    def set_parameter(self, component, parameter_name, parameter_properties,
                      vhost=None, ssl_auth=None):
        """
        Set parameter on a component
        :param component: component name (for example, federation-upstream)
        :param parameter_name: parameter name
        :param parameter_properties: parameter properties
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/parameters/{component}/{vhost}/{param}'.format(
            component=component, vhost=vhost, param=parameter_name)
        response = self._http_put_request(url, body=parameter_properties,
                                          ssl_auth=ssl_auth)

    def delete_parameter(self, component, parameter_name, vhost=None, ssl_auth=None):
        """
        Delete a component parameter
        :param component: component name
        :param parameter_name: parameter
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/parameters/{component}/{vhost}/{parameter}'.format(
            component=component, vhost=vhost, parameter=parameter_name)
        response = self._http_delete_request(url, ssl_auth)
        return response

    # Get all policies, Get/Set/Delete a specific property
    def get_policies(self, vhost=None, ssl_auth=None):
        """
        Get all policies
        :param vhost: virtual host
        :param ssl_auth_auth: Flag for ssl_auth connection
        :return:
        """
        # TODO: check -  this is the only request call.. others ar grequest calls
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        prefix = self._get_url_prefix(ssl_auth)

        url = '{prefix}/api/policies/{vhost}'.format(prefix=prefix,
                                                     vhost=vhost)
        kwargs = self._get_authentication_args(ssl_auth)
        response = requests.get(url, **kwargs)
        return response.json() if response else response

    def get_policy(self, name, vhost=None, ssl_auth=None):
        """
        Get a specific policy
        :param name: policy name
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
        response = self._http_get_request(url, ssl_auth)
        return response.json() if response else response

    # value = {"pattern":"^amq.",
    # "definition": {"federation-upstream-set":"all"},
    # "priority":0, "apply-to": "all"}
    def set_policy(self, name, value, vhost=None, ssl_auth=None):
        """
        Set a policy. For example a federation policy
        :param name: policy name
        :param value: policy value
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
        response = self._http_put_request(url, body=value, ssl_auth=ssl_auth)

    def delete_policy(self, name, vhost=None, ssl_auth=None):
        """
        Delete a policy
        :param name: policy name
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/policies/{vhost}/{name}'.format(vhost=vhost, name=name)
        response = self._http_delete_request(url, ssl_auth)

    # Exchanges - Create/delete/List exchanges
    # properties = dict(durable=False, type='topic', auto_delete=True,
    # arguments={"alternate-exchange": "aexc"})
    # properties = dict(durable=False, type='direct', auto_delete=True)
    def create_exchange(self, exchange, properties, vhost=None, ssl_auth=None):
        """
        Create a new exchange
        :param exchange: exchange name
        :param properties: dict containing properties
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        print("Create new exchange: {}, {}".format(exchange, properties))
        url = '/api/exchanges/{vhost}/{exchange}'.format(vhost=vhost,
                                                         exchange=exchange)
        response = self._http_put_request(url, body=properties, ssl_auth=ssl_auth)

    def delete_exchange(self, exchange, vhost=None, ssl_auth=None):
        """
        Delete a exchange
        :param exchange: exchange name
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/exchanges/{vhost}/{exchange}'.format(vhost=vhost,
                                                         exchange=exchange)
        response = self._http_delete_request(url, ssl_auth)

    def get_exchanges(self, vhost=None, ssl_auth=None):
        """
        List all exchanges
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/exchanges/{vhost}'.format(vhost=vhost)
        response = self._http_get_request(url, ssl_auth)
        exchanges = []

        if response:
            exchanges = [e['name'] for e in response]
        return exchanges

    def get_exchanges_with_props(self, vhost=None, ssl_auth=None):
        """
        List all exchanges with properties
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/exchanges/{vhost}'.format(vhost=vhost)
        return self._http_get_request(url, ssl_auth)

    # Queues - Create/delete/List queues
    # properties = dict(durable=False, auto_delete=True)
    def create_queue(self, queue, properties, vhost=None, ssl_auth=None):
        """
        Create a new queue
        :param queue: queue
        :param properties: dict containing properties
        :param vhost: virtual host
        :param ssl_auth: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/queues/{vhost}/{queue}'.format(vhost=vhost, queue=queue)
        response = self._http_put_request(url, body=properties, ssl_auth=ssl_auth)

    def delete_queue(self, queue, user=None, password=None, vhost=None, ssl_auth=None):
        """
        Delete a queue
        :param queue: queue
        :param vhost: virtual host
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/queues/{vhost}/{queue}'.format(vhost=vhost, queue=queue)
        response = self._http_delete_request(url, ssl_auth)

    def get_queues(self, user=None, password=None, vhost=None, ssl_auth=None):
        """
        Get list of queues
        :param user: username
        :param password: password
        :param vhost: virtual host
        :param ssl: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/queues/{vhost}'.format(vhost=vhost)
        response = self._http_get_request(url, ssl_auth)
        queues = []
        if response:
            queues = [q['name'] for q in response]
        return queues

    def get_queues_with_props(self, vhost=None, ssl_auth=None):
        """
        Get properties of all queues
        :param vhost: virtual host
        :param ssl: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/queues/{vhost}'.format(vhost=vhost)
        return self._http_get_request(url, ssl_auth)

    # List all open connections
    def get_connections(self, vhost=None, ssl_auth=None):
        """
        Get all connections
        :param user: username
        :param password: password
        :param vhost: virtual host
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/vhosts/{vhost}/connections'.format(vhost=vhost)
        response = self._http_get_request(url, ssl_auth)
        return response

    def get_connection(self, name, ssl_auth=None):
        """
        Get status of a connection
        :param name: connection name
        :param ssl: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/connections/{name}'.format(name=name)
        response = self._http_get_request(url, ssl_auth)
        return response.json() if response else response

    def delete_connection(self, name, ssl_auth=None):
        """
        Delete open connection
        :param name: connection name
        :param ssl: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/connections/{name}'.format(name=name)
        response = self._http_delete_request(url, ssl_auth)

    def list_channels_for_connection(self, connection, ssl_auth=None):
        """
        List all open channels for a given channel
        :param connection: connnection name
        :param ssl: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/connections/{conn}/channels'.format(conn=connection)
        return self._http_get_request(url, ssl_auth)

    def list_channels_for_vhost(self, vhost=None, ssl_auth=None):
        """
        List all open channels for a given vhost
        :param vhost: virtual host
        :param ssl: Flag for SSL connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/vhosts/{vhost}/channels'.format(vhost=vhost)
        response = self._http_get_request(url, ssl_auth)
        return response.json() if response else response

    def get_bindings(self, exchange, ssl_auth=None):
        """
        List all bindings in which a given exchange is the source
        :param exchange: source exchange
        :param ssl: Flag for SSL connection
        :return: list of bindings
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/exchanges/{vhost}/{exchange}/bindings/source'.format(
            vhost=self.rmq_config.virtual_host, exchange=exchange)
        response = self._http_get_request(url, ssl_auth)
        return response

    # We need http address and port
    def init_rabbitmq_setup(self):
        """
        Create a RabbitMQ resources for VOLTTRON instance.
         - Create a new virtual host: default is “volttron”
         - Create a new topic exchange: “volttron”
         - Create alternate exchange: “undeliverable” to capture unrouteable messages

        :return:
        """
        vhost = self.rmq_config.virtual_host
        # Create a new "volttron" vhost
        try:
            response = self.create_vhost(vhost, ssl_auth=False)
        except requests.exceptions.HTTPError:
            # Wait for few more seconds and retry again
            gevent.sleep(5)
            response = self.create_vhost(vhost, ssl_auth=False)
            print(f"Cannot create vhost {vhost}")
            return response

        # Create admin user for the instance
        self.create_user(self.rmq_config.admin_user, ssl_auth=False)
        permissions = dict(configure=".*", read=".*", write=".*")
        self.set_user_permissions(permissions, self.rmq_config.admin_user, ssl_auth=False)

        exchange = 'volttron'
        alternate_exchange = 'undeliverable'
        # Create a new "volttron" exchange. Set up alternate exchange to capture
        # all unrouteable messages
        properties = dict(durable=True, type='topic',
                          arguments={"alternate-exchange": alternate_exchange})
        self.create_exchange(exchange, properties=properties, vhost=vhost,
                             ssl_auth=False)

        # Create alternate exchange to capture all unroutable messages.
        # Note: Pubsub messages with no subscribers are also captured which is
        # unavoidable with this approach
        properties = dict(durable=True, type='fanout')
        self.create_exchange(alternate_exchange, properties=properties, vhost=vhost,
                             ssl_auth=False)
        return True

    def is_valid_amqp_port(port):
        try:
            port = int(port)
        except ValueError:
            return False

        return port == 5672 or port == 5671

    def is_valid_mgmt_port(port):
        try:
            port = int(port)
        except ValueError:
            return False

        return port == 15672 or port == 15671

    def delete_multiplatform_parameter(self, component, parameter_name, vhost=None):
        """
        Delete a component parameter
        :param component: component name
        :param parameter_name: parameter
        :param vhost: virtual host
        :return:
        """
        self.delete_parameter(component, parameter_name, vhost,
                              ssl_auth=self.rmq_config.is_ssl)

    def build_connection_param(self, rmq_user, ssl_auth=None, retry_attempt=30, retry_delay=2):
        """
        Build Pika Connection parameters
        :param rmq_user: RabbitMQ user
        :param ssl_auth: If SSL based connection or not
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        crt = self.rmq_config.crts
        heartbeat_interval = 20 #sec

        try:
            if ssl_auth:
                ssl_options = dict(
                    ssl_version=ssl.PROTOCOL_TLSv1,
                    ca_certs=crt.cert_file(crt.trusted_ca_name),
                    keyfile=crt.private_key_file(rmq_user),
                    certfile=crt.cert_file(rmq_user),
                    cert_reqs=ssl.CERT_REQUIRED)
                conn_params = pika.ConnectionParameters(
                    host=self.rmq_config.hostname,
                    port=int(self.rmq_config.amqp_port_ssl),
                    virtual_host=self.rmq_config.virtual_host,
                    connection_attempts=retry_attempt,
                    retry_delay=retry_delay,
                    heartbeat=heartbeat_interval,
                    ssl=True,
                    ssl_options=ssl_options,
                    credentials=pika.credentials.ExternalCredentials())
            else:
                # TODO: How is this working? PlainCredentials(rmq_user,
                # rmq_user) ?? My understanding is that non ssl mode is going to
                #  be used only for testing - when using plain
                # credentials all agents use same password.
                conn_params = pika.ConnectionParameters(
                    host=self.rmq_config.hostname,
                    port=int(self.rmq_config.amqp_port),
                    virtual_host=self.rmq_config.virtual_host,
                    heartbeat=heartbeat_interval,
                    credentials=pika.credentials.PlainCredentials(
                        rmq_user, rmq_user))
        except KeyError:
            return None
        return conn_params

    def build_remote_connection_param(self, rmq_user, rmq_address, ssl_auth=None, retry_attempt=30, retry_delay=2):
        """
        Build Pika Connection parameters
        :param rmq_user: RabbitMQ user
        :param ssl_auth: If SSL based connection or not
        :return:
        """

        from urlparse import urlparse

        parsed_addr = urlparse(rmq_address)
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl

        _, virtual_host = parsed_addr.path.split('/')

        try:
            if ssl_auth:
                certfile = self.certs.cert_file(rmq_user, True)
                metafile = certfile[:-4] + ".json"
                metadata = jsonapi.loads(open(metafile).read())
                local_keyfile = metadata['local_keyname']
                ca_file = self.certs.cert_file(metadata['remote_ca_name'], True)
                ssl_options = dict(
                    ssl_version=ssl.PROTOCOL_TLSv1,
                    ca_certs=ca_file,
                    keyfile=self.certs.private_key_file(local_keyfile),
                    certfile=self.certs.cert_file(rmq_user, True),
                    cert_reqs=ssl.CERT_REQUIRED)
                conn_params = pika.ConnectionParameters(
                    host= parsed_addr.hostname,
                    port= parsed_addr.port,
                    virtual_host=virtual_host,
                    ssl=True,
                    connection_attempts=retry_attempt,
                    retry_delay=retry_delay,
                    ssl_options=ssl_options,
                    credentials=pika.credentials.ExternalCredentials())
            else:
                conn_params = pika.ConnectionParameters(
                    host=parsed_addr.hostname,
                    port=parsed_addr.port,
                    virtual_host=virtual_host,
                    credentials=pika.credentials.PlainCredentials(
                        rmq_user, rmq_user))
        except KeyError:
            return None
        return conn_params

    def build_rmq_address(self, user=None, password=None,
                          host=None, port=None, vhost=None,
                          ssl_auth=None, ssl_params=None):
        """
        Build RMQ address for federation or shovel connection
        :param ssl_auth:
        :param config:
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        user = user if user else self.rmq_config.admin_user
        password = password if password else self.rmq_config.admin_pwd
        host = host if host else self.rmq_config.hostname
        vhost = vhost if vhost else self.rmq_config.virtual_host
        if ssl_auth:
            ssl_params = ssl_params if ssl_params else self.get_ssl_url_params()

        rmq_address = None
        try:
            if ssl_auth:
                # Address format to connect to server-name, with SSL and EXTERNAL
                # authentication
                rmq_address = "amqps://{host}:{port}/{vhost}?" \
                              "{ssl_params}&server_name_indication={host}".format(
                    host=host,
                    port=port,
                    vhost=vhost,
                    ssl_params=ssl_params)
            else:

                rmq_address = "amqp://{user}:{pwd}@{host}:{port}/{vhost}".format(
                    user=user, pwd=password, host=host,
                    port=port,
                    vhost=vhost)
        except KeyError as e:
            _log.error("Missing entries in rabbitmq config {}".format(e))
            raise

        return rmq_address

    def create_user_with_permissions(self, user, permissions, ssl_auth=None):
        """
        Create RabbitMQ user. Set permissions for it.
        :param identity: Identity of agent
        :param permissions: Configure+Read+Write permissions
        :param is_ssl: Flag to indicate if SSL connection or not
        :return:
        """
        # If user does not exist, create a new one
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        if user not in self.get_users(ssl_auth):
            self.create_user(user, user, ssl_auth=ssl_auth)
        # perms = dict(configure='.*', read='.*', write='.*')
        perms = dict(configure=permissions['configure'],
                     read=permissions['read'],
                     write=permissions['write'])
        self.set_user_permissions(perms, user, ssl_auth=ssl_auth)

    def get_default_permissions(self, fq_identity):
        config_access = "{user}|{user}.pubsub.*|{user}.zmq.*|amq.*".format(
            user=fq_identity)
        read_access = "volttron|{}".format(config_access)
        write_access = "volttron|{}".format(config_access)
        permissions = dict(configure=config_access, read=read_access,
                           write=write_access)
        return permissions

    def build_agent_connection(self, identity, instance_name):
        """
        Check if RabbitMQ user and certs exists for this agent, if not
        create a new one. Add access control/permissions if necessary.
        Return connection parameters.
        :param identity: Identity of agent
        :param instance_name: instance name of the platform
        :param is_ssl: Flag to indicate if SSL connection or not
        :return: Return connection parameters
        """

        rmq_user = get_fq_identity(identity, instance_name)
        permissions = self.get_default_permissions(rmq_user)

        if self.is_ssl:
            self.rmq_config.crts.create_ca_signed_cert(rmq_user, overwrite=False)
        param = None

        try:
            self.create_user_with_permissions(rmq_user, permissions, ssl_auth=self.is_ssl)
            param = self.build_connection_param(rmq_user, ssl_auth=self.is_ssl)
        except AttributeError:
            _log.error("Unable to create RabbitMQ user for the agent. Check if RabbitMQ broker is running")

        return param

    def build_shovel_connection(self, identity, instance_name, host, port, vhost, is_ssl):
        """
        Check if RabbitMQ user and certs exists for this agent, if not
        create a new one. Add access control/permissions if necessary.
        Return connection parameters.
        :param identity: Identity of agent
        :param instance_name: instance name of the platform
        :param host: hostname
        :param port: amqp/amqps port
        :param vhost: virtual host
        :param is_ssl: Flag to indicate if SSL connection or not
        :return: Return connection uri
        """
        rmq_user = instance_name + '.' + identity
        config_access = "{user}|{user}.pubsub.*|{user}.zmq.*|amq.*".format(
            user=rmq_user)
        read_access = "volttron|{}".format(config_access)
        write_access = "volttron|{}".format(config_access)
        permissions = dict(configure=config_access, read=read_access,
                           write=write_access)

        self.create_user_with_permissions(rmq_user, permissions)
        ssl_params = None
        if is_ssl:
            self.rmq_config.crts.create_ca_signed_cert(rmq_user,
                                                       overwrite=False)
            ssl_params = self.get_ssl_url_params(user=rmq_user)
        return self.build_rmq_address(rmq_user, self.rmq_config.admin_pwd,
                                      host, port, vhost, is_ssl, ssl_params)

    def build_router_connection(self, identity, instance_name):
        """
        Check if RabbitMQ user and certs exists for the router, if not
        create a new one. Add access control/permissions if necessary.
        Return connection parameters.
        :param identity: Identity of agent
        :param permissions: Configure+Read+Write permissions
        :param is_ssl: Flag to indicate if SSL connection or not
        :return:
        """
        rmq_user = instance_name + '.' + identity
        permissions = dict(configure=".*", read=".*", write=".*")

        if self.is_ssl:
            self.rmq_config.crts.create_ca_signed_cert(rmq_user, overwrite=False)

        self.create_user_with_permissions(rmq_user, permissions, ssl_auth=self.is_ssl)

        param = self.build_connection_param(rmq_user,
                                            ssl_auth=self.is_ssl,
                                            retry_attempt=60,
                                            retry_delay=2)
        return param

    def get_ssl_url_params(self, user=None):
        """
        Return SSL parameter string
        :return:
        """

        root_ca_name, server_cert, admin_user = \
            certs.Certs.get_admin_cert_names(self.rmq_config.instance_name)
        if not user:
            user = admin_user
        ca_file = self.rmq_config.crts.cert_file(self.rmq_config.crts.trusted_ca_name)
        cert_file = self.rmq_config.crts.cert_file(user)
        key_file = self.rmq_config.crts.private_key_file(user)
        return "cacertfile={ca}&certfile={cert}&keyfile={key}" \
               "&verify=verify_peer&fail_if_no_peer_cert=true" \
               "&auth_mechanism=external".format(ca=ca_file,
                                                 cert=cert_file,
                                                 key=key_file)
