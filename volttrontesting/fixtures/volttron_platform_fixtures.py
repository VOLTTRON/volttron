import os
import json
import pytest
from volttrontesting.utils.platformwrapper import PlatformWrapper

def get_rand_port():
    from random import randint
    port = randint(5000, 6000)
    while is_port_open(port):
        port = randint(5000, 6000)
    return port

def is_port_open(port):
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1',port))
    return result == 0

@pytest.fixture(scope="module")
def instance1_config():
    port = get_rand_port()
    return {"vip-address": "tcp://127.0.0.1:{}".format(port)}

@pytest.fixture(scope="module")
def instance2_config():
    port = get_rand_port()
    return {"vip-address": "tcp://127.0.0.1:{}".format(port)}

def build_wrapper(vip_address, **kwargs):
    wrapper = PlatformWrapper()
    print('BUILD_WRAPPER: {}'.format(vip_address))
    wrapper.startup_platform(vip_address=vip_address, **kwargs)
    return wrapper

@pytest.fixture(scope="module")
def volttron_instance1(request, instance1_config):
    wrapper = build_wrapper(instance1_config['vip-address'])

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance2(request, instance2_config):
    print("building instance 2")
    wrapper = build_wrapper(instance2_config['vip-address'])

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper
