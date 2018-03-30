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
py.test cases for global master driver settings.
"""

import pytest

from volttron.platform import get_services_core
from volttrontesting.utils.platformwrapper import start_wrapper_platform
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
import gevent
from volttron.platform.vip.agent import Agent, PubSub
from volttron.platform.messaging import topics


class _subscriber_agent(Agent):
    def __init__(self, **kwargs):
        super(_subscriber_agent, self).__init__(**kwargs)
        self.publish_results = set()

    def reset_results(self):
        print "Resetting results"
        self.publish_results.clear()

    def get_results(self):
        return self.publish_results.copy()

    def add_result(self, peer, sender, bus, topic, headers, message):
        print "message published to", topic
        self.publish_results.add(topic)


@pytest.fixture(scope="module")
def subscriber_agent(request, volttron_instance1):

    agent = volttron_instance1.build_agent(identity='subscriber_agent',
                                          agent_class=_subscriber_agent)

    agent.vip.pubsub.subscribe(peer='pubsub',
                                prefix=topics.DRIVER_TOPIC_BASE,
                                callback=agent.add_result).get()

    def cleanup():
        agent.core.stop()

    request.addfinalizer(cleanup)
    return agent

fake_device_config = """
{{
    "driver_config": {{}},
    "registry_config":"config://fake.csv",
    "interval": 1,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat",
    "driver_type": "fakedriver"

}}
"""

fake_device_config_override = """
{{
    "driver_config": {{}},
    "registry_config":"config://fake.csv",
    "interval": 1,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat",
    "driver_type": "fakedriver",
    "publish_breadth_first_all": {breadth_all},
    "publish_depth_first_all": {depth_all},
    "publish_depth_first": {depth},
    "publish_breadth_first": {breadth}

}}
"""

fake_device_config_single_override = """
{{
    "driver_config": {{}},
    "registry_config":"config://fake.csv",
    "interval": 1,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat",
    "driver_type": "fakedriver",
    {override_param}

}}
"""

master_driver_config = """
{{
    "driver_scrape_interval": 0.05,
    "publish_breadth_first_all": {breadth_all},
    "publish_depth_first_all": {depth_all},
    "publish_depth_first": {depth},
    "publish_breadth_first": {breadth}
}}
"""

master_driver_config_default = """
{{
    "driver_scrape_interval": 0.05
}}
"""

registry_config_string = """Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
Float,Float,F,-100 to 300,TRUE,50,float,CO2 Reading 0.00-2000.0 ppm
FloatNoDefault,FloatNoDefault,F,-100 to 300,TRUE,,float,CO2 Reading 0.00-2000.0 ppm
"""

depth_all_set = set(['devices/fake/all'])
breadth_all_set = set(['devices/all/fake'])
depth_set = set(['devices/fake/Float', 'devices/fake/FloatNoDefault'])
breadth_set = set(['devices/Float/fake', 'devices/FloatNoDefault/fake'])

@pytest.fixture(scope="module")
def config_store_connection(request, volttron_instance1):

    connection = volttron_instance1.build_connection(peer=CONFIGURATION_STORE)
    # Reset master driver config store
    connection.call("manage_delete_store", PLATFORM_DRIVER)

    # Start the master driver agent which would in turn start the fake driver
    #  using the configs created above
    master_uuid = volttron_instance1.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices


    def stop_agent():
        volttron_instance1.stop_agent(master_uuid)
        volttron_instance1.remove_agent(master_uuid)
        connection.kill()

    request.addfinalizer(stop_agent)

    return connection

@pytest.fixture(scope="function")
def config_store(request, config_store_connection):
    #Always have fake.csv ready to go.
    print "Adding fake.csv into store"
    config_store_connection.call("manage_store", PLATFORM_DRIVER, "fake.csv", registry_config_string, config_type="csv")

    def cleanup():
        # Reset master driver config store
        print "Wiping out store."
        config_store_connection.call("manage_delete_store", PLATFORM_DRIVER)
        gevent.sleep(0.1)

    request.addfinalizer(cleanup)

    return config_store_connection

def setup_config(config_store, config_name, config_string, **kwargs):
    config = config_string.format(**kwargs)
    print "Adding", config_name, "to store"
    config_store.call("manage_store", PLATFORM_DRIVER, config_name, config, config_type="json")


@pytest.mark.driver
def test_default_publish(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config_default)
    setup_config(config_store, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set

@pytest.mark.driver
def test_default_global_off(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")
    setup_config(config_store, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == set()

@pytest.mark.driver
def test_default_global_breadth_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="true",
                 depth_all="false",
                 breadth="false",
                 depth="false")
    setup_config(config_store, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_all_set

@pytest.mark.driver
def test_default_global_depth_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="true",
                 breadth="false",
                 depth="false")
    setup_config(config_store, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set

@pytest.mark.driver
def test_default_global_depth(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="true")
    setup_config(config_store, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_set

@pytest.mark.driver
def test_default_global_breadth(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="true",
                 depth="false")
    setup_config(config_store, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_set


@pytest.mark.driver
def test_default_override_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_override,
                 breadth_all="true",
                 depth_all="true",
                 breadth="true",
                 depth="true")

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set | breadth_all_set | depth_set | breadth_set


@pytest.mark.driver
def test_default_override_breadth_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_override,
                 breadth_all="true",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_all_set


@pytest.mark.driver
def test_default_override_depth_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_override,
                 breadth_all="false",
                 depth_all="true",
                 breadth="false",
                 depth="false")

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set


@pytest.mark.driver
def test_default_override_depth(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_override,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="true")

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_set

@pytest.mark.driver
def test_default_override_breadth(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_override,
                 breadth_all="false",
                 depth_all="false",
                 breadth="true",
                 depth="false")

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_set


@pytest.mark.driver
def test_default_override_single_breadth_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_single_override,
                 override_param='"publish_breadth_first_all": true')

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_all_set


@pytest.mark.driver
def test_default_override_single_depth_all(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_single_override,
                 override_param='"publish_depth_first_all": true')

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set


@pytest.mark.driver
def test_default_override_single_depth(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_single_override,
                 override_param='"publish_depth_first": true')

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_set

@pytest.mark.driver
def test_default_override_single_breadth(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config,
                 breadth_all="false",
                 depth_all="false",
                 breadth="false",
                 depth="false")

    setup_config(config_store, "devices/fake", fake_device_config_single_override,
                 override_param='"publish_breadth_first": true')

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_set