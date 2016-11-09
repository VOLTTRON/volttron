import ConfigParser as configparser
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from contextlib import closing
from os.path import dirname
from subprocess import CalledProcessError

import gevent
import gevent.subprocess as subprocess
import requests
from agent_additions import add_vc_to_instance
from gevent.fileobject import FileObject
from gevent.subprocess import Popen
from volttron.platform import packaging
from volttron.platform.agent import utils
from volttron.platform.agent.utils import strip_comments
from volttron.platform.aip import AIPplatform
from volttron.platform.auth import (AuthFile, AuthEntry,
                                    AuthFileEntryAlreadyExists)
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.connection import Connection
from volttrontesting.utils.utils import get_rand_http_address
from volttrontesting.utils.utils import get_rand_tcp_address
from zmq.utils import jsonapi

utils.setup_logging()
_log = logging.getLogger(__name__)

RESTRICTED_AVAILABLE = False

# Change the connection timeout to default to 5 seconds rather than the default
# of 30 secondes
DEFAULT_TIMEOUT = 5

try:
    from volttron.restricted import (auth, certs)
    RESTRICTED_AVAILABLE = True

except ImportError:
    RESTRICTED_AVAILABLE = False
    auth = None
    certs = None

# Filenames for the config files which are created during setup and then
# passed on the command line
TMP_PLATFORM_CONFIG_FILENAME = "config"
TMP_SMAP_CONFIG_FILENAME = "test-smap.ini"

# Used to fill in TWISTED_CONFIG template
TEST_CONFIG_FILE = 'base-platform-test.json'

PLATFORM_CONFIG_UNRESTRICTED = """
no-resource-monitor
no-verify
no-mobility
"""


PLATFORM_CONFIG_RESTRICTED = """
mobility-address = {mobility-address}
control-socket = {tmpdir}/run/control
resource-monitor = {resource-monitor}
"""



TWISTED_CONFIG = """
[report 0]
ReportDeliveryLocation = {smap-uri}/add/{smap-key}

[/]
type = Collection
Metadata/SourceName = {smap-source}
uuid = {smap-uuid}

[/datalogger]
type = volttron.drivers.data_logger.DataLogger
interval = 1

"""

UNRESTRICTED = 0
VERIFY_ONLY = 1
RESOURCE_CHECK_ONLY = 2
RESTRICTED = 3

MODES = (UNRESTRICTED, VERIFY_ONLY, RESOURCE_CHECK_ONLY, RESTRICTED)

VOLTTRON_ROOT = dirname(dirname(dirname(os.path.realpath(__file__))))

if os.environ.get('CI', None) is None:
    VSTART = os.path.join(VOLTTRON_ROOT, "env/bin/volttron")
    VCTRL = os.path.join(VOLTTRON_ROOT, "env/bin/volttron-ctl")
    TWISTED_START = os.path.join(VOLTTRON_ROOT, "env/bin/twistd")
else:
    VSTART ="volttron"
    VCTRL = "volttron-ctl"
    TWISTED_START = "twistd"

SEND_AGENT = "send"

RUN_DIR = 'run'
PUBLISH_TO = RUN_DIR+'/publish'
SUBSCRIBE_TO = RUN_DIR+'/subscribe'


class PlatformWrapperError(StandardError):
    pass


def build_vip_address(dest_wrapper, agent):
    """
    Create a usable vip address with zap parameters embedded in the uri.

    :param dest_wrapper:PlatformWrapper:
        The destination wrapper instance that the agent will be attempting to
        connect to.
    :param agent:Agent
        The agent that is being used to make the connection to dest_wrapper
    :return:
    """
    return "{}:?serverkey={}&publickey={}&secretkey={}".format(
        dest_wrapper.vip_address, dest_wrapper.publickey,
        agent.core.publickey, agent.core.secretkey
    )


def start_wrapper_platform(wrapper, with_http=False, with_tcp=True,
                           volttron_central_address=None):
    """ Customize easily customize the platform wrapper before starting it.
    """
    assert not wrapper.is_running()

    vc_http = get_rand_http_address() if with_http else None
    vc_tcp = get_rand_tcp_address() if with_tcp else None
    if vc_tcp:
        encrypt = True
    else:
        encrypt = False
    wrapper.startup_platform(encrypt=encrypt, vip_address=vc_tcp,
                             bind_web_address=vc_http,
                             volttron_central_address=volttron_central_address)
    if with_http:
        discovery = "{}/discovery/".format(vc_http)
        response = requests.get(discovery)
        assert response.ok

    assert wrapper.is_running()


class PlatformWrapper:
    def __init__(self):
        """ Initializes a new VOLTTRON instance

        Creates a temporary VOLTTRON_HOME directory with a packaged directory
        for agents that are built.
        """

        self.volttron_home = tempfile.mkdtemp()
        self.packaged_dir = os.path.join(self.volttron_home, "packaged")
        os.makedirs(self.packaged_dir)

        # in the context of this platform it is very important not to
        # use the main os.environ for anything.
        self.env = {
            'VOLTTRON_HOME': self.volttron_home,
            'PACKAGED_DIR': self.packaged_dir,
            'DEBUG_MODE': os.environ.get('DEBUG_MODE', ''),
            'DEBUG': os.environ.get('DEBUG', ''),
            'PATH': VOLTTRON_ROOT+':'+os.environ['PATH']
        }

        # By default no web server should be started.
        self.bind_web_address = None
        self.discovery_address = None
        self.jsonrpc_endpoint = None
        self.volttron_central_address = None
        self.instance_name = None
        self.serverkey = None

        self.p_process = None
        self.t_process = None

        self.started_agent_pids = []
        self.local_vip_address = None
        self.vip_address = None
        self.encrypt = False
        self.logit('Creating platform wrapper')

        # This was used when we are testing the SMAP historian.
        self.use_twistd = False

        # Added restricted code properties
        self.certsobj = None

        # Control whether the instance directory is cleaned up when shutdown.
        # if the environment variable DEBUG is set to a True value then the
        # instance is not cleaned up.
        self.skip_cleanup = False

        # This is used as command line entry replacement.  Especially working
        # with older 2.0 agents.
        self.opts = None

        keystorefile = os.path.join(self.volttron_home, 'keystore')
        self.keystore = KeyStore(keystorefile)
        self.keystore.generate()

    def logit(self, message):
        print('{}: {}'.format(self.volttron_home, message))

    def allow_all_connections(self):
        """ Add a /.*/ entry to the auth.json file.
        """
        entry = AuthEntry(credentials="/.*/")
        authfile = AuthFile(self.volttron_home + "/auth.json")
        try:
            authfile.add(entry)
        except AuthFileEntryAlreadyExists:
            pass

    def build_connection(self, peer=None, address=None, identity=None,
                         publickey=None, secretkey=None, serverkey=None,
                         **kwargs):

        if self.encrypt:
            self.allow_all_connections()

        if address is None:
            address = self.vip_address
            serverkey = self.serverkey

        if publickey is None or secretkey is None:
            self.logit('generating new public secret key pair')
            keyfile = tempfile.mktemp(".keys", "agent", self.volttron_home)
            keys = KeyStore(keyfile)
            keys.generate()
            publickey = keys.public
            secretkey = keys.secret
        if self.encrypt:
            conn = Connection(address=address, peer=peer, publickey=publickey,
                              secretkey=secretkey, serverkey=serverkey,
                              volttron_home=self.volttron_home)
        else:
            conn = Connection(address=self.local_vip_address, peer=peer,
                              volttron_home=self.volttron_home,
                              developer_mode=True)
        return conn

    def build_agent(self, address=None, should_spawn=True, identity=None,
                    publickey=None, secretkey=None, serverkey=None,
                    agent_class=Agent, **kwargs):
        """ Build an agent connnected to the passed bus.

        By default the current instance that this class wraps will be the
        vip address of the agent.

        :param address:
        :param should_spawn:
        :param identity:
        :param publickey:
        :param secretkey:
        :param serverkey:
        :param agent_class: Agent class to build
        :return:
        """
        self.logit("Building generic agent.")

        use_ipc = kwargs.pop('use_ipc', False)
        if self.encrypt:
            if serverkey is None:
                serverkey=self.serverkey
            if publickey is None:
                self.logit('generating new public secret key pair')
                keyfile = tempfile.mktemp(".keys", "agent", self.volttron_home)
                keys = KeyStore(keyfile)
                keys.generate()
                publickey=keys.public
                secretkey=keys.secret

        if address is None:
            if not self.encrypt:
                self.logit('Using IPC vip-address')
                address = "ipc://@"+self.volttron_home+"/run/vip.socket"
            else:
                self.logit('Using vip-address '+self.vip_address)
                address = self.vip_address

        if publickey and not serverkey:
            self.logit('using instance serverkey: {}'.format(self.publickey))
            serverkey = self.publickey

        agent = agent_class(address=address, identity=identity,
                            publickey=publickey, secretkey=secretkey,
                            serverkey=serverkey,
                            volttron_home=self.volttron_home,
                            developer_mode=(not self.encrypt),
                            **kwargs)
        self.logit('platformwrapper.build_agent.address: {}'.format(address))

        # Automatically add agent's credentials to auth.json file
        if publickey:
            self.logit('Adding publickey to auth.json')
            gevent.spawn(self._append_allow_curve_key, publickey)
            gevent.sleep(0.1)

        if should_spawn:
            self.logit('platformwrapper.build_agent spawning')
            event = gevent.event.Event()
            gevent.spawn(agent.core.run, event)#.join(0)
            event.wait(timeout=2)

            hello = agent.vip.hello().get(timeout=.3)
            self.logit('Got hello response {}'.format(hello))
        agent.publickey = publickey
        return agent

    def _read_auth_file(self):
        auth_path = os.path.join(self.volttron_home, 'auth.json')
        try:
            with open(auth_path, 'r') as fd:
                data = strip_comments(FileObject(fd, close=False).read())
                if data:
                    auth = jsonapi.loads(data)
                else:
                    auth = {}
        except IOError:
            auth = {}
        if not 'allow' in auth:
            auth['allow'] = []
        return auth, auth_path

    def _append_allow_curve_key(self, publickey):
        entry = AuthEntry(credentials=publickey)
        authfile = AuthFile(self.volttron_home + "/auth.json")
        try:
            authfile.add(entry)
        except AuthFileEntryAlreadyExists:
            pass

    def add_vc(self):
        return add_vc_to_instance(self)

    def add_capabilities(self, publickey, capabilities):
        if isinstance(capabilities, basestring):
            capabilities = [capabilities]
        auth, auth_path = self._read_auth_file()
        cred = publickey
        allow = auth['allow']
        entry = next((item for item in allow if item['credentials'] == cred), {})
        caps = entry.get('capabilities', [])
        entry['capabilities'] = list(set(caps + capabilities))

        with open(auth_path, 'w+') as fd:
            json.dump(auth, fd)

    def set_auth_dict(self, auth_dict):
        if auth_dict:
            with open(os.path.join(self.volttron_home, 'auth.json'), 'w') as fd:
                fd.write(json.dumps(auth_dict))

    def startup_platform(self, vip_address, auth_dict=None, use_twistd=False,
        mode=UNRESTRICTED, encrypt=False, bind_web_address=None,
        volttron_central_address=None, volttron_central_serverkey=None):

        # if not isinstance(vip_address, list):
        #     self.vip_address = [vip_address]
        # else:
        #     self.vip_address = vip_address

        self.vip_address = vip_address
        self.encrypt = encrypt
        self.mode = mode
        self.bind_web_address = bind_web_address
        if self.bind_web_address:
            self.discovery_address = "{}/discovery/".format(
                self.bind_web_address)

            # Only available if vc is installed!
            self.jsonrpc_endpoint = "{}/jsonrpc".format(
                self.bind_web_address)

        enable_logging = self.env.get('ENABLE_LOGGING', False)
        debug_mode = self.env.get('DEBUG_MODE', False)
        if not debug_mode:
            debug_mode = self.env.get('DEBUG', False)
        self.skip_cleanup = self.env.get('SKIP_CLEANUP', False)
        if debug_mode:
            self.skip_cleanup = True
            enable_logging = True
        self.logit("In start up platform enable_logging is {} ".format(enable_logging))
        assert self.mode in MODES, 'Invalid platform mode set: '+str(mode)
        opts = None

        # see main.py for how we handle pub sub addresses.
        ipc = 'ipc://{}{}/run/'.format(
            '@' if sys.platform.startswith('linux') else '',
            self.volttron_home)
        self.local_vip_address = ipc + 'vip.socket'
        self.set_auth_dict(auth_dict)

        self.opts = {'verify_agents': False,
                     'volttron_home': self.volttron_home,
                     'vip_address': vip_address,
                     'vip_local_address': ipc + 'vip.socket',
                     'publish_address': ipc + 'publish',
                     'subscribe_address': ipc + 'subscribe',
                     'bind_web_address': bind_web_address,
                     'volttron_central_address': volttron_central_address,
                     'volttron_central_serverkey': volttron_central_serverkey,
                     'platform_name': None,
                     'developer_mode': not encrypt,
                     'log': os.path.join(self.volttron_home, 'volttron.log'),
                     'log_config': None,
                     'monitor': True,
                     'autostart': True,
                     'log_level': logging.DEBUG,
                     'verboseness': logging.DEBUG}

        pconfig = os.path.join(self.volttron_home, 'config')
        config = {}

        # Add platform's public key to known hosts file
        publickey = self.keystore.public
        known_hosts_file = os.path.join(self.volttron_home, 'known_hosts')
        known_hosts = KnownHostsStore(known_hosts_file)
        known_hosts.add(self.opts['vip_local_address'], publickey)
        known_hosts.add(self.opts['vip_address'], publickey)

        # Set up the configuration file based upon the passed parameters.
        parser = configparser.ConfigParser()
        parser.add_section('volttron')
        parser.set('volttron', 'vip-address', vip_address)
        if bind_web_address:
            parser.set('volttron', 'bind-web-address', bind_web_address)
        if volttron_central_address:
            parser.set('volttron', 'volttron-central-address',
                       volttron_central_address)

        if self.mode == UNRESTRICTED:
            # TODO Restricted code should set with volttron as contianer
            # if RESTRICTED_AVAILABLE:
            #     config['mobility'] = False
            #     config['resource-monitor'] = False
            #     config['verify'] = False
            with closing(open(pconfig, 'wb')) as cfg:
                cfg.write(PLATFORM_CONFIG_UNRESTRICTED.format(**config))
                parser.write(cfg)

        elif self.mode == RESTRICTED:
            if not RESTRICTED_AVAILABLE:
                raise ValueError("restricted is not available.")

            certsdir = os.path.join(self.volttron_home, 'certificates')

            print ("certsdir", certsdir)
            self.certsobj = certs.Certs(certsdir)

            with closing(open(pconfig, 'wb')) as cfg:
                cfg.write(PLATFORM_CONFIG_RESTRICTED.format(**config))
            # opts = type('Options', (), {'resource-monitor':False,
            #                             'verify_agents': True,
            #                             'volttron_home': self.volttron_home})()
        else:
            raise PlatformWrapperError("Invalid platform mode specified: {}".format(mode))

        log = os.path.join(self.volttron_home, 'volttron.log')
        if enable_logging:
            cmd = ['volttron', '-vv', '-l{}'.format(log)]
        else:
            cmd = ['volttron', '-l{}'.format(log)]

        if not encrypt:
            cmd.append('--developer-mode')
        print('process environment: {}'.format(self.env))
        print('popen params: {}'.format(cmd))
        self.p_process = Popen(cmd, env=self.env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

        assert self.p_process is not None
        # A None value means that the process is still running.
        # A negative means that the process exited with an error.
        assert self.p_process.poll() is None

        self.serverkey = self.keystore.public
        assert self.serverkey
        agent = self.build_agent()

        has_control = False
        times = 0
        while not has_control and times < 10:
            times += 1
            try:
                has_control = agent.vip.peerlist().get(timeout=.2)
            except gevent.Timeout:
                pass

        if not has_control:
            self.shutdown_platform()
            raise "Couldn't connect to core platform!"

        if bind_web_address:
            times = 0
            has_discovery = False
            while times < 10:
                times += 1
                try:
                    resp = requests.get(self.discovery_address)
                    if resp.ok:
                        has_discovery = True
                        break
                except Exception as e:
                    gevent.sleep(0.1)
                    self.logit("Connection error found {}".format(e))
            if not has_discovery:
                raise "Couldn't connect to discovery platform."

        self.use_twistd = use_twistd

        # TODO: Revise this to start twistd with platform.
        if self.use_twistd:
            tconfig = os.path.join(self.volttron_home, TMP_SMAP_CONFIG_FILENAME)

            with closing(open(tconfig, 'w')) as cfg:
                cfg.write(TWISTED_CONFIG.format(**config))

            tparams = [TWISTED_START, "-n", "smap", tconfig]
            self.t_process = subprocess.Popen(tparams, env=self.env)
            time.sleep(5)
            #self.t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])

    def is_running(self):
        self.logit("PROCESS IS RUNNING: {}".format(self.p_process))
        return self.p_process is not None and self.p_process.poll() is None

    def twistd_is_running(self):
        return self.t_process is not None

    # def publish(self, topic, data):
    #     '''Publish data to a zmq context.
    #
    #     The publisher is goint to use the platform that is contained within
    #     this wrapper to write data to.
    #     '''
    #     if not self.zmq_context:
    #         self.zmq_context = zmq.Context()
    #     self.logit("binding publisher to: ", self.env['AGENT_PUB_ADDR'])
    #     pub = zmq.Socket(self.zmq_context, zmq.PUB)
    #     pub.bind(self.env['AGENT_PUB_ADDR'])
    #     pub.send_multipart([topic, data])

    # def fillout_file(self, filename, template, config_file):
    #
    #     try:
    #         config = json.loads(open(config_file, 'r').read())
    #     except Exception as e:
    #         sys.stderr.write (str(e))
    #         raise PlatformWrapperError("Could not load configuration file for tests")
    #
    #     config['tmpdir'] = self.tmpdir
    #
    #     outfile = os.path.join(self.tmpdir, filename)
    #     with closing(open(outfile, 'w')) as cfg:
    #         cfg.write(template.format(**config))
    #
    #     return outfile

    def direct_sign_agentpackage_creator(self, package):
        assert (RESTRICTED), "Auth not available"
        print ("wrapper.certsobj", self.certsobj.cert_dir)
        assert(auth.sign_as_creator(package, 'creator', certsobj=self.certsobj)), "Signing as {} failed.".format('creator')

    def direct_sign_agentpackage_admin(self, package):
        assert (RESTRICTED), "Auth not available"
        assert(auth.sign_as_admin(package, 'admin', certsobj=self.certsobj)), "Signing as {} failed.".format('admin')

    def direct_sign_agentpackage_initiator(self, package, config_file, contract):
        assert (RESTRICTED), "Auth not available"
        files = {"config_file":config_file,"contract":contract}
        assert(auth.sign_as_initiator(package, 'initiator', files=files,
                                      certsobj=self.certsobj)), "Signing as {} failed.".format('initiator')

    def _aip(self):
        opts = type('Options', (), self.opts)
        aip = AIPplatform(opts)
        aip.setup()
        return aip

    def _install_agent(self, wheel_file, start, vip_identity):

        self.logit('Creating channel for sending the agent.')
        gevent.sleep(0.3)
        self.logit('calling control install agent.')
        self.logit("VOLTTRON_HOME SETTING: {}".format(
            self.env['VOLTTRON_HOME']))
        env = self.env.copy()
        cmd = ['volttron-ctl', '-vv', 'install', wheel_file]
        if vip_identity:
            cmd.extend(['--vip-identity', vip_identity])
        if self.opts.get('developer_mode', False):
            cmd.append('--developer-mode')
        res = subprocess.check_output(cmd, env=env)
        assert res, "failed to install wheel:{}".format(wheel_file)
        agent_uuid = res.split(' ')[-2]
        self.logit(agent_uuid)

        if start:
             self.start_agent(agent_uuid)

        return agent_uuid

    def install_multiple_agents(self, agent_configs):
        """
        Installs mutltiple agents on the platform.

        :param agent_configs:list
            A list of 3-tuple that allows the configuration of a platform
            in a single go.  The tuple order is
            1. path to the agent directory.
            2. configuration data (either file or json data)
            3. Whether the agent should be started or not.

        :return:list:
            A list of uuid's associated with the agents that were installed.


        :Note:
            In order for this method to be called the platform must be
            currently running.
        """
        if not self.is_running():
            raise PlatformWrapperError("Instance isn't running!")
        results = []

        for path, config, start  in agent_configs:
            results = self.install_agent(agent_dir=path, config_file=config,
                                         start=start)

        return results

    def install_agent(self, agent_wheel=None, agent_dir=None, config_file=None,
        start=True, vip_identity=None):
        """ Install and optionally start an agent on the instance.

            This function allows installation from an agent wheel or an
            agent directory (NOT BOTH).  If an agent_wheel is specified then
            it is assumed to be ready for installation (has a config file).
            If an agent_dir is specified then a config_file file must be
            specified or if it is not specified then it is assumed that the
            file agent_dir/config is to be used as the configuration file.  If
            none of these exist then an assertion error will be thrown.

            This function will return with a uuid of the installed agent.
        :param agent_wheel:
        :param agent_dir:
        :param config_file:
        :param start:
        :param vip_identity:
        :return:
        """

        assert self.is_running(), "Instance must be running to install agent."
        assert agent_wheel or agent_dir, "Invalid agent_wheel or agent_dir."

        if agent_wheel:
            assert not agent_dir
            assert not config_file
            assert os.path.exists(agent_wheel)
            wheel_file = agent_wheel

        if agent_dir:
            assert not agent_wheel
            if isinstance(config_file, dict):
                from os.path import join, basename
                temp_config = join(self.volttron_home,
                                   basename(agent_dir) + "_config_file")
                with open(temp_config, "w") as fp:
                    fp.write(json.dumps(config_file))
                config_file = temp_config
            elif not config_file:
                assert os.path.exists(os.path.join(agent_dir, "config"))
                config_file = os.path.join(agent_dir, "config")
            elif os.path.exists(config_file):
                pass  # config_file already set!
            else:
                raise ValueError("Can't determine correct config file.")

            self.logit('Building agent package')
            wheel_file = self.build_agentpackage(agent_dir, config_file)
            assert wheel_file
        agent_uuid = self._install_agent(wheel_file, start, vip_identity)

        assert agent_uuid is not None

        if start:
            assert self.is_agent_running(agent_uuid)

        return agent_uuid

    def start_agent(self, agent_uuid):
        self.logit('Starting agent {}'.format(agent_uuid))
        self.logit("VOLTTRON_HOME SETTING: {}".format(
            self.env['VOLTTRON_HOME']))
        cmd = ['volttron-ctl']
        if self.opts.get('developer_mode', False):
            cmd.append('--developer-mode')
        cmd.extend(['start', agent_uuid])
        p = Popen(cmd, env=self.env,
                  stdout=sys.stdout, stderr=sys.stderr)
        p.wait()

        # Confirm agent running
        cmd = ['volttron-ctl']
        if self.opts.get('developer_mode', False):
            cmd.append('--developer-mode')
        cmd.extend(['status', agent_uuid])
        res = subprocess.check_output(cmd, env=self.env)
        #776 TODO: Timing issue where check fails
        time.sleep(.1)
        self.logit("Subprocess res is {}".format(res))
        assert 'running' in res
        pidpos = res.index('[') + 1
        pidend = res.index(']')
        pid = int(res[pidpos: pidend])

        self.started_agent_pids.append(pid)
        return int(pid)

    def stop_agent(self, agent_uuid):
        # Confirm agent running
        _log.debug("STOPPING AGENT: {}".format(agent_uuid))
        try:
            cmd = ['volttron-ctl']
            if self.opts.get('developer_mode', False):
                cmd.append('--developer-mode')
            cmd.extend(['stop', agent_uuid])
            res = subprocess.check_output(cmd, env=self.env)
        except CalledProcessError as ex:
            _log.error("Exception: {}".format(ex))
        return self.agent_status(agent_uuid)

    def list_agents(self):
        agent = self.build_agent()
        print('PEER LIST: {}'.format(agent.vip.peerlist().get(timeout=10)))
        agent_list = agent.vip.rpc('control', 'list_agents').get(timeout=10)
        agent.core.stop(timeout=3)
        return agent_list

    def remove_agent(self, agent_uuid):
        """Remove the agent specified by agent_uuid"""
        _log.debug("REMOVING AGENT: {}".format(agent_uuid))
        try:
            cmd = ['volttron-ctl']
            if self.opts.get('developer_mode', False):
                cmd.append('--developer-mode')
            cmd.extend(['remove', agent_uuid])
            res = subprocess.check_output(cmd, env=self.env)
        except CalledProcessError as ex:
            _log.error("Exception: {}".format(ex))
        return self.agent_status(agent_uuid)

    def is_agent_running(self, agent_uuid):
        return self.agent_status(agent_uuid) is not None

    def agent_status(self, agent_uuid):
        _log.debug("AGENT_STATUS: {}".format(agent_uuid))
        # Confirm agent running
        cmd = ['volttron-ctl']
        if self.opts.get('developer_mode', False):
            cmd.append('--developer-mode')
        cmd.extend(['status', agent_uuid])
        pid = None
        try:
            res = subprocess.check_output(cmd, env=self.env)
            try:
                pidpos = res.index('[') + 1
                pidend = res.index(']')
                pid = int(res[pidpos: pidend])
            except:
                pid = None
        except CalledProcessError as ex:
            _log.error("Exception: {}".format(ex))

        return pid

    def build_agentpackage(self, agent_dir, config_file):
        assert os.path.exists(agent_dir)
        assert os.path.exists(config_file)
        wheel_path = packaging.create_package(agent_dir,
                                              self.packaged_dir)
        packaging.add_files_to_package(wheel_path, {
            'config_file': os.path.join('./', config_file)
        })

        return wheel_path

    # def direct_build_agentpackage(self, agent_dir):
    #     self.logit("Building agent_directory ", agent_dir)
    #     wheel_path = packaging.create_package(os.path.join('./', agent_dir),
    #                                           self.packaged_dir)
    #
    #     return wheel_path
    #
    # def direct_send_agent(self, package, target):
    #     pparams = [VCTRL, SEND_AGENT, target, package]
    #     print (pparams, "CWD", os.getcwd())
    #     send_process = subprocess.call(pparams, env=self.env)
    #     print ("Done sending to", target)
    #
    # def direct_configure_agentpackage(self, agent_wheel, config_file):
    #     packaging.add_files_to_package(agent_wheel, {
    #                             'config_file':os.path.join('./', config_file)
    #                         })
    #
    #

#     def direct_build_install_agent(self, agent_dir, config_file):
#         agent_wheel = self.build_agentpackage(agent_dir=agent_dir,
#             config_file=config_file)
#         self.direct_configure_agentpackage(agent_wheel, config_file)
#         assert(agent_wheel is not None,"Agent wheel was not built")
#
#         uuid = self.test_aip.install_agent(agent_wheel)
#         #aip volttron_home, verify_agents
#         return uuid
# #         conn.call.start_agent()



    # def direct_build_install_run_agent(self, agent_dir, config_file):
    #     agent_uuid = self.direct_build_install_agent(agent_dir, config_file)
    #     self.direct_start_agent(agent_uuid)
    #     return agent_uuid
    #
    # def direct_build_send_agent(self, agent_dir, config_file, target):
    #     agent_uuid = self.direct_buid_install_agent(agent_dir, config_file)
    #     self.direct_start_agent(agent_uuid)
    #     return agent_uuid

    def confirm_agent_running(self, agent_name, max_retries=5, timeout_seconds=2):
        running = False
        retries = 0
        while not running and retries < max_retries:
            status = self.test_aip.status_agents()
            print ("Status", status)
            if len(status) > 0:
                status_name = status[0][1]
                assert status_name == agent_name

                assert len(status[0][2]) == 2, 'Unexpected agent status message'
                status_agent_status = status[0][2][1]
                running = not isinstance(status_agent_status, int)
            retries += 1
            time.sleep(timeout_seconds)
        return running


    # def direct_stop_agent(self, agent_uuid):
    #     result = self.conn.call.stop_agent(agent_uuid)
    #     print result

    def shutdown_platform(self):
        '''Stop platform here

           This function will shutdown the platform and attempt to kill any
           process that the platformwrapper has started.
        '''
        import signal
        self.logit('shutting down platform: PIDS: {}'.format(self.started_agent_pids))
        while self.started_agent_pids:
            pid = self.started_agent_pids.pop()
            self.logit('ending pid: {}'.format(pid))
            try:
                os.kill(pid, signal.SIGTERM)
            except:
                self.logit('could not kill: {} '.format(pid))

        if self.p_process is not None:
            try:
                gevent.sleep(0.2)
                self.p_process.terminate()
                gevent.sleep(0.2)
            except OSError:
                self.logit('Platform process was terminated.')
        else:
            self.logit("platform process was null")

        if self.use_twistd and self.t_process != None:
            self.t_process.kill()
            self.t_process.wait()
        elif self.use_twistd:
            self.logit("twistd process was null")
        if not self.skip_cleanup:
            self.logit('Removing {}'.format(self.volttron_home))
            shutil.rmtree(self.volttron_home, ignore_errors=True)


def mergetree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            mergetree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(src).st_mtime - os.stat(dst).st_mtime > 1:
                shutil.copy2(s, d)
