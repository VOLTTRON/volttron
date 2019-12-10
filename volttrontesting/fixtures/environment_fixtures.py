import contextlib
import os
import shutil
from types import SimpleNamespace

from volttron.platform import update_platform_config
from volttron.utils import get_random_key
from volttrontesting.fixtures.cert_fixtures import certs_profile_1
from volttrontesting.utils.platformwrapper import create_volttron_home
from volttrontesting.utils.utils import get_hostname_and_random_port, get_rand_ip_and_port


@contextlib.contextmanager
def build_test_environment(messagebus: str, web_https=False, web_http=False, has_vip=True,
                           bus_uses_tls: bool=True, config_params: dict = None,
                           env_options: dict = None):
    """
    Create a full volttronn_Home test environment with all of the options availalbe in the environment
    (os.environ) and configuration file (volttron_home/config) in order to test from.

    @param messagebus:
        Currently supports rmq and zmq strings
    @param web_https:
        Determines if https should be used and enabled.  If this is specified then the cert_fixtures.certs_profile_1
        function will be used to generate certificates for  the server and signed ca.  Either web_https or web_http
        may be specified not both.
    @param has_vip:
        Allows the rmq message bus to not specify a vip address if backward compatibility is not needed.
    @param bus_uses_tls:
        Determines if the bus should use tls or not for connections.  For rabbit this means that the certs
        will be populated as expected by the platform.
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
        config_params = {}

    env_cpy = os.environ.copy()

    get_hostname_and_random_port()

    assert messagebus in ('rmq', 'zmq'), 'Invalid messagebus specified, must be rmq or zmq.'

    if web_http and web_https:
        raise ValueError("Incompatabile tyeps web_https and web_Http cannot both be specified as True")

    default_env_options = ('VOLTTRON_HOME', 'MESSAGEBUS')

    for v in default_env_options:
        if v in env_options:
            raise ValueError(f"Cannot specify {v} in env_options as it is set already.")

    volttron_home = create_volttron_home()
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
        pass
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

    envs = dict(VOLTTRON_HOME=volttron_home, MESSAGEBUS=messagebus)
    os.environ.update(envs)
    try:
        yield config_file, envs
    finally:
        os.environ.clear()
        os.environ.update(env_cpy)
        shutil.rmtree(volttron_home, ignore_errors=True)
