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

"""
Pytest test cases for testing actuator agent using rpc calls.
"""
from datetime import datetime, timedelta

import gevent
import pytest
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.known_identities import CONFIGURATION_STORE

class _config_test_agent(Agent):
    def __init__(self, **kwargs):
        super(_config_test_agent, self).__init__(**kwargs)
        self.callback_results = []

    def callback(self, config_name, action, contents):
        self.callback_results.append((config_name, action, contents))

    def setup_callback(self, actions = ("NEW", "UPDATE", "DELETE"), pattern = "*"):
        self.vip.config.subscribe(self.callback, actions=actions, pattern=pattern)

    def reset_results(self):
        self.callback_results = []

@pytest.fixture(scope="module")
def _module_config_test_agent(request, volttron_instance):

    agent = volttron_instance.build_agent(identity='config_test_agent',
                                          agent_class=_config_test_agent)

    def cleanup():
        agent.core.stop()

    request.addfinalizer(cleanup)
    return agent

@pytest.fixture(scope="module")
def rpc_agent(request, volttron_instance):

    agent = volttron_instance.build_agent(identity='rpc_agent',
                                          enable_store=False)

    def cleanup():
        agent.core.stop()

    request.addfinalizer(cleanup)
    return agent

@pytest.fixture(scope="function")
def config_test_agent(request, _module_config_test_agent, rpc_agent, volttron_instance):

    def cleanup():
        rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_store', 'config_test_agent').get()

    request.addfinalizer(cleanup)
    return _module_config_test_agent


@pytest.fixture(scope="function")
def default_config_test_agent(request, config_test_agent):
    #Prevent other broken tests from messing us up.
    config_test_agent.vip.config.unsubscribe_all()
    config_test_agent.reset_results()

    config_test_agent.setup_callback()

    def cleanup():
        config_test_agent.vip.config.unsubscribe_all()
        config_test_agent.reset_results()

    request.addfinalizer(cleanup)
    return config_test_agent



@pytest.mark.config_store
def test_manage_store_json(default_config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()


    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "NEW", {"value":1})


@pytest.mark.config_store
def test_manage_store_csv(default_config_test_agent, rpc_agent):
    csv_config = "value\n1"
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", csv_config, config_type="csv").get()

    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "NEW", [{"value": "1"}])

@pytest.mark.config_store
def test_manage_store_raw(default_config_test_agent, rpc_agent):
    raw_config = "test_config_stuff"
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", raw_config, config_type="raw").get()

    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "NEW", raw_config)

@pytest.mark.config_store
def test_manage_update_config(default_config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "NEW", {"value": 1})

    json_config = """{"value":2}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    assert len(results) == 2
    second = results[1]
    assert second == ("config", "UPDATE", {"value": 2})

@pytest.mark.config_store
def test_manage_delete_config(default_config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "NEW", {"value": 1})
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_config',
                           "config_test_agent", "config").get()
    assert len(results) == 2
    second = results[1]
    assert second == ("config", "DELETE", None)

@pytest.mark.config_store
def test_manage_delete_store(default_config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "NEW", {"value": 1})
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_store',
                           "config_test_agent").get()
    assert len(results) == 2
    second = results[1]
    assert second == ("config", "DELETE", None)

@pytest.mark.config_store
def test_manage_get_config(config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    config = rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_get',
                           "config_test_agent", "config", raw=False).get()

    assert config == {"value": 1}


@pytest.mark.config_store
def test_manage_get_raw_config(config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()


    config = rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_get',
                                    "config_test_agent", "config", raw=True).get()

    assert config == json_config

@pytest.mark.config_store
def test_manage_list_config(config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config1", json_config, config_type="json").get()
    json_config = """{"value":2}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config2", json_config, config_type="json").get()
    json_config = """{"value":3}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config3", json_config, config_type="json").get()

    config_list = rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_list_configs',
                                    "config_test_agent").get()

    assert config_list == ['config1', 'config2', 'config3']

@pytest.mark.config_store
def test_manage_list_store(config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config1", json_config, config_type="json").get()

    config_list = rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_list_stores').get()

    assert "config_test_agent" in config_list


@pytest.mark.config_store
def test_agent_list_config(default_config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config1", json_config, config_type="json").get()
    json_config = """{"value":2}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config2", json_config, config_type="json").get()
    json_config = """{"value":3}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config3", json_config, config_type="json").get()

    config_list = default_config_test_agent.vip.config.list()

    assert config_list == ['config1', 'config2', 'config3']

@pytest.mark.config_store
def test_agent_get_config(default_config_test_agent, rpc_agent):
    json_config = """{"value":1}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    config = default_config_test_agent.vip.config.get("config")

    assert config == {"value": 1}

@pytest.mark.config_store
def test_agent_reference_config_and_callback_order(default_config_test_agent, rpc_agent):
    json_config = """{"config2":"config://config2", "config3":"config://config3"}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config", json_config, config_type="json").get()

    config = default_config_test_agent.vip.config.get("config")

    assert config == {"config2":None, "config3":None}

    json_config = """{"value":2}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config2", json_config, config_type="json").get()

    #Also use th to verify that the callback for "config" is called first.

    default_config_test_agent.reset_results()

    json_config = """{"value":3}"""
    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "config_test_agent", "config3", json_config, config_type="json").get()

    config = default_config_test_agent.vip.config.get("config")

    assert config == {"config2": {"value":2}, "config3": {"value":3}}

    results = default_config_test_agent.callback_results
    assert len(results) == 2
    first = results[0]
    assert first == ("config", "UPDATE", {"config2": {"value":2}, "config3": {"value":3}})


    second = results[1]
    assert second == ("config3", "NEW", {"value":3})

@pytest.mark.config_store
def test_agent_set_config(default_config_test_agent):
    json_config = {"value":1}

    default_config_test_agent.vip.config.set("config", json_config)

    results = default_config_test_agent.callback_results
    assert len(results) == 0

    config = default_config_test_agent.vip.config.get("config")

    assert config == {"value": 1}

    default_config_test_agent.vip.config.set("config", json_config, trigger_callback=True)

    results = default_config_test_agent.callback_results
    assert len(results) == 1
    first = results[0]
    assert first == ("config", "UPDATE",  {"value": 1})

@pytest.mark.config_store
def test_agent_set_config_no_update(default_config_test_agent):
    json_config = {"value":1}

    default_config_test_agent.vip.config.set("config", json_config, trigger_callback=True, send_update=False)

    results = default_config_test_agent.callback_results
    assert len(results) == 0

    config_list = default_config_test_agent.vip.config.list()

    assert config_list == []


@pytest.mark.config_store
def test_agent_delete_config(default_config_test_agent):
    json_config = {"value":1}

    default_config_test_agent.vip.config.set("config", json_config, trigger_callback=True)
    default_config_test_agent.vip.config.delete("config", trigger_callback=True)

    results = default_config_test_agent.callback_results
    assert len(results) == 2
    first = results[0]
    assert first == ("config", "NEW",  {"value": 1})

    second = results[1]
    assert second == ("config", "DELETE", None)

@pytest.mark.config_store
def test_agent_default_config(request, rpc_agent, volttron_instance):

    def cleanup():
        rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_store', 'test_default_agent').get()
        agent.core.stop()

    request.addfinalizer(cleanup)


    class test_default_agent(_config_test_agent):
        def __init__(self, **kwargs):
            super(test_default_agent, self).__init__(**kwargs)
            self.vip.config.set_default("config", {"value":2})
            self.setup_callback()


    agent = volttron_instance.build_agent(identity='test_default_agent',
                                          agent_class=test_default_agent)

    #Give the agent a chance to process it's configurations.
    gevent.sleep(1.0)

    results = agent.callback_results
    assert len(results) == 1
    result = results[0]
    assert result == ("config", "NEW", {"value": 2})

    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                           "test_default_agent", "config", '{"value": 1}', config_type="json").get()

    assert len(results) == 2
    result = results[-1]
    assert result == ("config", "UPDATE", {"value": 1})

    rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_config',
                           "test_default_agent", "config").get()

    assert len(results) == 3
    result = results[-1]
    assert result == ("config", "UPDATE", {"value": 2})

@pytest.mark.config_store
def test_agent_sub_options(request, rpc_agent, volttron_instance):

    def cleanup():
        rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_store', 'test_agent_sub_options').get()
        agent.core.stop()

    request.addfinalizer(cleanup)


    class test_sub_pattern_agent(_config_test_agent):
        def __init__(self, **kwargs):
            super(test_sub_pattern_agent, self).__init__(**kwargs)
            self.setup_callback(actions="NEW", pattern="new/*")
            self.setup_callback(actions="UPDATE", pattern="update/*")
            self.setup_callback(actions="DELETE", pattern="delete/*")


    agent = volttron_instance.build_agent(identity='test_agent_sub_options',
                                          agent_class=test_sub_pattern_agent)

    #Give the agent a chance to process it's configurations.
    gevent.sleep(1.0)

    new_json = """{"value": 1}"""
    update_json = """{"value": 2}"""

    for name in ("new/config", "update/config", "delete/config"):
        rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                               "test_agent_sub_options", name, new_json, config_type="json").get()

        rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_store',
                               "test_agent_sub_options", name, update_json, config_type="json").get()

        rpc_agent.vip.rpc.call(CONFIGURATION_STORE, 'manage_delete_config',
                               "test_agent_sub_options", name).get()

    results = agent.callback_results

    assert len(results) == 3

    new_result = results[0]
    assert new_result == ("new/config", "NEW", {"value": 1})

    update_result = results[1]
    assert update_result == ("update/config", "UPDATE", {"value": 2})

    delete_result = results[2]
    assert delete_result == ("delete/config", "DELETE", None)





