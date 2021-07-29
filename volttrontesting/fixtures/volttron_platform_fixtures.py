import contextlib
import os
from pathlib import Path
import shutil
from typing import Optional
from urllib.parse import urlparse

import psutil
import pytest

from volttron.platform import is_rabbitmq_available, is_web_available
from volttron.platform import update_platform_config
from volttron.utils import get_random_key
from volttrontesting.fixtures.cert_fixtures import certs_profile_1
from volttrontesting.utils.platformwrapper import PlatformWrapper, with_os_environ
from volttrontesting.utils.platformwrapper import create_volttron_home
from volttrontesting.utils.utils import get_hostname_and_random_port, get_rand_vip, get_rand_ip_and_port
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttron.utils.rmq_setup import start_rabbit

PRINT_LOG_ON_SHUTDOWN = False
HAS_RMQ = is_rabbitmq_available()
HAS_WEB = is_web_available()

ci_skipif = pytest.mark.skipif(os.getenv('CI', None) == 'true', reason='SSL does not work in CI')
rmq_skipif = pytest.mark.skipif(not HAS_RMQ,
                                reason='RabbitMQ is not setup and/or SSL does not work in CI')
web_skipif = pytest.mark.skipif(not HAS_WEB, reason='Web libraries are not installed')


def print_log(volttron_home):
    if PRINT_LOG_ON_SHUTDOWN:
        if os.environ.get('PRINT_LOGS', PRINT_LOG_ON_SHUTDOWN):
            log_path = volttron_home + "/volttron.log"
            if os.path.exists(log_path):
                with open(volttron_home + "/volttron.log") as fin:
                    print(fin.read())
            else:
                print('NO LOG FILE AVAILABLE.')


def build_wrapper(vip_address: str, should_start: bool = True, messagebus: str = 'zmq',
                  remote_platform_ca: Optional[str] = None,
                  instance_name: Optional[str] = None, secure_agent_users: bool = False, **kwargs):
    wrapper = PlatformWrapper(ssl_auth=kwargs.pop('ssl_auth', False),
                              messagebus=messagebus,
                              instance_name=instance_name,
                              secure_agent_users=secure_agent_users,
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
    if wrapper.p_process is not None:
        if psutil.pid_exists(wrapper.p_process.pid):
            proc = psutil.Process(wrapper.p_process.pid)
            proc.terminate()
    if not wrapper.debug_mode:
        assert not Path(wrapper.volttron_home).parent.exists(), \
            f"{str(Path(wrapper.volttron_home).parent)} wasn't cleaned!"


def cleanup_wrappers(platforms):
    for p in platforms:
        cleanup_wrapper(p)


@pytest.fixture(scope="module",
                params=[dict(messagebus='zmq', ssl_auth=False),
                        # pytest.param(dict(messagebus='rmq', ssl_auth=True), marks=rmq_skipif),
                        ])
def volttron_instance_msgdebug(request):
    print("building msgdebug instance")
    wrapper = build_wrapper(get_rand_vip(),
                            msgdebug=True,
                            messagebus=request.param['messagebus'],
                            ssl_auth=request.param['ssl_auth'])

    try:
        yield wrapper
    finally:
        cleanup_wrapper(wrapper)


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
    wrapper = build_wrapper(address,
                            messagebus=request.param['messagebus'],
                            ssl_auth=request.param['ssl_auth'],
                            **kwargs)
    wrapper_pid = wrapper.p_process.pid

    try:
        yield wrapper
    except Exception as ex:
        print(ex.args)
    finally:
        cleanup_wrapper(wrapper)
        if not wrapper.debug_mode:
            assert not Path(wrapper.volttron_home).exists()
        # Final way to kill off the platform wrapper for the tests.
        if psutil.pid_exists(wrapper_pid):
            psutil.Process(wrapper_pid).kill()


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
    instances = []

    def get_n_volttron_instances(n, should_start=True, **kwargs):
        nonlocal instances
        get_n_volttron_instances.count = n
        instances = []
        for i in range(0, n):
            address = kwargs.pop("vip_address", get_rand_vip())

            wrapper = build_wrapper(address, should_start=should_start,
                                    messagebus=request.param['messagebus'],
                                    ssl_auth=request.param['ssl_auth'],
                                    **kwargs)
            instances.append(wrapper)
        if should_start:
            for w in instances:
                assert w.is_running()
        # instances = instances if n > 1 else instances[0]
        # setattr(get_n_volttron_instances, 'instances', instances)
        get_n_volttron_instances.instances = instances if n > 1 else instances[0]
        return instances if n > 1 else instances[0]

    def cleanup():
        nonlocal instances
        print(f"My instances: {get_n_volttron_instances.count}")
        if isinstance(get_n_volttron_instances.instances, PlatformWrapper):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances))
            cleanup_wrapper(get_n_volttron_instances.instances)
            return

        for i in range(0, get_n_volttron_instances.count):
            print('Shutting down instance: {}'.format(
                get_n_volttron_instances.instances[i].volttron_home))
            cleanup_wrapper(get_n_volttron_instances.instances[i])

    try:
        yield get_n_volttron_instances
    finally:
        cleanup()



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
                    pytest.param(dict(messagebus='zmq', ssl_auth=True), marks=ci_skipif),
                    pytest.param(dict(messagebus='rmq', ssl_auth=True), marks=rmq_skipif),
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

#TODO: Add functionality for http use case for tests

@pytest.fixture(scope="module",
                params=[
                    pytest.param(dict(sink='zmq_web', source='zmq', zmq_ssl=False), marks=web_skipif),
                    pytest.param(dict(sink='zmq_web', source='zmq', zmq_ssl=True), marks=ci_skipif),
                    pytest.param(dict(sink='rmq_web', source='zmq', zmq_ssl=False), marks=rmq_skipif),
                    pytest.param(dict(sink='rmq_web', source='rmq', zmq_ssl=False), marks=rmq_skipif),
                    pytest.param(dict(sink='zmq_web', source='rmq', zmq_ssl=False), marks=rmq_skipif),
                    pytest.param(dict(sink='zmq_web', source='rmq', zmq_ssl=True), marks=rmq_skipif),

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

    def get_volttron_multi_msgbus_instances(instance_name1=None, instance_name2=None):
        print("volttron_multi_messagebus source: {} sink: {}".format(request.param['source'],
                                                                     request.param['sink']))
        sink_address = get_rand_vip()

        if request.param['sink'] == 'rmq_web':
            hostname, port = get_hostname_and_random_port()
            web_address = 'https://{hostname}:{port}'.format(hostname=hostname, port=port)
            messagebus = 'rmq'
            ssl_auth = True
        elif request.param['sink'] == 'zmq_web' and request.param['zmq_ssl'] is True:
            hostname, port = get_hostname_and_random_port()
            web_address = 'https://{hostname}:{port}'.format(hostname=hostname, port=port)
            messagebus = 'zmq'
            ssl_auth = True
        else:
            hostname, port = get_hostname_and_random_port()
            web_address = "http://{}".format(get_rand_ip_and_port())
            messagebus = 'zmq'
            ssl_auth = False

        sink = build_wrapper(sink_address,
                             ssl_auth=ssl_auth,
                             messagebus=messagebus,
                             bind_web_address=web_address,
                             volttron_central_address=web_address,
                             instance_name="volttron1")
        # sink.web_admin_api.create_web_admin("admin", "admin")

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
                                   remote_platform_ca=sink.certsobj.cert_file(sink.certsobj.root_ca_name),
                                   instance_name='volttron2')
        elif sink.messagebus == 'zmq' and sink.ssl_auth is True:
            source = build_wrapper(source_address,
                                   ssl_auth=ssl_auth,
                                   messagebus=messagebus,
                                   volttron_central_address=sink.bind_web_address,
                                   remote_platform_ca=sink.certsobj.cert_file(sink.certsobj.root_ca_name),
                                   instance_name='volttron2')
        else:
            source = build_wrapper(source_address,
                                   ssl_auth=ssl_auth,
                                   messagebus=messagebus,
                                   volttron_central_address=sink.bind_web_address,
                                   instance_name='volttron2')
        get_volttron_multi_msgbus_instances.source = source
        get_volttron_multi_msgbus_instances.sink = sink
        return source, sink

    def cleanup():
        # Handle the case where source or sink fail to be created
        try:
            cleanup_wrapper(get_volttron_multi_msgbus_instances.source)
        except AttributeError as e:
            print(e)
        try:
            cleanup_wrapper(get_volttron_multi_msgbus_instances.sink)
        except AttributeError as e:
            print(e)
    request.addfinalizer(cleanup)

    return get_volttron_multi_msgbus_instances


@contextlib.contextmanager
def get_test_volttron_home(messagebus: str, web_https=False, web_http=False, has_vip=True, volttron_home: str = None,
                           config_params: dict = None,
                           env_options: dict = None):
    """
    Create a full volttronn_home test environment with all of the options available in the environment
    (os.environ) and configuration file (volttron_home/config) in order to test from.

    @param messagebus:
        Currently supports rmq and zmq strings
    @param web_https:
        Determines if https should be used and enabled.  If this is specified then the cert_fixtures.certs_profile_1
        function will be used to generate certificates for  the server and signed ca.  Either web_https or web_http
        may be specified not both.
    @param has_vip:
        Allows the rmq message bus to not specify a vip address if backward compatibility is not needed.
    @param config_params:
        Configuration parameters that should go into the volttron configuration file, note if the basic ones are
        set via the previous arguments (i.e. web_https) then it is an error to specify bind-web-address (or other)
        duplicate.
    @param env_options:
        Other options that should be specified in the os.environ during the setup of this environment.
    """
    # Make these not None so that we can use set operations on them to see if we have any overlap between
    # common configuration params and environment.
    if config_params is None:
        config_params = {}
    if env_options is None:
        env_options = {}

    # make a copy so we can restore in cleanup
    env_cpy = os.environ.copy()

    # start validating input
    assert messagebus in ('rmq', 'zmq'), 'Invalid messagebus specified, must be rmq or zmq.'

    if web_http and web_https:
        raise ValueError("Incompatabile tyeps web_https and web_Http cannot both be specified as True")

    default_env_options = ('VOLTTRON_HOME', 'MESSAGEBUS')

    for v in default_env_options:
        if v in env_options:
            raise ValueError(f"Cannot specify {v} in env_options as it is set already.")

    # All is well.Create vhome
    if volttron_home:
        os.makedirs(volttron_home, exist_ok=True)
    else:
        volttron_home = create_volttron_home()

    # Create env
    envs = dict(VOLTTRON_HOME=volttron_home, MESSAGEBUS=messagebus)
    os.environ.update(envs)
    os.environ.update(env_options)

    # make the top level dirs
    os.mkdir(os.path.join(volttron_home, "agents"))
    os.mkdir(os.path.join(volttron_home, "configuration_store"))
    os.mkdir(os.path.join(volttron_home, "keystores"))
    os.mkdir(os.path.join(volttron_home, "run"))

    # create the certs. This will create the certs dirs
    web_certs_dir = os.path.join(volttron_home, "web_certs")
    web_certs = None
    if web_https:
        web_certs = certs_profile_1(web_certs_dir)

    vip_address = None
    bind_web_address = None
    web_ssl_cert = None
    web_ssl_key = None
    web_secret_key = None

    config_file = {}
    if messagebus == 'rmq':
        if has_vip:
            ip, port = get_rand_ip_and_port()
            vip_address = f"tcp://{ip}:{port}"
        web_https = True
    elif messagebus == 'zmq':
        if web_http or web_https:
            ip, port = get_rand_ip_and_port()
            vip_address = f"tcp://{ip}:{port}"

    if web_https:
        hostname, port = get_hostname_and_random_port()
        bind_web_address = f"https://{hostname}:{port}"
        web_ssl_cert = web_certs.server_certs[0].cert_file
        web_ssl_key = web_certs.server_certs[0].key_file
    elif web_http:
        hostname, port = get_hostname_and_random_port()
        bind_web_address = f"http://{hostname}:{port}"
        web_secret_key = get_random_key()

    if vip_address:
        config_file['vip-address'] = vip_address
    if bind_web_address:
        config_file['bind-web-address'] = bind_web_address
    if web_ssl_cert:
        config_file['web-ssl-cert'] = web_ssl_cert
    if web_ssl_key:
        config_file['web-ssl-key'] = web_ssl_key
    if web_secret_key:
        config_file['web-secret-key'] = web_secret_key

    config_intersect = set(config_file).intersection(set(config_params))
    if len(config_intersect) > 0:
        raise ValueError(f"passed configuration params {list(config_intersect)} are built internally")

    config_file.update(config_params)

    update_platform_config(config_file)

    try:
        yield volttron_home
    finally:
        os.environ.clear()
        os.environ.update(env_cpy)
        if not os.environ.get("DEBUG", 0) != 1 and not os.environ.get("DEBUG_MODE", 0):
            shutil.rmtree(volttron_home, ignore_errors=True)


@pytest.fixture(scope="module")
def federated_rmq_instances(request, **kwargs):
    """
    Create two rmq based volttron instances. One to act as producer of data and one to act as consumer of data
    producer is upstream instance and consumer is the downstream instance

    :return: 2 volttron instances - (producer, consumer) that are federated
    """
    upstream_vip = get_rand_vip()
    upstream_hostname, upstream_https_port = get_hostname_and_random_port()
    web_address = 'https://{hostname}:{port}'.format(hostname=upstream_hostname, port=upstream_https_port)
    upstream = build_wrapper(upstream_vip,
                             ssl_auth=True,
                             messagebus='rmq',
                             should_start=True,
                             bind_web_address=web_address,
                             instance_name='volttron1',
                             **kwargs)
    upstream.enable_auto_csr()
    downstream_vip = get_rand_vip()
    hostname, https_port = get_hostname_and_random_port()
    downstream_web_address = 'https://{hostname}:{port}'.format(hostname=hostname, port=https_port)

    downstream = build_wrapper(downstream_vip,
                               ssl_auth=True,
                               messagebus='rmq',
                               should_start=False,
                               bind_web_address=downstream_web_address,
                               instance_name='volttron2',
                               **kwargs)

    link_name = None
    rmq_mgmt = None
    try:
        # create federation config and save in volttron home of 'downstream' instance
        content = dict()
        fed = dict()
        fed[upstream.rabbitmq_config_obj.rabbitmq_config["host"]] = {
            'port': upstream.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
            'virtual-host': upstream.rabbitmq_config_obj.rabbitmq_config["virtual-host"],
            'https-port': upstream_https_port,
            'federation-user': "{}.federation".format(downstream.instance_name)}
        content['federation-upstream'] = fed
        import yaml
        config_path = os.path.join(downstream.volttron_home, "rabbitmq_federation_config.yml")
        with open(config_path, 'w') as yaml_file:
            yaml.dump(content, yaml_file, default_flow_style=False)

        # setup federation link from 'downstream' to 'upstream' instance
        downstream.setup_federation(config_path)

        downstream.startup_platform(vip_address=downstream_vip,
                                    bind_web_address=downstream_web_address)
        with with_os_environ(downstream.env):
            rmq_mgmt = RabbitMQMgmt()
            links = rmq_mgmt.get_federation_links()
            assert links and links[0]['status'] == 'running'
            link_name = links[0]['name']

    except Exception as e:
        print("Exception setting up federation: {}".format(e))
        upstream.shutdown_platform()
        if downstream.is_running():
            downstream.shutdown_platform()
        raise e

    yield upstream, downstream

    if link_name and rmq_mgmt:
        rmq_mgmt.delete_multiplatform_parameter('federation-upstream', link_name)
    upstream.shutdown_platform()
    downstream.shutdown_platform()


@pytest.fixture(scope="module")
def two_way_federated_rmq_instances(request, **kwargs):
    """
    Create two rmq based volttron instances. Create bi-directional data flow channel
    by creating 2 federation links

    :return: 2 volttron instances - that are connected through federation
    """
    instance_1_vip = get_rand_vip()
    instance_1_hostname, instance_1_https_port = get_hostname_and_random_port()
    instance_1_web_address = 'https://{hostname}:{port}'.format(hostname=instance_1_hostname,
                                                     port=instance_1_https_port)

    instance_1 = build_wrapper(instance_1_vip,
                               ssl_auth=True,
                               messagebus='rmq',
                               should_start=True,
                               bind_web_address=instance_1_web_address,
                               instance_name='volttron1',
                               **kwargs)

    instance_1.enable_auto_csr()

    instance_2_vip = get_rand_vip()
    instance_2_hostname, instance_2_https_port = get_hostname_and_random_port()
    instance_2_webaddress = 'https://{hostname}:{port}'.format(hostname=instance_2_hostname,
                                                               port=instance_2_https_port)

    instance_2 = build_wrapper(instance_2_vip,
                               ssl_auth=True,
                               messagebus='rmq',
                               should_start=False,
                               bind_web_address=instance_2_webaddress,
                               instance_name='volttron2',
                               **kwargs)

    instance_2_link_name = None
    instance_1_link_name = None

    try:
        # create federation config and setup federation link to instance_1
        content = dict()
        fed = dict()
        fed[instance_1.rabbitmq_config_obj.rabbitmq_config["host"]] = {
            'port': instance_1.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
            'virtual-host': instance_1.rabbitmq_config_obj.rabbitmq_config["virtual-host"],
            'https-port': instance_1_https_port,
            'federation-user': "{}.federation".format(instance_2.instance_name)}
        content['federation-upstream'] = fed
        import yaml
        config_path = os.path.join(instance_2.volttron_home, "rabbitmq_federation_config.yml")
        with open(config_path, 'w') as yaml_file:
            yaml.dump(content, yaml_file, default_flow_style=False)

        print(f"instance 2 Fed config path:{config_path}, content: {content}")

        instance_2.setup_federation(config_path)
        instance_2.startup_platform(vip_address=instance_2_vip, bind_web_address=instance_2_webaddress)
        instance_2.enable_auto_csr()
        # Check federation link status
        with with_os_environ(instance_2.env):
            rmq_mgmt = RabbitMQMgmt()
            links = rmq_mgmt.get_federation_links()
            print(f"instance 2 fed links state: {links[0]['status']}")
            assert links and links[0]['status'] == 'running'
            instance_2_link_name = links[0]['name']

        instance_1.skip_cleanup = True
        instance_1.shutdown_platform()
        instance_1.skip_cleanup = False

        start_rabbit(rmq_home=instance_1.rabbitmq_config_obj.rmq_home, env=instance_1.env)

        # create federation config and setup federation to instance_2
        content = dict()
        fed = dict()
        fed[instance_2.rabbitmq_config_obj.rabbitmq_config["host"]] = {
            'port': instance_2.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
            'virtual-host': instance_2.rabbitmq_config_obj.rabbitmq_config["virtual-host"],
            'https-port': instance_2_https_port,
            'federation-user': "{}.federation".format(instance_1.instance_name)}
        content['federation-upstream'] = fed
        import yaml
        config_path = os.path.join(instance_1.volttron_home, "rabbitmq_federation_config.yml")
        with open(config_path, 'w') as yaml_file:
            yaml.dump(content, yaml_file, default_flow_style=False)

        print(f"instance 1 Fed config path:{config_path}, content: {content}")

        instance_1.setup_federation(config_path)
        instance_1.startup_platform(vip_address=instance_1_vip, bind_web_address=instance_1_web_address)
        import gevent
        gevent.sleep(10)
        # Check federation link status
        with with_os_environ(instance_1.env):
            rmq_mgmt = RabbitMQMgmt()
            links = rmq_mgmt.get_federation_links()
            print(f"instance 1 fed links state: {links[0]['status']}")
            assert links and links[0]['status'] == 'running'
            instance_1_link_name = links[0]['name']

    except Exception as e:
        print(f"Exception setting up federation: {e}")
        instance_1.shutdown_platform()
        instance_2.shutdown_platform()
        raise e

    yield instance_1, instance_2

    if instance_1_link_name:
        with with_os_environ(instance_1.env):
            rmq_mgmt = RabbitMQMgmt()
            rmq_mgmt.delete_multiplatform_parameter('federation-upstream',
                                                    instance_1_link_name)
    if instance_2_link_name:
        with with_os_environ(instance_2.env):
            rmq_mgmt = RabbitMQMgmt()
            rmq_mgmt.delete_multiplatform_parameter('federation-upstream',
                                                    instance_2_link_name)
    instance_1.shutdown_platform()
    instance_2.shutdown_platform()


