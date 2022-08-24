# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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
py.test cases for global override settings.
"""

import pytest

from volttron.platform import get_services_core
from volttrontesting.utils.platformwrapper import start_wrapper_platform
from volttron.platform.agent.known_identities import PLATFORM_DRIVER, CONFIGURATION_STORE
import gevent
from volttron.platform.jsonrpc import RemoteError

TEST_AGENT = 'test-agent'
TEST1_AGENT = 'test1-agent'
SET_FAILURE = 0.0
REVERT_FAILURE = 0.0
master_uuid = ''
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

master_driver_config = """
{{
    "driver_scrape_interval": 0.05,
    "publish_breadth_first_all": false,
    "publish_depth_first_all": true,
    "publish_depth_first": false,
    "publish_breadth_first": false
}}
"""


# registry_config_string = """Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
# Float,Float,F,-100 to 300,TRUE,50,float,CO2 Reading 0.00-2000.0 ppm
# FloatNoDefault,FloatNoDefault,F,-100 to 300,TRUE,,float,CO2 Reading 0.00-2000.0 ppm
# """


@pytest.fixture(scope="module")
def config_store_connection(request, volttron_instance):
    capabilities = [{'edit_config_store': {'identity': PLATFORM_DRIVER}}]
    connection = volttron_instance.build_connection(peer=CONFIGURATION_STORE, capabilities=capabilities)
    # Reset master driver config store
    connection.call("manage_delete_store", PLATFORM_DRIVER)

    # Start the master driver agent which would in turn start the fake driver
    #  using the configs created above
    master_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    def stop_agent():
        volttron_instance.stop_agent(master_uuid)
        volttron_instance.remove_agent(master_uuid)
        connection.kill()

    request.addfinalizer(stop_agent)

    return connection


@pytest.fixture(scope="function")
def config_store(request, config_store_connection):
    # Always have fake.csv ready to go.

    # Add up fake.csv to config store
    config_path = "scripts/scalability-testing/fake_unit_testing.csv"
    with open(config_path, 'r') as f:
        registry_config_string = f.read()
    f.closed
    config_store_connection.call("manage_store", PLATFORM_DRIVER, "fake.csv", registry_config_string, config_type="csv")

    def cleanup():
        # Reset master driver config store
        print("Wiping out store.")
        config_store_connection.call("manage_delete_store", PLATFORM_DRIVER)
        gevent.sleep(0.1)

    request.addfinalizer(cleanup)

    return config_store_connection


def setup_config(config_store, config_name, config_string, **kwargs):
    config = config_string.format(**kwargs)
    print("Adding", config_name, "to store")
    config_store.call("manage_store", PLATFORM_DRIVER, config_name, config, config_type="json")


@pytest.fixture(scope="module")
def test_agent(request, volttron_instance):
    test_agent = volttron_instance.build_agent(identity=TEST_AGENT)
    def stop_agent():
        # result = test_agent.vip.rpc.call(
        #     PLATFORM_DRIVER,  # Target agent
        #     'clear_overrides'  # Method
        # ).get(timeout=10)
        test_agent.core.stop()

    # Add a tear down method to stop test agent
    request.addfinalizer(stop_agent)
    return test_agent


@pytest.mark.driver
def test_set_override(config_store, test_agent):
    setup_config(config_store, "config", master_driver_config)
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    device_path = "fakedriver1"
    gevent.sleep(1.1)
    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        2,  # Duration for override in secs
        True,  # Revert to default state is required
        True  # Staggered revert
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(1.1)

    try:
        # set point after override
        point = 'SampleWritableShort1'
        value = 20.0
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            device_path,  # device path
            point,
            value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned: {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            device_path)

    try:
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'revert_device',  # Method
            device_path  # device path
        ).get(timeout=10)

        pytest.fail("Expecting Override Error. Code returned: {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot revert device {} since global override is set'.format(
            device_path)


@pytest.mark.driver
def test_set_point_after_override_elapsed_interval(config_store, test_agent):
    setup_config(config_store, "config", master_driver_config)
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)

    device_path = 'fakedriver1'
    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        1,  # Duration for override in secs
        True,  # revert to default
        True  # staggered revert
    ).get(timeout=10)

    # Give it enough time to send the override request and override interval to timeout
    gevent.sleep(2)

    try:
        point = 'SampleWritableShort1'
        new_value = 30.0
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        assert result == new_value
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            device_path)
        pytest.fail("Expecting successful set point. Code raised OverrideError: {}".format(e.message))


#
@pytest.mark.driver
def test_set_hierarchical_override(config_store, test_agent):
    setup_config(config_store, "config", master_driver_config)
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    device_path = '*'
    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        1,  # Duration for override in secs
        True,
        True
    ).get(timeout=10)

    try:
        fakedriver1_path = 'fakedriver2'
        point = 'SampleWritableFloat'
        value = 12.5
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver1_path,  # device path
            point,
            value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned: {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver1_path)
    gevent.sleep(4)


@pytest.mark.driver
def test_set_override_no_revert(config_store, test_agent):
    setup_config(config_store, "config", master_driver_config)
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    device_path = 'fakedriver1'
    point = 'SampleWritableFloat1'
    old_value = 0.0
    # Get get device point value
    old_value = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'get_point',  # Method
        device_path,  # device path
        point
    ).get(timeout=10)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        2,  # Duration for override in secs
        False,  # revert flag to False
        False
    ).get(timeout=10)

    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'get_point',  # Method
        device_path,  # device path
        point
    ).get(timeout=10)
    assert result == old_value
    gevent.sleep(2)


@pytest.mark.driver
def test_set_override_off(config_store, test_agent):
    setup_config(config_store, "config", master_driver_config)
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    device_path = 'fakedriver1'

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        60,  # Duration for override in secs
        False,  # revert flag to False
        True
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(1.1)

    # Get override devices list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'get_override_devices'  # Method
    ).get(timeout=10)
    assert result == ['fakedriver1']

    # Get override patterns list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'get_override_patterns'  # Method
    ).get(timeout=10)
    assert result == ['fakedriver1']

    # Remove override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_off',  # Method
        device_path  # Override Pattern
    ).get(timeout=10)

    try:
        point = 'SampleWritableFloat1'
        value = 12.5
        # Try to set a point
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            device_path,  # device path
            point,
            value
        ).get(timeout=10)
        assert result == value
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            device_path)
        pytest.fail("Expecting successful set point. Code raised OverrideError: {}".format(e.message))

    # Get override patterns list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'get_override_patterns',  # Method
    ).get(timeout=10)
    assert result == []

    # Get override devices list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'get_override_devices',  # Method
    ).get(timeout=10)
    assert result == []


@pytest.mark.driver
def test_overlapping_override_onoff(config_store, test_agent):
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)

    fakedriver1_device_path = 'fakedriver1'
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        fakedriver1_device_path,  # Override Pattern
        5,  # Duration for override in secs
        False  # revert flag to False
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    device_path = '*'
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        5,  # Duration for override in secs
        False,
        False  # revert flag to False
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    fakedriver1_device_path = 'fakedriver1'
    # Remove override feature on fakedriver1 alone
    point = 'SampleWritableFloat1'
    new_value = 65.5
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_off',  # Method
        fakedriver1_device_path  # Override Pattern
    ).get(timeout=10)

    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver1_device_path)

    try:
        # Try to set a point on fakedriver2
        fakedriver2_device_path = 'fakedriver2'
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver2_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver2_device_path)

    # Wait for timeout
    gevent.sleep(6)
    try:
        # Try to set a point on fakedriver2
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver2_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        assert result == new_value
        print("New value of fake driver2, SampleWritableFloat1: {}".format(new_value))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver2_device_path)
        pytest.fail("Expecting successful set point. Code raised OverrideError: {}".format(e.message))


@pytest.mark.driver
def test_overlapping_override_onoff2(config_store, test_agent):
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    all_device_path = '*'
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        all_device_path,  # Override Pattern
        5,  # Duration for override in secs
        True,  # revert flag to True
        True
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    fakedriver1_device_path = 'fakedriver1'
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        fakedriver1_device_path,  # Override Pattern
        2,  # Duration for override in secs
        False  # revert flag to False
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    # Remove override feature on '*'
    all_device_path = '*'
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_off',  # Method
        all_device_path  # Override Pattern
    ).get(timeout=10)

    point = 'SampleWritableFloat1'
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver1_device_path)

    try:
        # Try to set a point on fakedriver2
        fakedriver2_device_path = 'fakedriver2'
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver2_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        assert result == new_value
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver2_device_path)
        pytest.fail("Expecting successful set point. Code raised OverrideError: {}".format(e.message))

    # Wait for timeout
    gevent.sleep(6)

    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        assert result == new_value
        print("New value of fake driver1, SampleWritableFloat1: {}".format(new_value))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver1_device_path)
        pytest.fail("Expecting successful set point. Code raised OverrideError: {}".format(e.message))


@pytest.mark.driver
def test_duplicate_override_on(config_store, test_agent):
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    all_device_path = '*'
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        all_device_path,  # Override Pattern
        1,  # Duration for override in secs
        True,  # revert flag to True
        True
    ).get(timeout=10)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        all_device_path,  # Override Pattern
        0.5,  # Duration for override in secs
        True,  # revert flag to True
        True
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.8)

    fakedriver1_device_path = 'fakedriver1'
    point = 'SampleWritableFloat1'
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            fakedriver1_device_path)


@pytest.mark.driver
def test_indefinite_override_on(config_store, test_agent):
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    device_path = 'fakedriver2'
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        -1,  # Indefinite override
        False,  # revert flag to True
        False
    ).get(timeout=10)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        0.5,  # Duration for override in secs
        True,  # revert flag to True
        True
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.8)

    point = 'SampleWritableFloat1'
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            device_path)
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'clear_overrides'  # Method
    ).get(timeout=10)


@pytest.mark.driver
def test_indefinite_override_after_restart(config_store, test_agent, volttron_instance):
    for i in range(4):
        config_name = "devices/fakedriver{}".format(i)
        setup_config(config_store, config_name, fake_device_config)
    device_path = 'fakedriver2'

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'set_override_on',  # Method
        device_path,  # Override Pattern
        0.0,  # Indefinite override
        False,  # revert flag to True
        False
    ).get(timeout=10)

    # Give it enough time to set indefinite override.
    gevent.sleep(0.5)
    global master_uuid
    volttron_instance.stop_agent(master_uuid)
    gevent.sleep(0.5)
    # Start the master driver agent which would in turn start the fake driver
    #  using the configs created above
    volttron_instance.start_agent(master_uuid)
    gevent.sleep(1)  # wait for the agent to start and start the devices

    point = 'SampleWritableFloat1'
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            'set_point',  # Method
            device_path,  # device path
            point,
            new_value
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'].endswith('OverrideError')
        assert e.message == 'Cannot set point on device {} since global override is set'.format(
            device_path)
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        'clear_overrides'  # Method
    ).get(timeout=10)


@pytest.mark.driver
def test_override_pattern(config_store, test_agent):
    setup_config(config_store, "config", master_driver_config)
    # add a fake driver
    config_path = "devices/{}"
    device_path = "fakedriver1"
    config_name = config_path.format(device_path)
    setup_config(config_store, config_name, fake_device_config)
    gevent.sleep(1.1)
    # set override feature on device
    test_agent.vip.rpc.call(PLATFORM_DRIVER, 'set_override_on', device_path, 2, True, True).get(timeout=10)
    # Give it enough time to send the override request, then ensure that it has created the override
    gevent.sleep(1.1)
    devices = test_agent.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices").get(timeout=3)
    assert device_path in devices

    test_agent.vip.rpc.call(PLATFORM_DRIVER, "clear_overrides")

    # add an override pattern with capitalization that doesn't match an installed driver
    camel_device_path = "fakeDriver1"
    test_agent.vip.rpc.call(PLATFORM_DRIVER, 'set_override_on', camel_device_path, 2, True, True).get(timeout=10)
    # Give it enough time to send the override request, then ensure that it has created the override
    gevent.sleep(1.1)
    devices = test_agent.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices").get(timeout=3)
    assert not devices

    # add another device to the store using the same string with different casing
    config_name = config_path.format(camel_device_path)
    setup_config(config_store, config_name, fake_device_config)
    gevent.sleep(1.1)
    # set override feature on device
    test_agent.vip.rpc.call(PLATFORM_DRIVER, 'set_override_on', camel_device_path, 2, True, True).get(timeout=10)
    gevent.sleep(1.1)
    devices = test_agent.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices").get(timeout=3)
    assert camel_device_path in devices
    assert device_path not in devices
