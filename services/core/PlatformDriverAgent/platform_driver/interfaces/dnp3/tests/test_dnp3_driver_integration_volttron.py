import pytest
import gevent
import logging
import time
import random

from volttron.platform import get_services_core, jsonapi

from volttron.platform.agent.known_identities import PLATFORM_DRIVER

from pydnp3 import opendnp3

from dnp3_python.dnp3station.outstation_new import MyOutStationNew
from pathlib import Path

import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


# TODO: add IP, port pool to avoid conflict
# TODO: make sleep more robust and flexible. (Currently relies on manually setup sleep time.)


class TestDummy:
    """
    Dummy test to check pytest setup
    """

    def test_dummy(self):
        print("I am a silly dummy test.")


@pytest.fixture(
    scope="class"
)
def outstation_app_p20000():
    """
    outstation using default configuration (including default database)
    Note: since outstation cannot shut down gracefully,
    outstation_app fixture need to in "module" scope to prevent interrupting pytest during outstation shut-down
    """
    port = 20000
    outstation_appl = MyOutStationNew(port=port)  # Note: using default port 20000
    outstation_appl.start()
    gevent.sleep(10)
    yield outstation_appl

    outstation_appl.shutdown()


@pytest.mark.skip(reason="only for debugging purpose")
class TestDummyAgentFixture:
    """
    Dummy test to check VOLTTRON agent (carry on test VOLTTRON instance) setup
    """

    def test_agent_dummy(self, dnp3_tester_agent):
        print("I am a fixture agent dummy test.")


class TestDnp3DriverRPC:

    def test_interface_get_point(
            self,
            dnp3_tester_agent,
            outstation_app_p20000,
    ):
        val_update = 7.124 + random.random()
        outstation_app_p20000.apply_update(opendnp3.Analog(value=val_update,
                                                           flags=opendnp3.Flags(24),
                                                           time=opendnp3.DNPTime(3094)),
                                           index=0)

        time.sleep(2)

        res_val = dnp3_tester_agent.vip.rpc.call("platform.driver", "get_point",
                                                 "campus-vm/building-vm/Dnp3-port20000",
                                                 "AnalogInput_index0").get(timeout=5)

        print(f"======res_val {res_val}")
        assert res_val == val_update

    def test_interface_set_point(
            self,
            dnp3_tester_agent,
            outstation_app_p20000,
    ):
        val_set = 8.342 + random.random()

        res_val = dnp3_tester_agent.vip.rpc.call("platform.driver", "set_point",
                                                 "campus-vm/building-vm/Dnp3-port20000",
                                                 "AnalogOutput_index0", val_set).get(timeout=5)

        # print(f"======res_val {res_val}")
        # Expected output
        # {'success_flag': True, 'value_to_set': 8.342, 'set_pt_response': None, 'get_pt_response': 8.342}
        try:
            assert res_val.get("success_flag")
        except AssertionError:
            print(f"======res_val {res_val}")

    @pytest.mark.skip(reason="TODO")
    def test_scrape_all(self, ):
        """
        Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @return: The dictionary mapping point names to their actual values from
        the RPC call.
        """
        # return agent.vip.rpc.call(PLATFORM_DRIVER, 'scrape_all', device_name) \
        #     .get(timeout=10)

    @pytest.mark.skip(reason="TODO")
    def test_revert_all(self, ):
        """
        Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @return: Return value from the RPC call.
        """
        # return agent.vip.rpc.call(PLATFORM_DRIVER, 'revert_device',
        #                           device_name).get(timeout=10)

    @pytest.mark.skip(reason="TODO")
    def test_revert_point(self, ):
        """
        Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @param point_name: The name of the point to query.
        @return: Return value from the RPC call.
        """
        # return agent.vip.rpc.call(PLATFORM_DRIVER, 'revert_point',
        #                           device_name, point_name).get(timeout=10)


@pytest.fixture(scope="module")
# @pytest.fixture
def dnp3_tester_agent(request, volttron_instance):
    """
    Build PlatformDriverAgent, add modbus driver & csv configurations
    """

    # Build platform driver agent
    tester_agent = volttron_instance.build_agent(identity="test_dnp3_agent")
    gevent.sleep(1)
    capabilities = {'edit_config_store': {'identity': PLATFORM_DRIVER}}
    # Note: commented out the add_capabilities due to complained by volttron_instance fixture, i.e.,
    # pytest.param(dict(messagebus='rmq', ssl_auth=True),
    #              marks=rmq_skipif),  # complain add_capabilities
    #              dict(messagebus='zmq', auth_enabled=False), # complain add_capabilities
    if volttron_instance.auth_enabled:
        volttron_instance.add_capabilities(tester_agent.core.publickey, capabilities)

    # Clean out platform driver configurations
    # wait for it to return before adding new config
    tester_agent.vip.rpc.call(peer='config.store',
                              method='manage_delete_store',
                              identity=PLATFORM_DRIVER).get(timeout=5)

    json_config_path = Path("../examples/dnp3.config")
    json_config_path = Path(TEST_DIR, json_config_path)
    with open(json_config_path, "r") as f:
        json_str_p20000 = f.read()

    csv_config_path = Path("../examples/dnp3.csv")
    csv_config_path = Path(TEST_DIR, csv_config_path)
    with open(csv_config_path, "r") as f:
        csv_str = f.read()

    tester_agent.vip.rpc.call(peer='config.store',
                              method='manage_store',
                              identity=PLATFORM_DRIVER,
                              config_name="dnp3.csv",
                              raw_contents=csv_str,
                              config_type='csv'
                              ).get(timeout=5)

    tester_agent.vip.rpc.call('config.store',
                              method='manage_store',
                              identity=PLATFORM_DRIVER,
                              config_name="devices/campus-vm/building-vm/Dnp3-port20000",
                              raw_contents=json_str_p20000,
                              config_type='json'
                              ).get(timeout=5)

    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={},
        start=True)

    gevent.sleep(10)  # Note: important, wait for the agent to start and start the devices, otherwise rpc call may fail.
    # time.sleep(10)  # wait for the agent to start and start the devices

    def stop():
        """
        Stop platform driver agent
        """
        volttron_instance.stop_agent(platform_uuid)
        tester_agent.core.stop()

    yield tester_agent
    request.addfinalizer(stop)
