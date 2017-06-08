# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

import requests

"""
This example exposes the VOLTTRON web API
through a python class that that does not depend
on VOLTTRON proper. A VOLTTRON Central Agent must
be running on the url passed to the constructor.
"""

class VolttronWebRPC(object):
    def __init__(self, url, username='admin', password='admin'):
        """
        :param url: Jsonrpc endpoint for posting data.
        :param username:
        :param password:
        """
        self._url = url
        self._username = username
        self._password = password

        self._auth_token = None
        self._auth_token = self.get_auth_token()

    def do_rpc(self, method, **params):
        """
        Generic method to request data from Volttron Central

        :param method: Method to call
        :param params: Any method specific keyword arguments
        """
        data = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'authorization': self._auth_token,
            'id': '1'
        }

        r = requests.post(self._url, json=data)
        validate_response(r)

        return r.json()['result']

    def get_auth_token(self):
        """
        Get an authorization token from Volttron Central,
        automatically called when the object is created
        """
        return self.do_rpc('get_authorization',
                               username=self._username,
                               password=self._password)

    def register_instance(self, addr, name=None):
        """
        Register a platform with Volttron Central

        :param addr: Platform's discovery address that will be registered
        """
        return self.do_rpc('register_instance',discovery_address=addr,
                           display_name=name)

    def list_platforms(self):
        """
        Get a list of registered platforms from Volttron Central.
        """
        return self.do_rpc('list_platforms')

    def install_agent(self, platform_uuid, fileargs):
        """
        Install an agent on a platform

        :param platform_uuid: uuid of platform where agent will be installed
        :param fileargs: arguments for installing the agent
        """
        rpc = 'platforms.uuid.{}.install'.format(platform_uuid)
        return self.do_rpc(rpc, files=[fileargs])

    def list_agents(self, platform_uuid):
        """
        List agents installed on a platform
        """
        return self.do_rpc('platforms.uuid.' + platform_uuid + '.list_agents')

    def unregister_platform(self, platform_uuid):
        """
        Unregister a platform with Volttron Central
        """
        return self.do_rpc('unregister_platform', platform_uuid=platform_uuid)

    def store_agent_config(self, platform_uuid, agent_identity, config_name,
                           raw_contents, config_type="json"):
        """
        Add a file to the an agent's config store

        :param platform_uuid: uuid of platform where agent will is installed
        :param agent_identity: VIP identity of agent that will own the config
        :param config_name: name of the configuration file
        :param raw_contents: file data
        """
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity,
                      config_name=config_name,
                      raw_contents=raw_contents,
                      config_type=config_type)
        return self.do_rpc("store_agent_config", **params)

    def list_agent_configs(self, platform_uuid, agent_identity):
        """
        List the configuration files stored for an agent.

        :param platform_uuid: uuid of platform where agent is installed
        :param agent_identity: VIP identity of agent that owns the configs
        """
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity)
        return self.do_rpc("list_agent_configs", **params)

    def get_agent_config(self, platform_uuid, agent_identity, config_name,
                         raw=True):
        """
        Get a config file from an agent's Configuration Store

        :param platform_uuid: uuid of platform where agent is installed
        :param agent_identity: VIP identity of agent that owns the config
        :param config_name: name of the configuration file
        """
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity,
                      config_name=config_name,
                      raw=raw)
        return self.do_rpc("get_agent_config", **params)

    def set_setting(self, setting, value):
        """
        Assign a value to a setting in Volttron Central
        
        :param setting: Name of the setting to set
        :param value: Value to assign to setting
        """
        return self.do_rpc("set_setting", key=key, value=value)

    def get_setting(self, setting):
        """
        Get the value of a setting in Volttron Central

        :param setting: Name of the setting to get
        """
        return self.do_rpc("get_setting", key=key)

    def get_setting_keys(self):
        """
        Get a list of settings in Volttorn Central
        """
        return self.do_rpc("get_setting_keys")


def validate_response(response):
    """
    Validate that the message is a json-rpc response.

    :param response:
    :return:
    """
    assert response.ok
    rpcdict = response.json()
    assert rpcdict['jsonrpc'] == '2.0'
    assert rpcdict['id']
    assert 'error' in rpcdict.keys() or 'result' in rpcdict.keys()
