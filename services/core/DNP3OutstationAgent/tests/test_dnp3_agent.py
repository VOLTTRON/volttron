"""
This test suits focus on the exposed RPC calls.
It utilizes a vip agent to evoke the RPC calls.
The volltron instance and dnp3-agent is start manually.
Note: several fixtures are used
    volttron_platform_wrapper
    vip_agent
    dnp3_outstation_agent
"""
import pathlib

import gevent
import pytest
import os
# from volttron.client.vip.agent import build_agent
from volttron.platform.vip.agent.utils import build_agent
from time import sleep
import datetime
from dnp3_outstation.agent import Dnp3OutstationAgent
from dnp3_python.dnp3station.outstation_new import MyOutStationNew
import random
import subprocess
from volttron.utils import is_volttron_running
import json
# from utils.testing_utils import *
from volttrontesting.fixtures.volttron_platform_fixtures import volttron_instance

import logging

logging_logger = logging.getLogger(__name__)

dnp3_vip_identity = "dnp3_outstation"


@pytest.fixture(scope="module")
def volttron_home():
    """
    VOLTTRON_HOME environment variable suggested to setup at pytest.ini [env]
    """
    volttron_home: str = os.getenv("VOLTTRON_HOME")
    assert volttron_home
    return volttron_home


def test_volttron_home_fixture(volttron_home):
    assert volttron_home
    print(volttron_home)


def test_testing_file_path():
    parent_path = os.getcwd()
    dnp3_agent_config_path = os.path.join(parent_path, "dnp3-outstation-config.json")
    # print(dnp3_agent_config_path)
    logging_logger.info(f"test_testing_file_path {dnp3_agent_config_path}")


def test_volttron_instance_fixture(volttron_instance):
    print(volttron_instance)
    logging_logger.info(f"=========== volttron_instance_new.volttron_home: {volttron_instance.volttron_home}")
    logging_logger.info(f"=========== volttron_instance_new.skip_cleanup: {volttron_instance.skip_cleanup}")
    logging_logger.info(f"=========== volttron_instance_new.vip_address: {volttron_instance.vip_address}")


@pytest.fixture(scope="module")
def vip_agent(volttron_instance):
    # build a vip agent
    a = volttron_instance.build_agent()
    print(a)
    return a


def test_vip_agent_fixture(vip_agent):
    print(vip_agent)
    logging_logger.info(f"=========== vip_agent: {vip_agent}")
    logging_logger.info(f"=========== vip_agent.core.identity: {vip_agent.core.identity}")
    logging_logger.info(f"=========== vip_agent.vip.peerlist().get(): {vip_agent.vip.peerlist().get()}")


@pytest.fixture(scope="module")
def dnp3_outstation_agent(volttron_instance) -> dict:
    """
    Install and start a dnp3-outstation-agent, return its vip-identity
    """
    # install a dnp3-outstation-agent
    # TODO: improve the following hacky path resolver
    parent_path = pathlib.Path(__file__)
    dnp3_outstation_package_path = pathlib.Path(parent_path).parent.parent
    dnp3_agent_config_path = str(os.path.join(parent_path, "dnp3-outstation-config.json"))
    config = {
        "outstation_ip": "0.0.0.0",
        "master_id": 2,
        "outstation_id": 1,
        "port": 20000
    }
    agent_vip_id = dnp3_vip_identity
    uuid = volttron_instance.install_agent(
        agent_dir=dnp3_outstation_package_path,
        # agent_dir="volttron-dnp3-outastion",
        config_file=config,
        start=False,  # Note: for some reason, need to set to False, then start
        vip_identity=agent_vip_id)
    # start agent with retry
    # pid = retry_call(volttron_instance.start_agent, f_kwargs=dict(agent_uuid=uuid), max_retries=5, delay_s=2,
    #                  wait_before_call_s=2)

    # # check if running with retry
    # retry_call(volttron_instance.is_agent_running, f_kwargs=dict(agent_uuid=uuid), max_retries=5, delay_s=2,
    #            wait_before_call_s=2)
    gevent.sleep(5)
    pid = volttron_instance.start_agent(uuid)
    gevent.sleep(5)
    logging_logger.info(
        f"=========== volttron_instance.is_agent_running(uuid): {volttron_instance.is_agent_running(uuid)}")
    # TODO: get retry_call back
    return {"uuid": uuid, "pid": pid}


def test_install_dnp3_outstation_agent_fixture(dnp3_outstation_agent, vip_agent, volttron_instance):
    puid = dnp3_outstation_agent
    print(puid)
    logging_logger.info(f"=========== dnp3_outstation_agent ids: {dnp3_outstation_agent}")
    logging_logger.info(f"=========== vip_agent.vip.peerlist().get(): {vip_agent.vip.peerlist().get()}")
    logging_logger.info(f"=========== volttron_instance_new.is_agent_running(puid): "
                        f"{volttron_instance.is_agent_running(dnp3_outstation_agent['uuid'])}")


def test_dummy(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.rpc_dummy
    peer_method = method.__name__  # "rpc_dummy"
    rs = vip_agent.vip.rpc.call(peer, peer_method).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)


def test_outstation_reset(vip_agent, dnp3_outstation_agent):

    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.reset_outstation
    peer_method = method.__name__  # "reset_outstation"
    # note: reset_outstation returns None, check if raise or time out instead
    try:
        rs = vip_agent.vip.rpc.call(peer, peer_method).get(timeout=5)
        print(datetime.datetime.now(), "rs: ", rs)
    except BaseException as e:
        assert False


def test_outstation_get_db(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.display_outstation_db
    peer_method = method.__name__  # "display_outstation_db"
    rs = vip_agent.vip.rpc.call(peer, peer_method).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)
    assert rs == {
        'Analog': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None, '8': None,
                   '9': None},
        'AnalogOutputStatus': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None,
                               '8': None, '9': None},
        'Binary': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None, '8': None,
                   '9': None},
        'BinaryOutputStatus': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None,
                               '8': None, '9': None}}


def test_outstation_get_config(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.get_outstation_config
    peer_method = method.__name__  # "get_outstation_config"
    rs = vip_agent.vip.rpc.call(peer, peer_method).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)
    assert rs == {'outstation_ip_str': '0.0.0.0', 'port': 20000, 'masterstation_id_int': 2, 'outstation_id_int': 1}


def test_outstation_is_connected(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.is_outstation_connected
    peer_method = method.__name__  # "is_outstation_connected"
    rs = vip_agent.vip.rpc.call(peer, peer_method).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)
    assert rs in [True, False]


def test_outstation_apply_update_analog_input(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.apply_update_analog_input
    peer_method = method.__name__  # "apply_update_analog_input"
    val, index = random.random(), random.choice(range(5))
    print(f"val: {val}, index: {index}")
    rs = vip_agent.vip.rpc.call(peer, peer_method, val, index).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)

    # verify
    val_new = rs.get("Analog").get(str(index))
    assert val_new == val


def test_outstation_apply_update_analog_output(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.apply_update_analog_output
    peer_method = method.__name__  # "apply_update_analog_output"
    val, index = random.random(), random.choice(range(5))
    print(f"val: {val}, index: {index}")
    rs = vip_agent.vip.rpc.call(peer, peer_method, val, index).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)

    # verify
    val_new = rs.get("AnalogOutputStatus").get(str(index))
    assert val_new == val


def test_outstation_apply_update_binary_input(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.apply_update_binary_input
    peer_method = method.__name__  # "apply_update_binary_input"
    val, index = random.choice([True, False]), random.choice(range(5))
    print(f"val: {val}, index: {index}")
    rs = vip_agent.vip.rpc.call(peer, peer_method, val, index).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)

    # verify
    val_new = rs.get("Binary").get(str(index))
    assert val_new == val


def test_outstation_apply_update_binary_output(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.apply_update_binary_output
    peer_method = method.__name__  # "apply_update_binary_output"
    val, index = random.choice([True, False]), random.choice(range(5))
    print(f"val: {val}, index: {index}")
    rs = vip_agent.vip.rpc.call(peer, peer_method, val, index).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)

    # verify
    val_new = rs.get("BinaryOutputStatus").get(str(index))
    assert val_new == val


def test_outstation_update_config_with_restart(vip_agent, dnp3_outstation_agent):
    peer = dnp3_vip_identity
    method = Dnp3OutstationAgent.update_outstation
    peer_method = method.__name__  # "update_outstation"
    port_to_set = 20001
    rs = vip_agent.vip.rpc.call(peer, peer_method, port=port_to_set).get(timeout=5)
    print(datetime.datetime.now(), "rs: ", rs)

    # verify
    rs = vip_agent.vip.rpc.call(peer, "get_outstation_config").get(timeout=5)
    port_new = rs.get("port")
    # print(f"========= port_new {port_new}")
    assert port_new == port_to_set
