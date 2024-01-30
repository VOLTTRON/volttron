# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from requests.exceptions import HTTPError
import os
from volttron.platform import jsonapi, get_home
from .rmq_config_params import RMQConfig, read_config_file, write_to_config_file


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


class RabbitMQMgmt:
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
            request = grequests.request(method_name, url, **kwargs)
            response = request.send().response

            if response and isinstance(response, list):
                response[0].raise_for_status()
        except (ConnectionError, NewConnectionError) as e:
            _log.debug("Error connecting to {} with "
                       "args {}: {}".format(url, kwargs, e))
            raise e
        except HTTPError as e:
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
            from volttron.platform.auth import certs
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
        if response:
            if isinstance(response, list):
                response = response[0].json()
            else:
                response = response.json()
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
        #_log.info("in get users")
        #_log.info(f"{self._get_url_prefix(ssl_auth) + url} {self._get_authentication_args(True)}")
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
        except HTTPError as e:
            if e.response.status_code == 404:
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
        except HTTPError as e:
            if e.response.status_code == 404:
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
        #_log.debug("Create READ, WRITE and CONFIGURE permissions for the user: "
        #           "{}".format(user))
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
        return response

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
        :param ssl_auth: Flag for ssl_auth connection
        :return:
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        vhost = vhost if vhost else self.rmq_config.virtual_host
        url = '/api/policies/{vhost}'.format(vhost=vhost)
        return self._http_get_request(url, ssl_auth)

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
        return response

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

    def get_federation_links(self, ssl_auth=None):
        """
        List all federation links for a given virtual host
        :param ssl: Flag for SSL connection
        :return: list of federation links
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/federation-links/{vhost}'.format(
            vhost=self.rmq_config.virtual_host)
        response = self._http_get_request(url, ssl_auth)
        links = []
        if response:
            for res in response:
                lk = dict()
                lk['name'] = res['upstream']
                lk['status'] = res.get('status', 'Error in link')
                links.append(lk)
        return links

    def get_shovel_link_status(self, name, ssl_auth=None):
        state = 'error'
        links = self.get_shovel_links(ssl_auth=ssl_auth)
        for link in links:
            if link['name'] == name:
                state = link['status']
                break
        return state

    def get_federation_link_status(self, name, ssl_auth=None):
        state = 'error'
        links = self.get_federation_links(ssl_auth=ssl_auth)
        for link in links:
            if link['name'] == name:
                state = link['status']
                break
        return state

    def get_shovel_links(self, ssl_auth=None):
        """
        List all shovel links for a given virtual host
        :param ssl: Flag for SSL connection
        :return: list of federation links
        """
        ssl_auth = ssl_auth if ssl_auth is not None else self.is_ssl
        url = '/api/shovels/{vhost}'.format(
            vhost=self.rmq_config.virtual_host)
        response = self._http_get_request(url, ssl_auth)
        links = []
        if response:
            for res in response:
                lk = dict()
                lk['name'] = res['name']
                lk['status'] = res.get('state', 'Error in link')
                lk['src_uri'] = res.get('src_uri', '')
                lk['dest_uri'] = res.get('dest_uri', '')
                lk['src_exchange_key'] = res.get('src_exchange_key', '')
                links.append(lk)
        return links

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
        except HTTPError:
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

    def delete_multiplatform_parameter(self, component, parameter_name, vhost=None, delete_certs=False):
        """
        Delete a component parameter
        :param component: component name
        :param parameter_name: parameter
        :param vhost: virtual host
        :return:
        """
        shovel_names_for_host = []
        self.delete_parameter(component, parameter_name, vhost,
                              ssl_auth=self.rmq_config.is_ssl)
        print(f"Deleted {component} parameter: {parameter_name}")

        try:
            if component == 'shovel':
                parameter_parts = parameter_name.split('-')
                shovel_links = self.get_shovel_links()
                shovel_names = [link['name'] for link in shovel_links]
                for name in shovel_names:
                    name_parts = name.split('-')
                    if parameter_parts[1] == name_parts[1]:
                        shovel_names_for_host.append(name)
                # Check if there are other shovel connections to remote platform. If yes, we
                # cannot delete the certs since others will need them
                if delete_certs and len(shovel_names_for_host) >= 1:
                    print(f"Cannot delete certificates since there are other shovels "
                          f"connected to remote host: {parameter_parts[1]}")
                    return
        except AttributeError as ex:
            _log.error(f"Unable to reach RabbitMQ management API. Check if RabbitMQ server is running. "
                       f"If not running, start the server using start-rabbitmq script in root of source directory.")
            return

        import os
        vhome = get_home()
        if component == 'shovel':
            config_file = os.path.join(vhome, 'rabbitmq_shovel_config.yml')
            key = 'shovel'
        else:
            config_file = os.path.join(vhome, 'rabbitmq_federation_config.yml')
            key = 'federation-upstream'
        config = read_config_file(config_file)

        # Delete certs from VOLTTRON_HOME
        if delete_certs:
            print(f"Removing certificate paths from VOLTTRON_HOME and from the config file")
            names = parameter_name.split("-")

            certs_config = None
            try:
                certs_config = config[key][names[1]]['certificates']
                del config[key][names[1]]['certificates']
                write_to_config_file(config_file, config)
            except (KeyError, IndexError) as e:
                print(f"Error: Did not find certificates entry in {config_file}:{e}")
                return
            try:
                private_key = certs_config['private_key']
                public_cert = certs_config['public_cert']
                remote_ca = certs_config['remote_ca']
                if os.path.exists(private_key):
                    os.remove(private_key)
                private_dir, filename = os.path.split(private_key)
                cert_name = filename[:-4] + '.crt'
                cert_path = private_dir.replace('private', 'certs')+'/' + cert_name

                if os.path.exists(cert_path):
                    os.remove(cert_path)
                if os.path.exists(public_cert):
                    os.remove(public_cert)
                if os.path.exists(remote_ca):
                    os.remove(remote_ca)
            except KeyError as e:
                print(f"Error: Missing key in {config_file}: {e}")
                pass

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

    def create_signed_certs(self, rmq_user):
        try:
            c, k = self.rmq_config.crts.create_signed_cert_files(rmq_user, overwrite=False)
        except Exception as e:
            _log.error("Exception creating certs. {}".format(e))
            raise RuntimeError(e)
