import os
import json
import pytest
from random import randint
import socket
from volttrontesting.utils.platformwrapper import PlatformWrapper

PRINT_LOG_ON_SHUTDOWN = True


def print_log(volttron_home):
    if PRINT_LOG_ON_SHUTDOWN:
        log_path = volttron_home+"/volttron.log"
        if os.path.exists(log_path):
            with open(volttron_home+"/volttron.log") as fin:
                print(fin.read())
        else:
            print('NO LOG FILE AVAILABLE.')


def get_rand_ip_and_port():
    ip = "127.0.0.{}".format(randint(1, 254))
    port = get_rand_port(ip)
    return ip+":{}".format(port)


def get_rand_port(ip=None):
    port = randint(5000, 6000)
    while is_port_open(port):
        port = randint(5000, 6000)
    return port


def is_port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1',port))
    return result == 0


def get_rand_vip():
    return "tcp://{}".format(get_rand_ip_and_port())


@pytest.fixture(scope="module")
def instance1_config():
    return {"vip-address": get_rand_vip()}


@pytest.fixture(scope="module")
def instance2_config():
    return {"vip-address": get_rand_vip()}


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
    wrapper = build_wrapper(get_rand_vip(), encrypt=True)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="function")
def volttron_instance2_encrypt(request):
    print("building instance 2 (using encryption)")
    wrapper = build_wrapper(get_rand_vip(), encrypt=True)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture
def volttron_instance1_web(request):
    print("building instance 1 (using web)")
    address = get_rand_vip()
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
    address = get_rand_vip()
    web_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = build_wrapper(address, encrypt=True,
                            bind_web_address=web_address)

    def cleanup():
        cleanup_wrapper(wrapper)
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="function")
def volttron_instance2_encrypt(request):
    print("building instance 2 (using encryption)")
    wrapper = build_wrapper(get_rand_vip(), encrypt=True)

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        print_log(wrapper.volttron_home)
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper

@pytest.fixture
def volttron_instance1_web(request):
    print("building instance 1 (using web)")
    address = get_rand_vip()
    web_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = build_wrapper(address, encrypt=True,
                            bind_web_address=web_address)

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        print_log(wrapper.volttron_home)
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper

@pytest.fixture
def volttron_instance2_web(request):
    print("building instance 2 (using web)")
    address = get_rand_vip()
    web_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = build_wrapper(address, encrypt=True,
                            bind_web_address=web_address)

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        print_log(wrapper.volttron_home)
<<<<<<< HEAD
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper

# def get_platforms(encrptyed=5, non=2):
#
# params(nonencpty=5, encrpty=2)
#
# @pytest.fixture(params=[(instance1, instance2)])
# def multi_platform
#
@pytest.fixture(scope="module",
                params=['unencrypted','encrypted'])
def volttron_instance(request, instance1_config):
    wrapper = None
    if request.param == 'encrypted':
        print("building instance 1 (using encryption)")
        address = "tcp://127.0.0.1:{}".format(get_rand_port())
        wrapper = build_wrapper(address, encrypt=True)
    else:
        wrapper = build_wrapper(instance1_config['vip-address'])

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
=======
>>>>>>> develop
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper






