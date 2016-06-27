import ConfigParser as configparser
import urlparse
from contextlib import closing
import json
import logging
import os
import shutil
import sys
import tempfile
import time

import gevent
from gevent.fileobject import FileObject
import gevent.subprocess as subprocess
from gevent.subprocess import Popen
from subprocess import CalledProcessError

from os.path import dirname

import zmq
from volttron.platform.vip.connection import Connection
from volttron.platform.web import build_vip_address_string
from zmq.utils import jsonapi


from volttron.platform.auth import AuthFile, AuthEntry
from volttron.platform.keystore import KeyStore
from volttron.platform.agent.utils import strip_comments
from volttron.platform.messaging import topics
from volttron.platform.main import start_volttron_process
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.socket import encode_key
from volttron.platform.aip import AIPplatform
#from volttron.platform.control import client, server
from volttron.platform import packaging
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

RESTRICTED_AVAILABLE = False

try:
    from volttron.restricted import (auth, certs)
    RESTRICTED_AVAILABLE = True

except ImportError:
    RESTRICTED_AVAILABLE = False
    auth = None
    certs = None

#Filenames for the config files which are created during setup and then
#passed on the command line
TMP_PLATFORM_CONFIG_FILENAME = "config"
TMP_SMAP_CONFIG_FILENAME = "test-smap.ini"

#Used to fill in TWISTED_CONFIG template
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


class PlatformWrapper:
    def __init__(self, volttron_home=None):
        '''Initializes a new volttron environment

        Creates a temporary VOLTTRON_HOME directory with a packaged directory for
        agents that are built.
        '''
        if volttron_home is None:
            self.__volttron_home = tempfile.mkdtemp()

            self.env = dict(
                VOLTTRON_HOME=self.__volttron_home,
                PATH=os.environ['PATH']
            )
        else:
            self.__volttron_home = volttron_home

        self.__packaged_dir = os.path.join(self.volttron_home, "packaged")
        os.makedirs(self.__packaged_dir)

        # By default no web server should be started.
        self.__bind_web_address = None

        self._p_process = None
        self._t_process = None
        self.__publickey = self.generate_key()
        self._started_pids = []
        self.__local_vip_address = None
        self.__vip_address = None
        self.__encrypted = False
        self.__volttron_central_address = None
        self.__volttron_central_serverkey = None
        self.__local_vip_address = None
        self.__control = None
        self.logit('Creating platform wrapper')

    def logit(self, message):
        print('{}: {}'.format(self.volttron_home, message))

    @property
    def encrypted(self):
        return self.__encrypted

    @property
    def bind_web_address(self):
        return self.__bind_web_address

    @bind_web_address.setter
    def bind_web_address(self, value):
        if value is None:
            raise ValueError("bind_web_address cannot have None value.")
        parsed = urlparse.urlparse(value)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError("bind_web_addres must have http or https scheme.")
        self.__bind_web_address = value

    @property
    def local_vip_address(self):
        return self.__local_vip_address

    @property
    def packaged_dir(self):
        return self.__packaged_dir

    @property
    def publickey(self):
        return self.__publickey

    @property
    def local_vip_address(self):
        return self.__local_vip_address

    @property
    def vip_address(self):
        return self.__vip_address

    @vip_address.setter
    def vip_address(self, value):
        if value is None:
            raise ValueError("Setting of vip_address requires a value.")
        self.__vip_address = value

    @property
    def volttron_central_address(self):
        return self.__volttron_central_address

    @volttron_central_address.setter
    def volttron_central_address(self, value):
        self.__volttron_central_address = value

    @property
    def volttron_central_serverkey(self):
        return self.__volttron_central_serverkey

    @volttron_central_serverkey.setter
    def volttron_central_serverkey(self, value):
        self.__volttron_central_address = value

    @property
    def volttron_home(self):
        return self.__volttron_home

    def allow_all_connections(self):
        """ Add a CURVE:.* entry to the auth.json file.
        """
        entry = AuthEntry(credentials="/CURVE:.*/")
        authfile = AuthFile(self.volttron_home+"/auth.json")
        authfile.add(entry)

    def build_connection(self, peer):
        self.logit('generating new public secret key pair for connecction')
        tf = tempfile.NamedTemporaryFile()
        ks = KeyStore(tf.name)
        ks.generate()
        publickey = ks.public()
        secretkey = ks.secret()
        # Strip off the key and stuff from the vip address.
        parsed = urlparse.urlparse(self.vip_address)
        address = "{}://{}".format(parsed.scheme, parsed.netloc)
        # Build address of new agent.
        address = build_vip_address_string(address, self.publickey,
                                           publickey, secretkey)

        # Add properties on for testing environment.
        connection = Connection(address, peer=peer)
        connection.publickey = publickey
        connection.secretkey = secretkey
        connection.serverkey = self.publickey

        return connection

    def build_agent(self, address=None, should_spawn=True, identity=None,
                    publickey=None, secretkey=None, serverkey=None,
                    generatekeys=False, **kwargs):
        """ Build an agent connnected to the passed bus.

        By default the current instance that this class wraps will be the
        vip address of the agent.

        :param address:
        :param should_spawn:
        :param identity:
        :param publickey:
        :param secretkey:
        :param serverkey:
        :return:
        """
        self.logit("Building generic agent.")
        assert self.is_running()
        use_ipc = kwargs.pop('use_ipc', False)
        if address is None:
            if use_ipc:
                self.logit('Using IPC vip-address')
                address = "ipc://@"+self.volttron_home+"/run/vip.socket"
            else:
                self.logit('Using vip-address '+self.vip_address)
                address = self.vip_address

        if generatekeys or (publickey is None and serverkey is None and
                                    self.encrypted):
            self.logit('generating new public secret key pair')
            tf = tempfile.NamedTemporaryFile()
            ks = KeyStore(tf.name)
            ks.generate()
            publickey = ks.public()
            secretkey = ks.secret()

        if publickey and not serverkey:
            self.logit('using instance serverkey: {}'.format(self.publickey))
            serverkey = self.publickey

        agent = Agent(address=address, identity=identity, publickey=publickey,
                      secretkey=secretkey, serverkey=serverkey, **kwargs)
        self.logit('platformwrapper.build_agent.address: {}'.format(address))

        # Automatically add agent's credentials to auth.json file
        if publickey:
            self.logit('Adding publickey to auth.json')
            gevent.spawn(self._append_allow_curve_key, publickey)
            gevent.sleep(0.1)

        if should_spawn:
            self.logit('platformwrapper.build_agent spawning')
            self.logit('Agent connecting to: {}'.format(agent.core.address))
            event = gevent.event.Event()
            gevent.spawn(agent.core.run, event)#.join(0)
            event.wait(timeout=2)

            hello = agent.vip.hello().get(timeout=.3)
            self.logit('Got hello response {}'.format(hello))

        return agent

    def generate_key(self):
        key = ''.join(zmq.curve_keypair())
        with open(os.path.join(self.volttron_home, 'curve.key'), 'w') as fd:
            fd.write(key)
        return encode_key(key[:40])  # public key

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
        entry = AuthEntry(credentials="CURVE:{}".format(publickey))
        authfile = AuthFile(self.volttron_home+"/auth.json")
        authfile.add(entry)

    def add_capabilities(self, publickey, capabilities):
        if isinstance(capabilities, basestring):
            capabilities = [capabilities]
        auth, auth_path = self._read_auth_file()
        cred = 'CURVE:{}'.format(publickey)
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

    def startup_platform(self, vip_address=None, auth_dict=None,
                         use_twistd=False, mode=UNRESTRICTED, encrypt=False,
                         bind_web_address=None, volttron_central_address=None,
                         volttron_central_serverkey=None):
        os.environ['VOLTTRON_HOME'] = self.__volttron_home
        self.logit('Starting platform - VOLTTRON_HOME: {}'.format(
            self.volttron_home))

        if vip_address is None:
            if self.vip_address is None:
                raise AttributeError(
                    "vip-address not specified nor set on instance.")
        else:
            self.vip_address = vip_address
        self.mode = mode
        self.bind_web_address = bind_web_address
        self.__encrypted = encrypt

        self.platform_name = ''
        self.volttron_central_address = volttron_central_address
        self.logit('VC BEFORE: {}'.format(volttron_central_address))
        if volttron_central_address:
            if '|' in volttron_central_address:
                self.platform_name, self.volttron_central_address = \
                    volttron_central_address.split('|')
        self.logit('VC AFTER: {}'.format(volttron_central_address))
        self.logit('self.VC BEFORE: {}'.format(self.volttron_central_address))
        self.volttron_central_serverkey = volttron_central_serverkey
        self.logit('PLATFORM NAME IS: {}'.format(self.platform_name))
        enable_logging = os.environ.get('ENABLE_LOGGING', False)
        debug_mode = os.environ.get('DEBUG_MODE', False)
        if not debug_mode:
            debug_mode = os.environ.get('DEBUG', False)
        self.skip_cleanup = os.environ.get('SKIP_CLEANUP', False)
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
        self.__local_vip_address = ipc + 'vip.socket'
        if not encrypt:
            if os.path.exists(os.path.join(self.volttron_home, 'curve.key')):
                # Remove connection encryption
                with open(os.path.join(self.volttron_home, 'curve.key'), 'w'):
                    pass

        for k, v in self.__dict__.items():
            self.logit("configuration: {} => {}".format(k, v))

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
                     'log': os.path.join(self.volttron_home,'volttron.log'),
                     'log_config': None,
                     'monitor': True,
                     'autostart': True,
                     'log_level': logging.DEBUG,
                     'verboseness': logging.DEBUG}

        pconfig = os.path.join(self.volttron_home, 'config')
        config = {}

        parser =  configparser.ConfigParser()
        parser.add_section('volttron')
        parser.set('volttron', 'vip-address', self.vip_address)
        if self.bind_web_address:
            parser.set('volttron', 'bind-web-address', self.bind_web_address)
        if self.volttron_central_address:
            parser.set('volttron', 'volttron-central-address',
                       volttron_central_address)
        if self.mode == UNRESTRICTED:
            if RESTRICTED_AVAILABLE:
                config['mobility'] = False
                config['resource-monitor'] = False
                config['verify'] = False
            with closing(open(pconfig, 'wb')) as cfg:
                cfg.write(PLATFORM_CONFIG_UNRESTRICTED.format(**config))
                parser.write(cfg)

        elif self.mode == RESTRICTED:
            if not RESTRICTED_AVAILABLE:
                raise ValueError("restricted is not available.")

            certsdir = os.path.join(os.path.expanduser(self.env['VOLTTRON_HOME']),
                                    'certificates')

            print ("certsdir", certsdir)
            self.certsobj = certs.Certs(certsdir)

            with closing(open(pconfig, 'wb')) as cfg:
                cfg.write(PLATFORM_CONFIG_RESTRICTED.format(**config))
            opts = type('Options', (), {'resource-monitor':False,
                                        'verify_agents': True,
                                        'volttron_home': self.volttron_home})()
        else:
            raise PlatformWrapperError("Invalid platform mode specified: {}".format(mode))

        log = os.path.join(self.env['VOLTTRON_HOME'], 'volttron.log')
        if enable_logging:
            cmd = ['volttron', '-vv', '-l{}'.format(log)]
        else:
            cmd = ['volttron', '-l{}'.format(log)]

        if self.opts['developer_mode']:
            cmd.append('--developer-mode')

        self.logit("popen arguments are: {}".format(cmd))
        self._p_process = Popen(cmd, env=self.env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        assert self._p_process is not None
        # A None value means that the process is still running.
        # A negative means that the process exited with an error.
        assert self._p_process.poll() is None

        # # make sure we don't return too quickly.
        gevent.sleep(0.2)
        gevent.sleep(0.2)
        self.use_twistd = use_twistd

        #TODO: Revise this to start twistd with platform.
        if self.use_twistd:
            tconfig = os.path.join(self.volttron_home, TMP_SMAP_CONFIG_FILENAME)

            with closing(open(tconfig, 'w')) as cfg:
                cfg.write(TWISTED_CONFIG.format(**config))

            tparams = [TWISTED_START, "-n", "smap", tconfig]
            self._t_process = subprocess.Popen(tparams, env=self.env)
            time.sleep(5)
            #self._t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])

        self.__control = Connection(self.local_vip_address, peer="control")
        # Loop until we are sure that the platform is started up.
        while True:
            if 'control' in self.__control.server.vip.peerlist().get(
                    timeout=10):
                _log.debug('CONTROL FOUND!')
                break
            gevent.sleep(0.2)

    def is_running(self):
        self.logit("PROCESS IS RUNNING: {}".format(self._p_process))
        return self._p_process is not None and self._p_process.poll() is None

    def twistd_is_running(self):
        return self._t_process is not None

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

    def _install_agent(self, wheel_file, start):

        aip = self._aip()
        auuid = aip.install_agent(wheel_file)
        assert auuid is not None
        if start:
            self.logit('STARTING: {}'.format(wheel_file))
            status = self.start_agent(auuid)
            self.logit('STATUS NOW: {}'.format(status))
            assert status > 0

        return auuid

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

        for path, config, start in agent_configs:
            results = self.install_agent(agent_dir=path, config_file=config,
                                         start=start)

        return results

    def build_wheel(self, agent_dir, config=None):
        """ Build a wheel file.

        If config is not specified then the default config (in the agent's
        code directory) will be used.

        This function will build a wheel file in the volttron-home packaged
        directory.  If config is a  dictionary it will be converted to a file
        and used within the packaging process.  If it is a file it will be
        used directly.

        :return: string:
            - path to the created wheel file.
            - None if it was not able to create the file.
        """
        if not config:
            assert os.path.exists(os.path.join(agent_dir, "config"))
            config_file = os.path.join(agent_dir, "config")
        else:
            if isinstance(config, dict):
                from os.path import join, basename
                temp_config = join(self.volttron_home,
                                   basename(agent_dir) + "_config_file")
                with open(temp_config, "w") as fp:
                    fp.write(json.dumps(config))
                config_file = temp_config
        self.logit('Building agent package')
        wheel_file = self.build_agentpackage(agent_dir, config_file)
        return wheel_file

    def install_agent(self, agent_wheel=None, agent_dir=None, config_file=None,
        start=True):
        """Install and optionally start an agent on the platform.

            This function allows installation from an agent wheel or an
            agent directory (NOT BOTH).  If an agent_wheel is specified then
            it is assumed to be ready for installation (has a config file).
            If an agent_dir is specified then a config_file file must be
            specified or if it is not specified then it is assumed that the
            file agent_dir/config is to be used as the configuration file.  If
            none of these exist then an assertion error will be thrown.

            This function will return with a uuid of the installed agent.
        """

        assert self.is_running()
        assert agent_wheel or agent_dir

        if agent_wheel:
            assert not agent_dir
            assert not config_file
            assert os.path.exists(agent_wheel)
            wheel_file = agent_wheel

        if agent_dir:
            assert not agent_wheel
            if not config_file:
                assert os.path.exists(os.path.join(agent_dir, "config"))
                config_file = os.path.join(agent_dir, "config")
            else:
                if isinstance(config_file, dict):
                    from os.path import join, basename
                    temp_config=join(self.volttron_home, basename(agent_dir) + "_config_file")
                    with open(temp_config,"w") as fp:
                        fp.write(json.dumps(config_file))
                    config_file = temp_config
            self.logit('Building agent package')
            wheel_file = self.build_agentpackage(agent_dir, config_file)
            assert wheel_file

        agent_uuid = self._install_agent(wheel_file, start)

        assert agent_uuid is not None

        if start:
            assert self.is_agent_running(agent_uuid)
        gevent.sleep(1)
        return agent_uuid

    def start_agent(self, agent_uuid):
        self.logit('Starting agent {}'.format(agent_uuid))
        self.__control.call('start_agent', agent_uuid)
        status = self.agent_status(agent_uuid)
        if len(status) == 2:
            if status[1] is None:
                self._started_pids.append(status[0])
        # tuple with (pid, return status)
        return status
        # self.logit("VOLTTRONO_HOME SETTING: {}".format(
        #     self.env['VOLTTRON_HOME']))
        # cmd = ['volttron-ctl', 'start', agent_uuid]
        # p = Popen(cmd, env=self.env,
        #           stdout=sys.stdout, stderr=sys.stderr)
        # p.wait()
        #
        # # Confirm agent running
        # cmd = ['volttron-ctl', 'status', agent_uuid]
        # res = subprocess.check_output(cmd, env=self.env)
        # assert 'running' in res
        # pidpos = res.index('[') + 1
        # pidend = res.index(']')
        # pid = int(res[pidpos: pidend])
        #
        # self._started_pids.append(pid)
        # return int(pid)

    def stop_agent(self, agent_uuid):
        # Confirm agent running
        _log.debug("STOPPING AGENT: {}".format(agent_uuid))
        self.__control.call('stop_agent', agent_uuid)
        return self.agent_status(agent_uuid)
        # try:
        #     cmd = ['volttron-ctl', 'stop', agent_uuid]
        #     res = subprocess.check_output(cmd, env=self.env)
        # except CalledProcessError as ex:
        #     _log.error("Exception: {}".format(ex))
        # return self.agent_status(agent_uuid)

    def list_agents(self):
        return self.__control.call('list_agents')
        # aip = self._aip()
        # return aip.list_agents()

    def remove_agent(self, agent_uuid):
        """Remove the agent specified by agent_uuid"""
        _log.debug("REMOVING AGENT: {}".format(agent_uuid))
        self.__control.call('remove_agent', agent_uuid)
        return self.agent_status(agent_uuid)
        # try:
        #     cmd = ['volttron-ctl', 'remove', agent_uuid]
        #     res = subprocess.check_output(cmd, env=self.env)
        # except CalledProcessError as ex:
        #     _log.error("Exception: {}".format(ex))
        # return self.agent_status(agent_uuid)

    def is_agent_running(self, agent_uuid):
        return self.agent_status(agent_uuid) is not None

    def agent_status(self, agent_uuid):
        _log.debug("AGENT_STATUS: {}".format(agent_uuid))
        status = self.__control.call('agent_status', agent_uuid)
        if status == [None, None]:
            status = None
        return status
        # # Confirm agent running
        # cmd = ['volttron-ctl', 'status', agent_uuid]
        # pid = None
        # try:
        #     res = subprocess.check_output(cmd, env=self.env)
        #
        #     try:
        #         pidpos = res.index('[') + 1
        #         pidend = res.index(']')
        #         pid = int(res[pidpos: pidend])
        #     except:
        #         pid = None
        # except CalledProcessError as ex:
        #     _log.error("Exception: {}".format(ex))
        #
        # return pid

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
        while (not running and retries < max_retries):
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


    def shutdown_platform(self, cleanup=True):
        '''Stop platform here

           This function will shutdown the platform and attempt to kill any
           process that the platformwrapper has started.
        '''
        import signal
        self.logit('shutting down platform: PIDS: {}'.format(self._started_pids))
        while self._started_pids:
            pid = self._started_pids.pop()
            self.logit('ending pid: {}'.format(pid))
            try:
                os.kill(pid, signal.SIGTERM)
            except:
                self.logit('could not kill: {} '.format(pid))
        if self._p_process != None:
            try:
                gevent.sleep(0.2)
                self._p_process.terminate()
                gevent.sleep(0.2)
            except OSError:
                self.logit('Platform process was terminated.')
        else:
            self.logit("platform process was null")

        if self.use_twistd and self._t_process != None:
            self._t_process.kill()
            self._t_process.wait()
        elif self.use_twistd:
            self.logit("twistd process was null")

        self.logit('CLEANUP IS {} skipcleanup is {}'.format(cleanup,
                                                       self.skip_cleanup))
        if not self.skip_cleanup and cleanup:
            self.logit("Doing cleanup for {}".format(self.volttron_home))
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
