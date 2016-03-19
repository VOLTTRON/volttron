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


def cleanup_wrapper(wrapper):
    print('Shutting down instance: {}'.format(wrapper.volttron_home))
    if wrapper.is_running():
        print_log(wrapper.volttron_home)
        wrapper.shutdown_platform(True)
    else:
        print('Platform was never started')


@pytest.fixture(scope="module")
def volttron_instance1(request, instance1_config):
    wrapper = build_wrapper(instance1_config['vip-address'])

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance2(request, instance2_config):
    print("building instance 2")
    wrapper = build_wrapper(instance2_config['vip-address'])

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="function")
def volttron_instance1_encrypt(request):
    print("building instance 1 (using encryption)")
    address = "tcp://127.0.0.1:{}".format(get_rand_port()) 
    wrapper = build_wrapper(address, encrypt=True)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="function")
def volttron_instance2_encrypt(request):
    print("building instance 2 (using encryption)")
    address = "tcp://127.0.0.1:{}".format(get_rand_port())
    wrapper = build_wrapper(address, encrypt=True)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture
def volttron_instance1_web(request):
    print("building instance 1 (using web)")
    address = "tcp://{}".format(get_rand_ip_and_port())
    web_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = build_wrapper(address, encrypt=True,
                            bind_web_address=web_address)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture
def volttron_instance2_web(request):
    print("building instance 2 (using web)")
    address = "tcp://{}".format(get_rand_ip_and_port())
    web_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = build_wrapper(address, encrypt=True,
                            bind_web_address=web_address)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper
