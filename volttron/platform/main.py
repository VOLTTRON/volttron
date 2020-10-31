# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


import argparse
import errno
import logging
from logging import handlers
import logging.config
from typing import Optional
from urllib.parse import urlparse

import os
import resource
import stat
import struct
import sys
import threading
import uuid

import gevent
import gevent.monkey

from volttron.platform.vip.healthservice import HealthService
from volttron.platform.vip.servicepeer import ServicePeerNotifier
from volttron.utils import get_random_key
from volttron.utils.frame_serialization import deserialize_frames, serialize_frames

gevent.monkey.patch_socket()
gevent.monkey.patch_ssl()
from gevent.fileobject import FileObject
import zmq
from zmq import ZMQError
from zmq import green
import subprocess

# Create a context common to the green and non-green zmq modules.
from volttron.platform.instance_setup import _update_config_file
from volttron.platform.agent.utils import get_platform_instance_name
green.Context._instance = green.Context.shadow(zmq.Context.instance().underlying)
from volttron.platform import jsonapi

from . import aip
from . import __version__
from . import config
from . import vip
from .vip.agent import Agent, Core
from .vip.router import *
from .vip.socket import decode_key, encode_key, Address
from .vip.tracking import Tracker
from .auth import AuthService, AuthFile, AuthEntry
from .control import ControlService
try:
    from .web import MasterWebService
    HAS_WEB = True
except ImportError:
    HAS_WEB = False
from .store import ConfigStoreService
from .agent import utils
from .agent.known_identities import MASTER_WEB, CONFIGURATION_STORE, AUTH, CONTROL, CONTROL_CONNECTION, PLATFORM_HEALTH, \
    KEY_DISCOVERY, PROXY_ROUTER
from .vip.agent.subsystems.pubsub import ProtectedPubSubTopics
from .keystore import KeyStore, KnownHostsStore
from .vip.pubsubservice import PubSubService
from .vip.routingservice import RoutingService
from .vip.externalrpcservice import ExternalRPCService
from .vip.keydiscovery import KeyDiscoveryAgent
from .vip.pubsubwrapper import PubSubWrapper
from ..utils.persistance import load_create_store
from .vip.rmq_router import RMQRouter
from volttron.platform.agent.utils import store_message_bus_config
from zmq import green as _green
from volttron.platform.vip.proxy_zmq_router import ZMQProxyRouter
from volttron.utils.rmq_setup import start_rabbit
from volttron.utils.rmq_config_params import RMQConfig

try:
    import volttron.restricted
except ImportError:
    HAVE_RESTRICTED = False
else:
    from volttron.restricted import resmon

    HAVE_RESTRICTED = True

_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)

# Only show debug on the platform when really necessary!
log_level_info = (
    'volttron.platform.main',
    'volttron.platform.vip.zmq_connection',
    'urllib3.connectionpool',
    'watchdog.observers.inotify_buffer',
    'volttron.platform.auth',
    'volttron.platform.store',
    'volttron.platform.control',
    'volttron.platform.vip.agent.core',
    'volttron.utils',
    'volttron.platform.vip.router'
)

for log_name in log_level_info:
    logging.getLogger(log_name).setLevel(logging.INFO)


VOLTTRON_INSTANCES = '~/.volttron_instances'


def log_to_file(file_, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file_)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter())
    root = logging.getLogger()
    if root.level < level:
        root.setLevel(level)
    root.addHandler(handler)


def configure_logging(conf_path):
    '''Load logging configuration from a file.

    Several formats are possible: ini, JSON, Python, and YAML. The ini
    format uses the standard Windows ini file format and is read in
    using logging.config.fileConfig(). The remaining formats will be
    read in according to the serialization format and the resulting
    dictionary will be passed to logging.config.dictConfig(). See the
    logging.config module for specifics on the two file and dict
    formats. Returns None on success, (path, exception) on error.

    The default format is ini. Other formats will be selected based on
    the file extension. Each format can be forced, regardless of file
    extension, by prepending the path with the format name followed by a
    colon:

      Examples:
        config.json        is loaded as JSON
        config.conf        is loaded as ini
        json:config.conf   is loaded as JSON

    YAML formatted configuration files require the PyYAML package.
    '''

    conf_format = 'ini'
    if conf_path.startswith('ini:'):
        conf_format, conf_path = 'ini', conf_path[4:]
    elif conf_path.startswith('json:'):
        conf_format, conf_path = 'json', conf_path[5:]
    elif conf_path.startswith('py:'):
        conf_format, conf_path = 'py', conf_path[3:]
    elif conf_path.startswith('yaml:'):
        conf_format, conf_path = 'yaml', conf_path[5:]
    elif conf_path.endswith('.json'):
        conf_format = 'json'
    elif conf_path.endswith('.py'):
        conf_format = 'py'
    elif conf_path.endswith('.yaml'):
        conf_format = 'yaml'

    if conf_format == 'ini':
        try:
            logging.config.fileConfig(conf_path)
        except (ValueError, TypeError, AttributeError, ImportError) as exc:
            return conf_path, exc
        return

    with open(conf_path) as conf_file:
        if conf_format == 'json':
            from volttron.platform import jsonapi
            try:
                conf_dict = jsonapi.load(conf_file)
            except ValueError as exc:
                return conf_path, exc
        elif conf_format == 'py':
            import ast
            try:
                conf_dict = ast.literal_eval(conf_file.read())
            except ValueError as exc:
                return conf_path, exc
        else:
            try:
                import yaml
            except ImportError:
                return (conf_path, 'PyYAML must be installed before '
                                   'loading logging configuration from a YAML file.')
            try:
                conf_dict = yaml.load(conf_file)
            except yaml.YAMLError as exc:
                return conf_path, exc
    try:
        logging.config.dictConfig(conf_dict)
    except (ValueError, TypeError, AttributeError, ImportError) as exc:
        return conf_path, exc


class LogLevelAction(argparse.Action):
    '''Action to set the log level of individual modules.'''

    def __call__(self, parser, namespace, values, option_string=None):
        for pair in values.split(','):
            if not pair.strip():
                continue
            try:
                logger_name, level_name = pair.rsplit(':', 1)
            except (ValueError, TypeError):
                raise argparse.ArgumentError(
                    self, 'invalid log level pair: {}'.format(values))
            try:
                level = int(level_name)
            except (ValueError, TypeError):
                try:
                    level = getattr(logging, level_name)
                except AttributeError:
                    raise argparse.ArgumentError(
                        self, 'invalid log level {!r}'.format(level_name))
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)


class Monitor(threading.Thread):
    '''Monitor thread to log connections.'''

    def __init__(self, sock):
        super(Monitor, self).__init__()
        self.daemon = True
        self.sock = sock

    def run(self):
        events = {value: name[6:] for name, value in vars(zmq).items()
                  if name.startswith('EVENT_') and name != 'EVENT_ALL'}
        log = logging.getLogger('vip.monitor')
        if log.level == logging.NOTSET:
            log.setLevel(logging.INFO)
        sock = self.sock
        while True:
            event, endpoint = sock.recv_multipart()
            event_id, event_value = struct.unpack('=HI', event)
            event_name = events[event_id]
            log.info('%s %s %s', event_name, event_value, endpoint)


class FramesFormatter(object):
    def __init__(self, frames):
        self.frames = frames

    def __repr__(self):
        return str([bytes(f) for f in self.frames])

    __str__ = __repr__


class Router(BaseRouter):
    '''Concrete VIP router.'''

    def __init__(self, local_address, addresses=(),
                 context=None, secretkey=None, publickey=None,
                 default_user_id=None, monitor=False, tracker=None,
                 volttron_central_address=None, instance_name=None,
                 bind_web_address=None, volttron_central_serverkey=None,
                 protected_topics={}, external_address_file='',
                 msgdebug=None, agent_monitor_frequency=600,
                 service_notifier=Optional[ServicePeerNotifier]):

        super(Router, self).__init__(
            context=context, default_user_id=default_user_id, service_notifier=service_notifier)
        self.local_address = Address(local_address)
        self._addr = addresses
        self.addresses = addresses = [Address(addr) for addr in set(addresses)]
        self._secretkey = secretkey
        self._publickey = publickey
        self.logger = logging.getLogger('vip.router')
        if self.logger.level == logging.NOTSET:
            self.logger.setLevel(logging.WARNING)
        self._monitor = monitor
        self._tracker = tracker
        self._volttron_central_address = volttron_central_address
        if self._volttron_central_address:
            parsed = urlparse(self._volttron_central_address)

            assert parsed.scheme in ('http', 'https', 'tcp', 'amqp'), \
                "volttron central address must begin with http(s) or tcp found"
            if parsed.scheme == 'tcp':
                assert volttron_central_serverkey, \
                    "volttron central serverkey must be set if address is tcp."
        self._volttron_central_serverkey = volttron_central_serverkey
        self._instance_name = instance_name
        self._bind_web_address = bind_web_address
        self._protected_topics = protected_topics
        self._external_address_file = external_address_file
        self._pubsub = None
        self.ext_rpc = None
        self._msgdebug = msgdebug
        self._message_debugger_socket = None
        self._instance_name = instance_name
        self._agent_monitor_frequency = agent_monitor_frequency

    def setup(self):
        sock = self.socket
        identity = str(uuid.uuid4())
        sock.identity = identity.encode("utf-8")
        _log.debug("ROUTER SOCK identity: {}".format(sock.identity))
        if self._monitor:
            Monitor(sock.get_monitor_socket()).start()
        sock.bind('inproc://vip')
        _log.debug('In-process VIP router bound to inproc://vip')
        sock.zap_domain = b'vip'
        addr = self.local_address
        if not addr.identity:
            addr.identity = identity
        if not addr.domain:
            addr.domain = 'vip'

        addr.server = 'CURVE'
        addr.secretkey = self._secretkey

        addr.bind(sock)
        _log.debug('Local VIP router bound to %s' % addr)
        for address in self.addresses:
            if not address.identity:
                address.identity = identity
            if (address.secretkey is None and
                        address.server not in ['NULL', 'PLAIN'] and
                    self._secretkey):
                address.server = 'CURVE'
                address.secretkey = self._secretkey
            if not address.domain:
                address.domain = 'vip'
            address.bind(sock)
            _log.debug('Additional VIP router bound to %s' % address)
        self._ext_routing = None

        self._ext_routing = RoutingService(self.socket, self.context,
                                           self._socket_class, self._poller,
                                           self._addr, self._instance_name)

        self.pubsub = PubSubService(self.socket,
                                    self._protected_topics,
                                    self._ext_routing)
        self.ext_rpc = ExternalRPCService(self.socket,
                                          self._ext_routing)
        self._poller.register(sock, zmq.POLLIN)
        _log.debug("ZMQ version: {}".format(zmq.zmq_version()))

    def issue(self, topic, frames, extra=None):
        log = self.logger.debug
        formatter = FramesFormatter(frames)
        if topic == ERROR:
            errnum, errmsg = extra
            log('%s (%s): %s', errmsg, errnum, formatter)
        elif topic == UNROUTABLE:
            log('unroutable: %s: %s', extra, formatter)
        else:
            log('%s: %s',
                ('incoming' if topic == INCOMING else 'outgoing'), formatter)
        if self._tracker:
            self._tracker.hit(topic, frames, extra)
        if self._msgdebug:
            if not self._message_debugger_socket:
                # Initialize a ZMQ IPC socket on which to publish all messages to MessageDebuggerAgent.
                socket_path = os.path.expandvars('$VOLTTRON_HOME/run/messagedebug')
                socket_path = os.path.expanduser(socket_path)
                socket_path = 'ipc://{}'.format('@' if sys.platform.startswith('linux') else '') + socket_path
                self._message_debugger_socket = zmq.Context().socket(zmq.PUB)
                self._message_debugger_socket.connect(socket_path)
            # Publish the routed message, including the "topic" (status/direction), for use by MessageDebuggerAgent.
            frame_bytes = [topic]
            frame_bytes.extend(frames)  # [frame if type(frame) is bytes else frame.bytes for frame in frames])
            frame_bytes = serialize_frames(frames)
            # TODO we need to fix the msgdebugger socket if we need it to be connected
            #frame_bytes = [f.bytes for f in frame_bytes]
            #self._message_debugger_socket.send_pyobj(frame_bytes)
    # This is currently not being used e.g once fixed we won't use it.
    #def extract_bytes(self, frame_bytes):
    #    result = []
    #    for f in frame_bytes:
    #        if isinstance(f, list):
    #            result.extend(self.extract_bytes(f))
    #        else:
    #            result.append(f.bytes)
    #    return result

    def handle_subsystem(self, frames, user_id):
        _log.debug(f"Handling subsystem with frames: {frames} user_id: {user_id}")

        subsystem = frames[5]
        if subsystem == 'quit':
            sender = frames[0]
            # was if sender == 'control' and user_id == self.default_user_id:
            # now we serialize frames and if user_id is always the sender and not
            # recipents.get('User-Id') or default user name
            if sender == 'control':
                if self._ext_routing:
                    self._ext_routing.close_external_connections()
                self.stop()
                raise KeyboardInterrupt()
            else:
                _log.error(f"Sender {sender} not authorized to shutdown platform")
        elif subsystem =='agentstop':
            try:
                drop = frames[6]
                self._drop_peer(drop)
                self._drop_pubsub_peers(drop)
                if self._service_notifier:
                    self._service_notifier.peer_dropped(drop)

                _log.debug("ROUTER received agent stop message. dropping peer: {}".format(drop))
            except IndexError:
                _log.error(f"agentstop called but unable to determine agent from frames sent {frames}")
            return False
        elif subsystem == 'query':
            try:
                name = frames[6]
            except IndexError:
                value = None
            else:
                if name == 'addresses':
                    if self.addresses:
                        value = [addr.base for addr in self.addresses]
                    else:
                        value = [self.local_address.base]
                elif name == 'local_address':
                    value = self.local_address.base
                # Allow the agents to know the serverkey.
                elif name == 'serverkey':
                    keystore = KeyStore()
                    value = keystore.public
                elif name == 'volttron-central-address':
                    value = self._volttron_central_address
                elif name == 'volttron-central-serverkey':
                    value = self._volttron_central_serverkey
                elif name == 'instance-name':
                    value = self._instance_name
                elif name == 'bind-web-address':
                    value = self._bind_web_address
                elif name == 'platform-version':
                    value = __version__
                elif name == 'message-bus':
                    value = os.environ.get('MESSAGEBUS', 'zmq')
                elif name == 'agent-monitor-frequency':
                    value = self._agent_monitor_frequency
                else:
                    value = None
            frames[6:] = ['', value]
            frames[3] = ''
            
            return frames
        elif subsystem == 'pubsub':
            result = self.pubsub.handle_subsystem(frames, user_id)
            return result
        elif subsystem == 'routing_table':
            result = self._ext_routing.handle_subsystem(frames)
            return result
        elif subsystem == 'external_rpc':
            result = self.ext_rpc.handle_subsystem(frames)
            return result

    def _drop_pubsub_peers(self, peer):
        self.pubsub.peer_drop(peer)

    def _add_pubsub_peers(self, peer):
        self.pubsub.peer_add(peer)

    def poll_sockets(self):
        """
        Poll for incoming messages through router socket or other external socket connections
        """
        try:
            sockets = dict(self._poller.poll())
        except ZMQError as ex:
            _log.error("ZMQ Error while polling: {}".format(ex))

        for sock in sockets:
            if sock == self.socket:
                if sockets[sock] == zmq.POLLIN:
                    frames = sock.recv_multipart(copy=False)
                    self.route(deserialize_frames(frames))
            elif sock in self._ext_routing._vip_sockets:
                if sockets[sock] == zmq.POLLIN:
                    # _log.debug("From Ext Socket: ")
                    self.ext_route(sock)
            elif sock in self._ext_routing._monitor_sockets:
                self._ext_routing.handle_monitor_event(sock)
            else:
                # _log.debug("External ")
                frames = sock.recv_multipart(copy=False)

    def ext_route(self, socket):
        """
        Handler function for message received through external socket connection
        :param socket: socket affected files: {}
        :return:
        """
        # Expecting incoming frames to follow this VIP format:
        #   [SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]
        frames = socket.recv_multipart(copy=False)
        self.route(deserialize_frames(frames))
        # for f in frames:
        #     _log.debug("PUBSUBSERVICE Frames: {}".format(bytes(f)))
        if len(frames) < 6:
            return

        sender, proto, user_id, msg_id, subsystem = frames[:5]
        if proto != 'VIP1':
            return

        # Handle 'EXT_RPC' subsystem messages
        name = subsystem
        if name == 'external_rpc':
            # Reframe the frames
            sender, proto, usr_id, msg_id, subsystem, msg = frames[:6]
            msg_data = jsonapi.loads(msg)
            peer = msg_data['to_peer']
            # Send to destionation agent/peer
            # Form new frame for local
            frames[:9] = [peer, sender, proto, usr_id, msg_id, 'external_rpc', msg]
            try:
                self.socket.send_multipart(frames, flags=NOBLOCK, copy=False)
            except ZMQError as ex:
                _log.debug("ZMQ error: {}".format(ex))
                pass
        # Handle 'pubsub' subsystem messages
        elif name == 'pubsub':
            if frames[1] == 'VIP1':
                recipient = ''
                frames[:1] = ['', '']
                # for f in frames:
                #     _log.debug("frames: {}".format(bytes(f)))
            result = self.pubsub.handle_subsystem(frames, user_id)
            return result
        # Handle 'routing_table' subsystem messages
        elif name == 'routing_table':
            # for f in frames:
            #     _log.debug("frames: {}".format(bytes(f)))
            if frames[1] == 'VIP1':
                frames[:1] = ['', '']
            result = self._ext_routing.handle_subsystem(frames)
            return result


class GreenRouter(Router):
    """
    Greenlet friendly Router
    """

    def __init__(self, local_address, addresses=(),
                 context=None, secretkey=None, publickey=None,
                 default_user_id=None, monitor=False, tracker=None,
                 volttron_central_address=None, instance_name=None,
                 bind_web_address=None, volttron_central_serverkey=None,
                 protected_topics={}, external_address_file='',
                 msgdebug=None, volttron_central_rmq_address=None,
                 service_notifier=Optional[ServicePeerNotifier]):
        self._context_class = _green.Context
        self._socket_class = _green.Socket
        self._poller_class = _green.Poller
        super(GreenRouter, self).__init__(
            local_address, addresses=addresses,
            context=context, secretkey=secretkey, publickey=publickey,
            default_user_id=default_user_id, monitor=monitor, tracker=tracker,
            volttron_central_address=volttron_central_address, instance_name=instance_name,
            bind_web_address=bind_web_address, volttron_central_serverkey=volttron_central_address,
            protected_topics=protected_topics, external_address_file=external_address_file,
            msgdebug=msgdebug, service_notifier=service_notifier)

    def start(self):
        '''Create the socket and call setup().

        The socket is save in the socket attribute. The setup() method
        is called at the end of the method to perform additional setup.
        '''
        self.socket = sock = self._socket_class(self.context, zmq.ROUTER)
        sock.router_mandatory = True
        sock.tcp_keepalive = True
        sock.tcp_keepalive_idle = 180
        sock.tcp_keepalive_intvl = 20
        sock.tcp_keepalive_cnt = 6
        sock.set_hwm(6000)
        self.setup()


def start_volttron_process(opts):
    '''Start the main volttron process.

    Typically this function is used from main.py and just uses the argparser's
    Options arguments as inputs.   It also can be called with a dictionary.  In
    that case the dictionaries keys are mapped into a value that acts like the
    args options.
    '''
    if isinstance(opts, dict):
        opts = type('Options', (), opts)()
        # vip_address is meant to be a list so make it so.
        if not isinstance(opts.vip_address, list):
            opts.vip_address = [opts.vip_address]
    if opts.log:
        opts.log = config.expandall(opts.log)
    if opts.log_config:
        opts.log_config = config.expandall(opts.log_config)

    # Configure logging
    level = max(1, opts.verboseness)
    if opts.monitor and level > logging.INFO:
        level = logging.INFO

    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(opts.log, level, handler_class=handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())

    if opts.log_config:
        with open(opts.log_config, 'r') as f:
            for line in f.readlines():
                _log.info(line.rstrip())

        error = configure_logging(opts.log_config)

        if error:
            _log.error('{}: {}'.format(*error))
            sys.exit(1)

    if opts.secure_agent_users == "True":
        _log.info("VOLTTRON starting in secure mode")
        os.umask(0o007)
    else:
        opts.secure_agent_users = 'False'

    opts.publish_address = config.expandall(opts.publish_address)
    opts.subscribe_address = config.expandall(opts.subscribe_address)
    opts.vip_address = [config.expandall(addr) for addr in opts.vip_address]
    opts.vip_local_address = config.expandall(opts.vip_local_address)
    opts.message_bus = config.expandall(opts.message_bus)
    if opts.web_ssl_key:
        opts.web_ssl_key = config.expandall(opts.web_ssl_key)
    if opts.web_ssl_cert:
        opts.web_ssl_cert = config.expandall(opts.web_ssl_cert)

    if opts.web_ssl_key and not opts.web_ssl_cert:
        raise Exception("If web-ssl-key is specified web-ssl-cert MUST be specified.")
    if opts.web_ssl_cert and not opts.web_ssl_key:
        raise Exception("If web-ssl-cert is specified web-ssl-key MUST be specified.")

    if opts.web_ca_cert:
        assert os.path.isfile(opts.web_ca_cert), "web_ca_cert does not exist!"
        os.environ['REQUESTS_CA_BUNDLE'] = opts.web_ca_cert

    # Removed the check for opts.web_ca_cert to be the same cert that was used to create web_ssl_key
    # and opts.web_ssl_cert

    os.environ['MESSAGEBUS'] = opts.message_bus
    os.environ['SECURE_AGENT_USER'] = opts.secure_agent_users
    if opts.instance_name is None:
        if len(opts.vip_address) > 0:
            opts.instance_name = opts.vip_address[0]

    _log.debug("opts.instancename {}".format(opts.instance_name))
    if opts.instance_name:
        store_message_bus_config(opts.message_bus, opts.instance_name)
    else:
        # if there is no instance_name given get_platform_instance_name will
        # try to retrieve from config or default a value and store it in the config
        get_platform_instance_name(vhome=opts.volttron_home, prompt=False)

    if opts.bind_web_address:
        parsed = urlparse(opts.bind_web_address)
        if parsed.scheme not in ('http', 'https'):
            raise Exception(
                'bind-web-address must begin with http or https.')
        opts.bind_web_address = config.expandall(opts.bind_web_address)
        # zmq with tls is supported
        if opts.message_bus == 'zmq' and parsed.scheme == 'https':
            if not opts.web_ssl_key or not opts.web_ssl_cert:
                raise Exception("zmq https requires a web-ssl-key and a web-ssl-cert file.")
            if not os.path.isfile(opts.web_ssl_key) or not os.path.isfile(opts.web_ssl_cert):
                raise Exception("zmq https requires a web-ssl-key and a web-ssl-cert file.")
        # zmq without tls is supported through the use of a secret key, if it's None then
        # we want to generate a secret key and set it in the config file.
        elif opts.message_bus == 'zmq' and opts.web_secret_key is None:
            opts.web_secret_key = get_random_key()
            _update_config_file(web_secret_key = opts.web_secret_key)

    if opts.volttron_central_address:
        parsed = urlparse(opts.volttron_central_address)
        if parsed.scheme not in ('http', 'https', 'tcp', 'amqp', 'amqps'):
            raise Exception(
                'volttron-central-address must begin with tcp, amqp, amqps, http or https.')
        opts.volttron_central_address = config.expandall(
            opts.volttron_central_address)
    opts.volttron_central_serverkey = opts.volttron_central_serverkey

    # Log configuration options
    if getattr(opts, 'show_config', False):
        _log.info('volttron version: {}'.format(__version__))
        for name, value in sorted(vars(opts).items()):
            _log.info("%s: %s" % (name, str(repr(value))))

    # Increase open files resource limit to max or 8192 if unlimited
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)

    except OSError:
        _log.exception('error getting open file limits')
    else:
        if soft != hard and soft != resource.RLIM_INFINITY:
            try:
                limit = 8192 if hard == resource.RLIM_INFINITY else hard
                resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
            except OSError:
                _log.exception('error setting open file limits')
            else:
                _log.debug('open file resource limit increased from %d to %d',
                           soft, limit)
        _log.debug('open file resource limit %d to %d',
                   soft, hard)
    # Set configuration
    if HAVE_RESTRICTED:
        if opts.verify_agents:
            _log.info('Agent integrity verification enabled')
        if opts.resource_monitor:
            _log.info('Resource monitor enabled')
            opts.resmon = resmon.ResourceMonitor()
    opts.aip = aip.AIPplatform(opts)
    opts.aip.setup()

    # Check for secure mode/permissions on VOLTTRON_HOME directory
    mode = os.stat(opts.volttron_home).st_mode
    if mode & (stat.S_IWGRP | stat.S_IWOTH):
        _log.warning('insecure mode on directory: %s', opts.volttron_home)
    # Get or generate encryption key
    keystore = KeyStore()
    _log.debug('using key-store file %s', keystore.filename)
    if not keystore.isvalid():
        _log.warning('key store is invalid; connections may fail')
    st = os.stat(keystore.filename)
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        _log.warning('insecure mode on key file')
    publickey = decode_key(keystore.public)
    if publickey:
        # Authorize the platform key:
        entry = AuthEntry(credentials=encode_key(publickey),
                          user_id='platform',
                          capabilities=[{'edit_config_store': {'identity': '/.*/'}}],
                          comments='Automatically added by platform on start')
        AuthFile().add(entry, overwrite=True)
        # Add platform key to known-hosts file:
        known_hosts = KnownHostsStore()
        known_hosts.add(opts.vip_local_address, encode_key(publickey))
        for addr in opts.vip_address:
            known_hosts.add(addr, encode_key(publickey))
    secretkey = decode_key(keystore.secret)

    # Add the control.connection so that volttron-ctl can access the bus
    control_conn_path = KeyStore.get_agent_keystore_path(CONTROL_CONNECTION)
    os.makedirs(os.path.dirname(control_conn_path), exist_ok=True)
    ks_control_conn = KeyStore(KeyStore.get_agent_keystore_path(CONTROL_CONNECTION))
    entry = AuthEntry(credentials=encode_key(decode_key(ks_control_conn.public)),
                      user_id=CONTROL_CONNECTION,
                      capabilities=[{'edit_config_store': {'identity': '/.*/'}}],
                      comments='Automatically added by platform on start')
    AuthFile().add(entry, overwrite=True)

    # The following line doesn't appear to do anything, but it creates
    # a context common to the green and non-green zmq modules.
    zmq.Context.instance()  # DO NOT REMOVE LINE!!
    # zmq.Context.instance().set(zmq.MAX_SOCKETS, 2046)

    tracker = Tracker()
    protected_topics_file = os.path.join(opts.volttron_home, 'protected_topics.json')
    _log.debug('protected topics file %s', protected_topics_file)
    external_address_file = os.path.join(opts.volttron_home, 'external_address.json')
    _log.debug('external_address_file file %s', external_address_file)
    protected_topics = {}
    if opts.agent_monitor_frequency:
        try:
            int(opts.agent_monitor_frequency)
        except ValueError as e:
            raise ValueError("agent-monitor-frequency should be integer "
                             "value. Units - seconds. This determines how "
                             "often the platform checks for any crashed agent "
                             "and attempts to restart. {}".format(e))

    # Allows registration agents to callbacks for peers
    notifier = ServicePeerNotifier()

    # Main loops
    def zmq_router(stop):
        try:
            _log.debug("Running zmq router")
            Router(opts.vip_local_address, opts.vip_address,
                   secretkey=secretkey, publickey=publickey,
                   default_user_id='vip.service', monitor=opts.monitor,
                   tracker=tracker,
                   volttron_central_address=opts.volttron_central_address,
                   volttron_central_serverkey=opts.volttron_central_serverkey,
                   instance_name=opts.instance_name,
                   bind_web_address=opts.bind_web_address,
                   protected_topics=protected_topics,
                   external_address_file=external_address_file,
                   msgdebug=opts.msgdebug,
                   service_notifier=notifier).run()
        except Exception:
            _log.exception('Unhandled exception in router loop')
            raise
        except KeyboardInterrupt:
            pass
        finally:
            _log.debug("In finally")
            stop(platform_shutdown=True)

    # RMQ router
    def rmq_router(stop):
        try:
            RMQRouter(opts.vip_address, opts.vip_local_address, opts.instance_name, opts.vip_address,
                      volttron_central_address=opts.volttron_central_address,
                      volttron_central_serverkey=opts.volttron_central_serverkey,
                      bind_web_address=opts.bind_web_address,
                      service_notifier=notifier
                      ).run()
        except Exception:
            _log.exception('Unhandled exception in rmq router loop')
        except KeyboardInterrupt:
            pass
        finally:
            _log.debug("In RMQ router finally")
            stop(platform_shutdown=True)

    address = 'inproc://vip'
    pid_file = os.path.join(opts.volttron_home, "VOLTTRON_PID")
    try:

        stop_event = None

        auth_task = None
        protected_topics = {}
        config_store_task = None
        proxy_router = None
        proxy_router_task = None

        _log.debug("********************************************************************")
        _log.debug("VOLTTRON PLATFORM RUNNING ON {} MESSAGEBUS".format(opts.message_bus))
        _log.debug("********************************************************************")
        if opts.message_bus == 'zmq':
            # Start the config store before auth so we may one day have auth use it.
            config_store = ConfigStoreService(address=address,
                                              identity=CONFIGURATION_STORE,
                                              message_bus=opts.message_bus)

            event = gevent.event.Event()
            config_store_task = gevent.spawn(config_store.core.run, event)
            event.wait()
            del event

            # Ensure auth service is running before router
            auth_file = os.path.join(opts.volttron_home, 'auth.json')
            auth = AuthService(
                auth_file, protected_topics_file, opts.setup_mode,
                opts.aip, address=address, identity=AUTH,
                enable_store=False, message_bus='zmq')

            event = gevent.event.Event()
            auth_task = gevent.spawn(auth.core.run, event)
            event.wait()
            del event

            protected_topics = auth.get_protected_topics()
            _log.debug("MAIN: protected topics content {}".format(protected_topics))
            # Start ZMQ router in separate thread to remain responsive
            thread = threading.Thread(target=zmq_router, args=(config_store.core.stop,))
            thread.daemon = True
            thread.start()

            gevent.sleep(0.1)
            if not thread.isAlive():
                sys.exit()
        else:
            # Start RabbitMQ server if not running
            rmq_config = RMQConfig()
            if rmq_config is None:
                _log.error("DEBUG: Exiting due to error in rabbitmq config file. Please check.")
                sys.exit()

            try:
                start_rabbit(rmq_config.rmq_home)
            except AttributeError as exc:
                _log.error("Exception while starting RabbitMQ. Check the path in the config file.")
                sys.exit()
            except subprocess.CalledProcessError as exc:
                _log.error("Unable to start rabbitmq server. "
                           "Check rabbitmq log for errors")
                sys.exit()

            # Start the config store before auth so we may one day have auth use it.
            config_store = ConfigStoreService(address=address,
                                              identity=CONFIGURATION_STORE,
                                              message_bus=opts.message_bus)

            thread = threading.Thread(target=rmq_router, args=(config_store.core.stop,))
            thread.daemon = True
            thread.start()

            gevent.sleep(0.1)
            if not thread.isAlive():
                sys.exit()

            gevent.sleep(1)
            event = gevent.event.Event()
            config_store_task = gevent.spawn(config_store.core.run, event)
            event.wait()
            del event

            # Ensure auth service is running before router
            auth_file = os.path.join(opts.volttron_home, 'auth.json')
            auth = AuthService(auth_file, protected_topics_file,
                               opts.setup_mode, opts.aip,
                               address=address, identity=AUTH,
                               enable_store=False, message_bus='rmq')

            event = gevent.event.Event()
            auth_task = gevent.spawn(auth.core.run, event)
            event.wait()
            del event

            protected_topics = auth.get_protected_topics()

            # Spawn Greenlet friendly ZMQ router
            # Necessary for backward compatibility with ZMQ message bus
            green_router = GreenRouter(opts.vip_local_address, opts.vip_address,
                                       secretkey=secretkey, publickey=publickey,
                                       default_user_id='vip.service', monitor=opts.monitor,
                                       tracker=tracker,
                                       volttron_central_address=opts.volttron_central_address,
                                       volttron_central_serverkey=opts.volttron_central_serverkey,
                                       instance_name=opts.instance_name,
                                       bind_web_address=opts.bind_web_address,
                                       protected_topics=protected_topics,
                                       external_address_file=external_address_file,
                                       msgdebug=opts.msgdebug,
                                       service_notifier=notifier)

            proxy_router = ZMQProxyRouter(address=address,
                                          identity=PROXY_ROUTER,
                                          zmq_router=green_router,
                                          message_bus=opts.message_bus)
            event = gevent.event.Event()
            proxy_router_task = gevent.spawn(proxy_router.core.run, event)
            event.wait()
            del event

        # The instance file is where we are going to record the instance and
        # its details according to
        instance_file = os.path.expanduser(VOLTTRON_INSTANCES)
        try:
            instances = load_create_store(instance_file)
        except ValueError:
            os.remove(instance_file)
            instances = load_create_store(instance_file)
        this_instance = instances.get(opts.volttron_home, {})
        this_instance['pid'] = os.getpid()
        this_instance['version'] = __version__
        # note vip_address is a list
        this_instance['vip-address'] = opts.vip_address
        this_instance['volttron-home'] = opts.volttron_home
        this_instance['volttron-root'] = os.path.abspath('../..')
        this_instance['start-args'] = sys.argv[1:]
        instances[opts.volttron_home] = this_instance
        instances.async_sync()

        protected_topics_file = os.path.join(opts.volttron_home, 'protected_topics.json')
        _log.debug('protected topics file %s', protected_topics_file)
        external_address_file = os.path.join(opts.volttron_home, 'external_address.json')
        _log.debug('external_address_file file %s', external_address_file)

        # Launch additional services and wait for them to start before
        # auto-starting agents
        services = [
            ControlService(opts.aip, address=address, identity=CONTROL,
                           tracker=tracker, heartbeat_autostart=True,
                           enable_store=False, enable_channel=True,
                           message_bus=opts.message_bus,
                           agent_monitor_frequency=opts.agent_monitor_frequency),

            KeyDiscoveryAgent(address=address, serverkey=publickey,
                              identity=KEY_DISCOVERY,
                              external_address_config=external_address_file,
                              setup_mode=opts.setup_mode,
                              bind_web_address=opts.bind_web_address,
                              enable_store=False,
                              message_bus='zmq'),
            # For Backward compatibility with VOLTTRON versions <= 4.1
            PubSubWrapper(address=address,
                          identity='pubsub', heartbeat_autostart=True,
                          enable_store=False,
                          message_bus='zmq')
        ]

        entry = AuthEntry(credentials=services[0].core.publickey,
                          user_id=CONTROL,
                          capabilities=[{'edit_config_store': {'identity': '/.*/'}}],
                          comments='Automatically added by platform on start')
        AuthFile().add(entry, overwrite=True)

        # Begin the webserver based options here.
        if opts.bind_web_address is not None:
            if not HAS_WEB:
                sys.stderr.write("Web libraries not installed, but bind web address specified\n")
                sys.stderr.write("Please install web libraries using python3 bootstrap.py --web\n")
                sys.exit(-1)

            if opts.instance_name is None:
                _update_config_file()

            if opts.message_bus == 'rmq':
                if opts.web_ssl_key is None or opts.web_ssl_cert is None or \
                        (not os.path.isfile(opts.web_ssl_key) and not os.path.isfile(opts.web_ssl_cert)):
                    # This is different than the master.web cert which is used for the agent to connect
                    # to rmq server.  The master.web-server certificate will be used for the master web
                    # services.
                    base_webserver_name = MASTER_WEB + "-server"
                    from volttron.platform.certs import Certs
                    certs = Certs()
                    certs.create_signed_cert_files(base_webserver_name, cert_type='server')
                    opts.web_ssl_key = certs.private_key_file(base_webserver_name)
                    opts.web_ssl_cert = certs.cert_file(base_webserver_name)

            _log.info("Starting master web service")
            services.append(MasterWebService(
                serverkey=publickey, identity=MASTER_WEB,
                address=address,
                bind_web_address=opts.bind_web_address,
                volttron_central_address=opts.volttron_central_address,
                enable_store=False,
                message_bus=opts.message_bus,
                volttron_central_rmq_address=opts.volttron_central_rmq_address,
                web_ssl_key=opts.web_ssl_key,
                web_ssl_cert=opts.web_ssl_cert,
                web_secret_key=opts.web_secret_key
            ))

        ks_masterweb = KeyStore(KeyStore.get_agent_keystore_path(MASTER_WEB))
        entry = AuthEntry(credentials=encode_key(decode_key(ks_masterweb.public)),
                          user_id=MASTER_WEB,
                          capabilities=['allow_auth_modifications'],
                          comments='Automatically added by platform on start')
        AuthFile().add(entry, overwrite=True)

        # # MASTER_WEB did not work on RMQ. Referred to agent as master
        # # Added this auth to allow RPC calls for credential authentication
        # # when using the RMQ messagebus.
        # ks_masterweb = KeyStore(KeyStore.get_agent_keystore_path('master'))
        # entry = AuthEntry(credentials=encode_key(decode_key(ks_masterweb.public)),
        #                   user_id='master',
        #                   capabilities=['allow_auth_modifications'],
        #                   comments='Automatically added by platform on start')
        # AuthFile().add(entry, overwrite=True)

        health_service = HealthService(address=address,
                                       identity=PLATFORM_HEALTH, heartbeat_autostart=True,
                                       enable_store=False,
                                       message_bus=opts.message_bus)
        notifier.register_peer_callback(health_service.peer_added, health_service.peer_dropped)
        services.append(health_service)
        events = [gevent.event.Event() for service in services]
        tasks = [gevent.spawn(service.core.run, event)
                 for service, event in zip(services, events)]
        tasks.append(config_store_task)
        tasks.append(auth_task)
        if stop_event:
            tasks.append(stop_event)
        gevent.wait(events)
        del events

        # Auto-start agents now that all services are up
        if opts.autostart:
            for name, error in opts.aip.autostart():
                _log.error('error starting {!r}: {}\n'.format(name, error))

        # Done with all start up process write a PID file

        with open(pid_file, 'w+') as f:
            f.write(str(os.getpid()))

        # Wait for any service to stop, signaling exit
        try:
            gevent.wait(tasks, count=1)
        except KeyboardInterrupt:
            _log.info('SIGINT received; shutting down')
        finally:
            sys.stderr.write('Shutting down.\n')
            if proxy_router_task:
                proxy_router.core.stop()
            _log.debug("Kill all service agent tasks")
            for task in tasks:
                task.kill(block=False)
            gevent.wait(tasks)
    except Exception as e:
        _log.error(e)
        import traceback
        _log.error(traceback.print_exc())
    finally:
        _log.debug("AIP finally")
        opts.aip.finish()
        instance_file = os.path.expanduser(VOLTTRON_INSTANCES)
        try:
            instances = load_create_store(instance_file)
            instances.pop(opts.volttron_home, None)
            instances.sync()
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            _log.warn("Unable to load {}".format(VOLTTRON_INSTANCES))
        _log.debug("********************************************************************")
        _log.debug("VOLTTRON PLATFORM HAS SHUTDOWN")
        _log.debug("********************************************************************")


def main(argv=sys.argv):
    # Refuse to run as root
    if not getattr(os, 'getuid', lambda: -1)():
        sys.stderr.write('%s: error: refusing to run as root to prevent '
                         'potential damage.\n' % os.path.basename(argv[0]))
        sys.exit(77)

    volttron_home = os.path.normpath(config.expandall(
        os.environ.get('VOLTTRON_HOME', '~/.volttron')))
    os.environ['VOLTTRON_HOME'] = volttron_home
    # Setup option parser
    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]), add_help=False,
        description='VOLTTRON platform service',
        usage='%(prog)s [OPTION]...',
        argument_default=argparse.SUPPRESS,
        epilog='Boolean options, which take no argument, may be inversed by '
               'prefixing the option with no- (e.g. --autostart may be '
               'inversed using --no-autostart).'
    )
    parser.add_argument(
        '-c', '--config', metavar='FILE', action='parse_config',
        ignore_unknown=False, sections=[None, 'volttron'],
        help='read configuration from FILE')
    parser.add_argument(
        '-l', '--log', metavar='FILE', default=None,
        help='send log output to FILE instead of stderr')
    parser.add_argument(
        '-L', '--log-config', metavar='FILE',
        help='read logging configuration from FILE')
    parser.add_argument(
        '--log-level', metavar='LOGGER:LEVEL', action=LogLevelAction,
        help='override default logger logging level')
    parser.add_argument(
        '--monitor', action='store_true',
        help='monitor and log connections (implies -v)')
    parser.add_argument(
        '-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument(
        '-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument(
        '--verboseness', type=int, metavar='LEVEL', default=logging.WARNING,
        help='set logger verboseness')
    # parser.add_argument(
    #    '--volttron-home', env_var='VOLTTRON_HOME', metavar='PATH',
    #    help='VOLTTRON configuration directory')
    parser.add_argument(
        '--show-config', action='store_true',
        help=argparse.SUPPRESS)
    parser.add_help_argument()
    parser.add_version_argument(version='%(prog)s ' + __version__)

    agents = parser.add_argument_group('agent options')
    agents.add_argument(
        '--autostart', action='store_true', inverse='--no-autostart',
        help='automatically start enabled agents and services')
    agents.add_argument(
        '--no-autostart', action='store_false', dest='autostart',
        help=argparse.SUPPRESS)
    agents.add_argument(
        '--publish-address', metavar='ZMQADDR',
        help='ZeroMQ URL used for pre-3.x agent publishing (deprecated)')
    agents.add_argument(
        '--subscribe-address', metavar='ZMQADDR',
        help='ZeroMQ URL used for pre-3.x agent subscriptions (deprecated)')
    agents.add_argument(
        '--vip-address', metavar='ZMQADDR', action='append', default=[],
        help='ZeroMQ URL to bind for VIP connections')
    agents.add_argument(
        '--vip-local-address', metavar='ZMQADDR',
        help='ZeroMQ URL to bind for local agent VIP connections')
    agents.add_argument(
        '--bind-web-address', metavar='BINDWEBADDR', default=None,
        help='Bind a web server to the specified ip:port passed')
    agents.add_argument(
        '--web-ca-cert', metavar='CAFILE', default=None,
        help='If using self-signed certificates, this variable will be set globally to allow requests'
             'to be able to correctly reach the webserver without having to specify verify in all calls.'
    )
    agents.add_argument(
        "--web-secret-key", default=None,
        help="Secret key to be used instead of https based authentication."
    )
    agents.add_argument(
        '--web-ssl-key', metavar='KEYFILE', default=None,
        help='ssl key file for using https with the volttron server'
    )
    agents.add_argument(
        '--web-ssl-cert', metavar='CERTFILE', default=None,
        help='ssl certficate file for using https with the volttron server'
    )
    agents.add_argument(
        '--volttron-central-address', default=None,
        help='The web address of a volttron central install instance.')
    agents.add_argument(
        '--volttron-central-serverkey', default=None,
        help='The serverkey of volttron central.')
    agents.add_argument(
        '--instance-name', default=None,
        help='The name of the instance that will be reported to '
             'VOLTTRON central.')
    agents.add_argument(
        '--msgdebug', action='store_true',
        help='Route all messages to an agent while debugging.')
    agents.add_argument(
        '--setup-mode', action='store_true',
        help='Setup mode flag for setting up authorization of external platforms.')
    parser.add_argument(
        '--message-bus', action='store', default='zmq', dest='message_bus',
        help='set message to be used. valid values are zmq and rmq')
    agents.add_argument(
        '--volttron-central-rmq-address', default=None,
        help='The AMQP address of a volttron central install instance')
    agents.add_argument(
        '--agent-monitor-frequency', default=600,
        help='How often should the platform check for crashed agents and '
             'attempt to restart. Units=seconds. Default=600')
    agents.add_argument(
        '--secure-agent-users', default=False,
        help='Require that agents run with their own users (this requires '
             'running scripts/secure_user_permissions.sh as sudo)')

    # XXX: re-implement control options
    # on
    # control.add_argument(
    #    '--allow-root', action='store_true', inverse='--no-allow-root',
    #    help='allow root to connect to control socket')
    # control.add_argument(
    #    '--no-allow-root', action='store_false', dest='allow_root',
    #    help=argparse.SUPPRESS)
    # control.add_argument(
    #    '--allow-users', action='store_list', metavar='LIST',
    #    help='users allowed to connect to control socket')
    # control.add_argument(
    #    '--allow-groups', action='store_list', metavar='LIST',
    #    help='user groups allowed to connect to control socket')

    if HAVE_RESTRICTED:
        class RestrictedAction(argparse.Action):
            def __init__(self, option_strings, dest,
                         const=True, help=None, **kwargs):
                super(RestrictedAction, self).__init__(
                    option_strings, dest=argparse.SUPPRESS, nargs=0,
                    const=const, help=help)

            def __call__(self, parser, namespace, values, option_string=None):
                namespace.verify_agents = self.const
                namespace.resource_monitor = self.const
                # namespace.mobility = self.const

        restrict = parser.add_argument_group('restricted options')
        restrict.add_argument(
            '--restricted', action=RestrictedAction, inverse='--no-restricted',
            help='shortcut to enable all restricted features')
        restrict.add_argument(
            '--no-restricted', action=RestrictedAction, const=False,
            help=argparse.SUPPRESS)
        restrict.add_argument(
            '--verify', action='store_true', inverse='--no-verify',
            help='verify agent integrity before execution')
        restrict.add_argument(
            '--no-verify', action='store_false', dest='verify_agents',
            help=argparse.SUPPRESS)
        restrict.add_argument(
            '--resource-monitor', action='store_true',
            inverse='--no-resource-monitor',
            help='enable agent resource management')
        restrict.add_argument(
            '--no-resource-monitor', action='store_false',
            dest='resource_monitor', help=argparse.SUPPRESS)
        # restrict.add_argument(
        #    '--mobility', action='store_true', inverse='--no-mobility',
        #    help='enable agent mobility')
        # restrict.add_argument(
        #    '--no-mobility', action='store_false', dest='mobility',
        #    help=argparse.SUPPRESS)

    ipc = 'ipc://%s$VOLTTRON_HOME/run/' % (
        '@' if sys.platform.startswith('linux') else '')
    parser.set_defaults(
        log=None,
        log_config=None,
        monitor=False,
        verboseness=logging.WARNING,
        volttron_home=volttron_home,
        autostart=True,
        publish_address=ipc + 'publish',
        subscribe_address=ipc + 'subscribe',
        vip_address=[],
        vip_local_address=ipc + 'vip.socket',
        # This is used to start the web server from the web module.
        bind_web_address=None,
        # Used to contact volttron central when registering volttron central
        # platform agent.
        volttron_central_address=None,
        volttron_central_serverkey=None,
        instance_name=None,
        # allow_root=False,
        # allow_users=None,
        # allow_groups=None,
        verify_agents=True,
        resource_monitor=True,
        # mobility=True,
        msgdebug=None,
        setup_mode=False,
        # Type of underlying message bus to use - ZeroMQ or RabbitMQ
        message_bus='zmq',
        # Volttron Central in AMQP address format is needed if running on RabbitMQ message bus
        volttron_central_rmq_address=None,
        web_ssl_key=None,
        web_ssl_cert=None,
        web_ca_cert=None,
        # If we aren't using ssl then we need a secret key available for us to use.
        web_secret_key=None
    )

    # Parse and expand options
    args = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'SKIP_VOLTTRON_CONFIG' not in os.environ:
        # command line args get preference over same args in config file
        args = args + ['--config', conf]
    logging.getLogger().setLevel(logging.NOTSET)
    opts = parser.parse_args(args)
    start_volttron_process(opts)


def _main():
    """ Entry point for scripts."""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    _main()
