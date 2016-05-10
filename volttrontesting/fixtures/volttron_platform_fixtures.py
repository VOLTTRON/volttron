import os
import pytest
from random import randint
import socket
from volttrontesting.utils.platformwrapper import PlatformWrapper

PRINT_LOG_ON_SHUTDOWN = False

def print_log(volttron_home):
    if PRINT_LOG_ON_SHUTDOWN:
        if os.environ.get('PRINT_LOGS', PRINT_LOG_ON_SHUTDOWN):
            log_path = volttron_home + "/volttron.log"
            if os.path.exists(log_path):
                with open(volttron_home + "/volttron.log") as fin:
                    print(fin.read())
            else:
                print('NO LOG FILE AVAILABLE.')


def get_rand_ip_and_port():
    ip = "127.0.0.{}".format(randint(1, 254))
    port = get_rand_port(ip)
    return ip + ":{}".format(port)


def get_rand_port(ip=None):
    port = randint(5000, 6000)
    if ip:
        while is_port_open(ip, port):
            port = randint(5000, 6000)
    return port


def is_port_open(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((ip, port))
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
        wrapper.shutdown_platform()
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


# Generic fixtures. Ideally we want to use the below instead of
# Use this fixture when you want a single instance of volttron platform for
# test
@pytest.fixture(scope="module",
                params=['encrypted'])
def volttron_instance(request):
    """Fixture that returns a single instance of volttron platform for testing
    Tests using this fixture will be run twice, once with an unencrypted
    volttron instance and once with an encrypted volttron instance
    @param request: pytest request object
    @return: volttron platform instance
    """
    wrapper = None
    address = get_rand_ip_and_port()
    if request.param == 'encrypted':
        print("building instance 1 (using encryption)")
        wrapper = build_wrapper(address, encrypt=True)
    else:
        wrapper = build_wrapper(address)

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        wrapper.shutdown_platform()

    request.addfinalizer(cleanup)
    return wrapper


# Use this fixture to get more than 1 volttron instance for test.
# Usage example:
# def test_function_that_uses_n_instances(request, get_volttron_instances):
#     instances = get_volttron_instances(3)
@pytest.fixture(scope="module",
                params=['unencrypted', 'encrypted'])
def get_volttron_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. Since this fixture is
    parameterized you test method will be run twice once with unencrypted
    volttron instances and once with encrypted instances. The fixture also
    takes care of shutting down all the instances at the end
    Example Usage:
    def test_function_that_uses_n_instances(request, get_volttron_instances):
        instances = get_volttron_instances(3)
    @param request: pytest request object
    @return: a function that can used to get any number of volttron instnaces
    for testing.
    """

    def get_n_volttron_instances(n):
        get_n_volttron_instances.count = n
        instances = []
        for i in range(0, n):
            address = "tcp://127.0.0.1:{}".format(get_rand_port())
            wrapper = None
            if request.param == 'encrypted':
                print("building instance  (using encryption)")
                wrapper = build_wrapper(address, encrypt=True)
            else:
                wrapper = build_wrapper(address)
            instances.append(wrapper)
        get_n_volttron_instances.instances = instances
        return instances

    def cleanup():
        for i in range(0, get_n_volttron_instances.count):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances[i].volttron_home))
            get_n_volttron_instances.instances[i].shutdown_platform()

    request.addfinalizer(cleanup)

    return get_n_volttron_instances
