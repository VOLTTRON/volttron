import os
import pytest
from random import randint
import socket
import uuid

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


def get_rand_ipc_vip():
    return "ipc://@/" + str(uuid.uuid4())


def build_wrapper(vip_address, **kwargs):
    wrapper = PlatformWrapper()
    print('BUILD_WRAPPER: {}'.format(vip_address))
    wrapper.startup_platform(vip_address=vip_address, **kwargs)
    return wrapper


def cleanup_wrapper(wrapper):
    print('Shutting down instance: {}'.format(wrapper.volttron_home))
    # Shutdown handles case where the platform hasn't started.
    wrapper.shutdown_platform()


def cleanup_wrappers(platforms):
    for p in platforms:
        cleanup_wrapper(p)


@pytest.fixture(scope="module")
def volttron_instance1(request):
    wrapper = build_wrapper(get_rand_vip())

    def cleanup():
        cleanup_wrapper(wrapper)

    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance2(request):
    print("building instance 2")
    wrapper = build_wrapper(get_rand_vip())

    def cleanup():
        cleanup_wrapper(wrapper)

    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="function",
        params=['tcp', 'ipc'])
def volttron_instance_encrypt(request):
    print("building instance (using encryption)")
    if request.param == 'tcp':
        address = get_rand_vip()
    else:
        address = get_rand_ipc_vip()
    wrapper = build_wrapper(address, encrypt=True)

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
                params=['encrypted', 'unencrypted'])
def volttron_instance(request):
    """Fixture that returns a single instance of volttron platform for testing
    Tests using this fixture will be run twice, once with an unencrypted
    volttron instance and once with an encrypted volttron instance
    @param request: pytest request object
    @return: volttron platform instance
    """
    wrapper = None
    address = get_rand_vip()
    if request.param == 'encrypted':
        print("building instance (using encryption)")
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
                params=['encrypted', 'unencrypted'])
def get_volttron_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. Since this fixture is
    parameterized you test method will be run twice once with unencrypted
    volttron instances and once with encrypted instances. The fixture also
    takes care of shutting down all the instances at the end

    Example Usage:

    def test_function_that_uses_n_instances(get_volttron_instances):
        instance1, instance2, instance3 = get_volttron_instances(3)

        if get_volttron_instances.param != 'encrypted':
            pytest.skipif('Only available during encrypted round')

    @param request: pytest request object
    @return: tuple:
        The current param value (useful for skipping if context is either
        encrypted or not) and a function that can used to get any number of
        volttron instances for testing.
    """
    all_instances = []

    def get_n_volttron_instances(n, should_start=True):
        print('GETTING NEW INSTANCES!!!!!', request.param, n)
        get_n_volttron_instances.count = n
        instances = []
        for i in range(0, n):
            address = get_rand_vip()
            wrapper = None
            if should_start:
                if request.param == 'encrypted':
                    print("building instance  (using encryption)")
                    wrapper = build_wrapper(address, encrypt=True)
                else:
                    wrapper = build_wrapper(address)
            else:
                wrapper = PlatformWrapper()
            instances.append(wrapper)
        get_n_volttron_instances.param = request.param
        instances = instances if n > 1 else instances[0]
        get_n_volttron_instances.instances = instances
        return instances

    def cleanup():
        if isinstance(get_n_volttron_instances.instances, PlatformWrapper):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances.volttron_home))
            get_n_volttron_instances.instances.shutdown_platform()
            return

        for i in range(0, get_n_volttron_instances.count):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances[i].volttron_home))
            get_n_volttron_instances.instances[i].shutdown_platform()

    request.addfinalizer(cleanup)

    return get_n_volttron_instances
