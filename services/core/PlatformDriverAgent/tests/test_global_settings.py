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

"""
py.test cases for global platform driver settings.
"""

import pytest
import gevent

from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.platform.vip.agent import Agent
from volttron.platform.messaging import topics


class _subscriber_agent(Agent):
    def __init__(self, **kwargs):
        super(_subscriber_agent, self).__init__(**kwargs)
        self.publish_results = set()

    def reset_results(self):
        print("Resetting results")
        self.publish_results.clear()

    def get_results(self):
        return self.publish_results.copy()

    def add_result(self, peer, sender, bus, topic, headers, message):
        print("message published to", topic)
        self.publish_results.add(topic)


# def subscriber_agent(request, volttron_instance):
@pytest.fixture(scope="module")
def subscriber_agent(request, volttron_instance):

    agent = volttron_instance.build_agent(
        identity="subscriber_agent", agent_class=_subscriber_agent
    )

    agent.vip.pubsub.subscribe(
        peer="pubsub", prefix=topics.DRIVER_TOPIC_BASE, callback=agent.add_result
    ).get()

    yield agent

    agent.core.stop()


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

platform_driver_config = """
{{
    "driver_scrape_interval": 0.05,
    "publish_breadth_first_all": {breadth_all},
    "publish_depth_first_all": {depth_all},
    "publish_depth_first": {depth},
    "publish_breadth_first": {breadth}
}}
"""

platform_driver_config_default = """
{{
    "driver_scrape_interval": 0.05
}}
"""

registry_config_string = """Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
Float,Float,F,-100 to 300,TRUE,50,float,CO2 Reading 0.00-2000.0 ppm
FloatNoDefault,FloatNoDefault,F,-100 to 300,TRUE,,float,CO2 Reading 0.00-2000.0 ppm
"""

depth_all_set = set(["devices/fake/all"])
breadth_all_set = set(["devices/all/fake"])
depth_set = set(["devices/fake/Float", "devices/fake/FloatNoDefault"])
breadth_set = set(["devices/Float/fake", "devices/FloatNoDefault/fake"])


@pytest.fixture(scope="module")
def test_agent(volttron_instance):
    """
    Build a test_agent, PlatformDriverAgent
    """

    # Build a test agent
    md_agent = volttron_instance.build_agent(identity="test_md_agent")
    gevent.sleep(1)

    if volttron_instance.auth_enabled:
        capabilities = {"edit_config_store": {"identity": PLATFORM_DRIVER}}
        volttron_instance.add_capabilities(md_agent.core.publickey, capabilities)

    # Clean out platform driver configurations
    # wait for it to return before adding new config
    md_agent.vip.rpc.call("config.store", "delete_store", PLATFORM_DRIVER).get()

    # Add a fake.csv to the config store
    md_agent.vip.rpc.call(
        "config.store",
        "set_config",
        PLATFORM_DRIVER,
        "fake.csv",
        registry_config_string,
        config_type="csv",
    ).get()

    # install the PlatformDriver
    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"), config_file={}, start=True
    )

    gevent.sleep(10)  # wait for the agent to start and start the devices

    yield md_agent

    volttron_instance.stop_agent(platform_uuid)
    md_agent.core.stop()


def setup_config(test_agent, config_name, config_string, **kwargs):
    config = config_string.format(**kwargs)
    print("Adding", config_name, "to store")
    test_agent.vip.rpc.call(
        "config.store",
        "set_config",
        PLATFORM_DRIVER,
        config_name,
        config,
        config_type="json",
    ).get()


@pytest.mark.driver
def test_default_publish(test_agent, subscriber_agent):
    setup_config(test_agent, "config", platform_driver_config_default)
    setup_config(test_agent, "devices/fake", fake_device_config)
    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set


@pytest.mark.driver
def test_default_global_off(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )
    setup_config(test_agent, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == set()


@pytest.mark.driver
def test_default_global_breadth_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="true",
        depth_all="false",
        breadth="false",
        depth="false",
    )
    setup_config(test_agent, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_all_set


@pytest.mark.driver
def test_default_global_depth_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="true",
        breadth="false",
        depth="false",
    )
    setup_config(test_agent, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set


@pytest.mark.driver
def test_default_global_depth(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="true",
    )
    setup_config(test_agent, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_set


@pytest.mark.driver
def test_default_global_breadth(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="true",
        depth="false",
    )
    setup_config(test_agent, "devices/fake", fake_device_config)

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_set


@pytest.mark.driver
def test_default_override_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_override,
        breadth_all="true",
        depth_all="true",
        breadth="true",
        depth="true",
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set | breadth_all_set | depth_set | breadth_set


@pytest.mark.driver
def test_default_override_breadth_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_override,
        breadth_all="true",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_all_set


@pytest.mark.driver
def test_default_override_depth_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_override,
        breadth_all="false",
        depth_all="true",
        breadth="false",
        depth="false",
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set


@pytest.mark.driver
def test_default_override_depth(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_override,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="true",
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_set


@pytest.mark.driver
def test_default_override_breadth(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_override,
        breadth_all="false",
        depth_all="false",
        breadth="true",
        depth="false",
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_set


@pytest.mark.driver
def test_default_override_single_breadth_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_single_override,
        override_param='"publish_breadth_first_all": true',
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_all_set


@pytest.mark.driver
def test_default_override_single_depth_all(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_single_override,
        override_param='"publish_depth_first_all": true',
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_all_set


@pytest.mark.driver
def test_default_override_single_depth(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_single_override,
        override_param='"publish_depth_first": true',
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == depth_set


@pytest.mark.driver
def test_default_override_single_breadth(test_agent, subscriber_agent):
    setup_config(
        test_agent,
        "config",
        platform_driver_config,
        breadth_all="false",
        depth_all="false",
        breadth="false",
        depth="false",
    )

    setup_config(
        test_agent,
        "devices/fake",
        fake_device_config_single_override,
        override_param='"publish_breadth_first": true',
    )

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(1.1)

    results = subscriber_agent.get_results()

    assert results == breadth_set
