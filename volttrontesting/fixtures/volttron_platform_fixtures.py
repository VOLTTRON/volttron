import os
import pytest

from volttrontesting.utils.platform_process import VolttronRuntimeOptions, VolttronProcess
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.utils.utils import get_hostname_and_random_port, get_rand_vip, get_rand_ip_and_port
from volttron.platform import is_rabbitmq_available

PRINT_LOG_ON_SHUTDOWN = False
HAS_RMQ = is_rabbitmq_available()
rmq_skipif = pytest.mark.skipif(not HAS_RMQ, reason='RabbitMQ is not setup')


def print_log(volttron_home):
    if PRINT_LOG_ON_SHUTDOWN:
        if os.environ.get('PRINT_LOGS', PRINT_LOG_ON_SHUTDOWN):
            log_path = volttron_home + "/volttron.log"
            if os.path.exists(log_path):
                with open(volttron_home + "/volttron.log") as fin:
                    print(fin.read())
            else:
                print('NO LOG FILE AVAILABLE.')


def build_wrapper(vip_address, should_start=True, messagebus='zmq', remote_platform_ca=None,
                  instance_name=None, **kwargs):

    wrapper = PlatformWrapper(ssl_auth=kwargs.pop('ssl_auth', False),
                              messagebus=messagebus,
                              instance_name=instance_name,
                              remote_platform_ca=remote_platform_ca)
    if should_start:
        wrapper.startup_platform(vip_address=vip_address, **kwargs)
    return wrapper


def cleanup_wrapper(wrapper):
    print('Shutting down instance: {0}, MESSAGE BUS: {1}'.format(wrapper.volttron_home, wrapper.messagebus))
    # if wrapper.is_running():
    #     wrapper.remove_all_agents()
    # Shutdown handles case where the platform hasn't started.
    wrapper.shutdown_platform()


def cleanup_wrappers(platforms):
    for p in platforms:
        cleanup_wrapper(p)


@pytest.fixture(scope="module",
                params=[dict(messagebus='zmq', ssl_auth=False),
                        #pytest.param(dict(messagebus='rmq', ssl_auth=True), marks=rmq_skipif),
                        ])
def volttron_instance_msgdebug(request):
    print("building msgdebug instance")
    wrapper = build_wrapper(get_rand_vip(),
                            msgdebug=True,
                            messagebus=request.param['messagebus'],
                            ssl_auth=request.param['ssl_auth'])

    yield wrapper

    cleanup_wrapper(wrapper)


# IPC testing is removed since it is not used from VOLTTRON 6.0
@pytest.fixture(scope="function")
def volttron_instance_encrypt(request):
    print("building instance (using encryption)")

    address = get_rand_vip()
    wrapper = build_wrapper(address)

    def cleanup():
        cleanup_wrapper(wrapper)

    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance_module_web(request):
    print("building module instance (using web)")
    address = get_rand_vip()
    web_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = build_wrapper(address,
                            bind_web_address=web_address,
                            messagebus='zmq',
                            ssl_auth=False)

    yield wrapper

    cleanup_wrapper(wrapper)


# Generic fixtures. Ideally we want to use the below instead of
# Use this fixture when you want a single instance of volttron platform for
# test
@pytest.fixture(scope="module",
                params=[
                    dict(messagebus='zmq', ssl_auth=False),
                    pytest.param(dict(messagebus='rmq', ssl_auth=True), marks=rmq_skipif),
                ])
def volttron_instance(request, **kwargs):
    """Fixture that returns a single instance of volttron platform for testing

    @param request: pytest request object
    @return: volttron platform instance
    """
    address = kwargs.pop("vip_address", get_rand_vip())
    wrapper = build_wrapper(address, messagebus='zmq', ssl_auth=False, **kwargs)
    # wrapper = build_wrapper(address,
    #                         messagebus=request.param['messagebus'],
    #                         ssl_auth=request.param['ssl_auth'],
    #                         **kwargs)

    yield wrapper

    cleanup_wrapper(wrapper)


# Use this fixture to get more than 1 volttron instance for test.
# Usage example:
# def test_function_that_uses_n_instances(request, get_volttron_instances):
#     instances = get_volttron_instances(3)
#
# TODO allow rmq to be added to the multi platform request.
@pytest.fixture(scope="module",
                params=[
                    dict(messagebus='zmq', ssl_auth=False)
                ])
def get_volttron_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. The fixture also
    takes care of shutting down all the instances at the end

    Example Usage:

    def test_function_that_uses_n_instances(get_volttron_instances):
        instance1, instance2, instance3 = get_volttron_instances(3)

    @param request: pytest request object
    @return: function that can used to get any number of
        volttron instances for testing.
    """
    all_instances = []

    def get_n_volttron_instances(n, should_start=True, **kwargs):
        get_n_volttron_instances.count = n
        instances = []
        for i in range(0, n):
            address = kwargs.pop("vip_address", get_rand_vip())

            wrapper = build_wrapper(address, should_start=should_start,
                                    messagebus=request.param['messagebus'],
                                    ssl_auth=request.param['ssl_auth'],
                                    **kwargs)
            instances.append(wrapper)
        instances = instances if n > 1 else instances[0]
        # setattr(get_n_volttron_instances, 'instances', instances)
        get_n_volttron_instances.instances = instances
        return instances

    def cleanup():
        if isinstance(get_n_volttron_instances.instances, PlatformWrapper):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances))
            cleanup_wrapper(get_n_volttron_instances.instances)
            return

        for i in range(0, get_n_volttron_instances.count):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances[i].volttron_home))
            cleanup_wrapper(get_n_volttron_instances.instances[i])

    request.addfinalizer(cleanup)

    return get_n_volttron_instances


# Use this fixture when you want a single instance of volttron platform for zmq message bus
# test
@pytest.fixture(scope="module")
def volttron_instance_zmq(request):
    """Fixture that returns a single instance of volttron platform for testing

    @param request: pytest request object
    @return: volttron platform instance
    """
    address = get_rand_vip()

    wrapper = build_wrapper(address)

    yield wrapper

    cleanup_wrapper(wrapper)


# Use this fixture when you want a single instance of volttron platform for rmq message bus
# test
@pytest.fixture(scope="module")
def volttron_instance_rmq(request):
    """Fixture that returns a single instance of volttron platform for testing

    @param request: pytest request object
    @return: volttron platform instance
    """
    wrapper = None
    address = get_rand_vip()

    wrapper = build_wrapper(address,
                            messagebus='rmq',
                            ssl_auth=True)

    yield wrapper

    cleanup_wrapper(wrapper)


@pytest.fixture(scope="module",
                params=[
                    dict(messagebus='zmq', ssl_auth=False),
                    # pytest.param(dict(messagebus='rmq', ssl_auth=True), marks=rmq_skipif),
                ])
def volttron_instance_web(request):
    print("volttron_instance_web (messagebus {messagebus} ssl_auth {ssl_auth})".format(**request.param))
    address = get_rand_vip()

    if request.param['ssl_auth']:
        hostname, port = get_hostname_and_random_port()
        web_address = 'https://{hostname}:{port}'.format(hostname=hostname, port=port)
    else:
        web_address = "http://{}".format(get_rand_ip_and_port())

    wrapper = build_wrapper(address,
                            ssl_auth=request.param['ssl_auth'],
                            messagebus=request.param['messagebus'],
                            bind_web_address=web_address,
                            volttron_central_address=web_address)

    yield wrapper

    cleanup_wrapper(wrapper)


@pytest.fixture(scope="module",
                params=[
                    dict(sink='zmq_web', source='zmq'),
                    pytest.param(dict(sink='rmq_web', source='zmq'), marks=rmq_skipif),
                    pytest.param(dict(sink='rmq_web', source='rmq'), marks=rmq_skipif),
                    pytest.param(dict(sink='zmq_web', source='rmq'), marks=rmq_skipif),
                ])
def volttron_multi_messagebus(request):
    """ This fixture allows multiple two message bus types to be configured to work together

    This case will create a source (where data comes from) and a sink (where data goes to) to
    allow connections from source to sink to be tested for the different cases.  In particular,
    the case of VolttronCentralPlatform, Forwarder and DataMover agents should use this
    case.

    :param request:
    :return:
    """
    print("volttron_multi_messagebus source: {} sink: {}".format(request.param['source'],
                                                                 request.param['sink']))
    sink_address = get_rand_vip()

    if request.param['sink'] == 'rmq_web':
        hostname, port = get_hostname_and_random_port()
        web_address = 'https://{hostname}:{port}'.format(hostname=hostname, port=port)
        messagebus = 'rmq'
        ssl_auth = True
    else:
        web_address = "http://{}".format(get_rand_ip_and_port())
        messagebus = 'zmq'
        ssl_auth = False

    sink = build_wrapper(sink_address,
                         ssl_auth=ssl_auth,
                         messagebus=messagebus,
                         bind_web_address=web_address,
                         volttron_central_address=web_address)

    source_address = get_rand_vip()
    messagebus = 'zmq'
    ssl_auth = False

    if request.param['source'] == 'rmq':
        messagebus = 'rmq'
        ssl_auth = True

    if sink.messagebus == 'rmq':
        # sink_ca_file = sink.certsobj.cert_file(sink.certsobj.root_ca_name)

        source = build_wrapper(source_address,
                               ssl_auth=ssl_auth,
                               messagebus=messagebus,
                               volttron_central_address=sink.bind_web_address,
                               remote_platform_ca=sink.certsobj.cert_file(sink.certsobj.root_ca_name))
        if source.messagebus == 'rmq':
            # The _ca is how the auth subsystem saves the remote cert from discovery.  We
            # are effectively doing that here instead of making the discovery call.
            source.certsobj.save_remote_cert(sink.certsobj.root_ca_name + "_ca", sink.certsobj.ca_cert(
                public_bytes=True))
    else:
        source = build_wrapper(source_address,
                               ssl_auth=ssl_auth,
                               messagebus=messagebus,
                               volttron_central_address=sink.bind_web_address)

    yield source, sink

    cleanup_wrapper(source)
    cleanup_wrapper(sink)
