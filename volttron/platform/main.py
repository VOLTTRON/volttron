# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

from __future__ import print_function, absolute_import

import argparse
import errno
import logging
from logging import handlers
import logging.config
from urlparse import urlparse

import os
import resource
import stat
import struct
import sys
import threading
import uuid

import gevent
from gevent.fileobject import FileObject
import zmq
from zmq import green
# Create a context common to the green and non-green zmq modules.
green.Context._instance = green.Context.shadow(zmq.Context.instance().underlying)
from zmq.utils import jsonapi

from . import aip
from . import __version__
from . import config
from . import vip
from .vip.agent import Agent, Core
from .vip.agent.compat import CompatPubSub
from .vip.router import *
from .vip.socket import decode_key, encode_key, Address
from .vip.tracking import Tracker
from .auth import AuthService, AuthFile, AuthEntry
from .control import ControlService
from .web import MasterWebService
from .store import ConfigStoreService
from .agent import utils
from .agent.known_identities import MASTER_WEB
from .vip.agent.subsystems.pubsub import ProtectedPubSubTopics
from .keystore import KeyStore, KnownHostsStore

try:
    import volttron.restricted
except ImportError:
    HAVE_RESTRICTED = False
else:
    from volttron.restricted import resmon
    HAVE_RESTRICTED = True


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)


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
            import json
            try:
                conf_dict = json.load(conf_file)
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
        events = {value: name[6:] for name, value in vars(zmq).iteritems()
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
                 developer_mode=False):
        super(Router, self).__init__(
            context=context, default_user_id=default_user_id)
        self.local_address = Address(local_address)
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

            assert parsed.scheme in ('http', 'https', 'tcp'), \
                "volttron central address must begin with http(s) or tcp found"
            if parsed.scheme == 'tcp':
                assert volttron_central_serverkey, \
                    "volttron central serverkey must be set if address is tcp."
        self._volttron_central_serverkey = volttron_central_serverkey
        self._instance_name = instance_name
        self._bind_web_address = bind_web_address
        self._developer_mode = developer_mode

    def setup(self):
        sock = self.socket
        sock.identity = identity = str(uuid.uuid4())
        if self._monitor:
            Monitor(sock.get_monitor_socket()).start()
        sock.bind('inproc://vip')
        _log.debug('In-process VIP router bound to inproc://vip')
        sock.zap_domain = 'vip'
        addr = self.local_address
        if not addr.identity:
            addr.identity = identity
        if not addr.domain:
            addr.domain = 'vip'
        if not self._developer_mode:
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

    def handle_subsystem(self, frames, user_id):
        subsystem = bytes(frames[5])
        if subsystem == b'quit':
            sender = bytes(frames[0])
            if sender == b'control' and user_id == self.default_user_id:
                raise KeyboardInterrupt()
        elif subsystem == b'query':
            try:
                name = bytes(frames[6])
            except IndexError:
                value = None
            else:
                if name == b'addresses':
                    if self.addresses:
                        value = [addr.base for addr in self.addresses]
                    else:
                        value = [self.local_address.base]
                elif name == b'local_address':
                    value = self.local_address.base
                # Allow the agents to know the serverkey.
                elif name == b'serverkey':
                    if self._publickey is None:
                        return None
                    value = encode_key(self._publickey)
                elif name == b'volttron-central-address':
                    value = self._volttron_central_address
                elif name == b'volttron-central-serverkey':
                    value = self._volttron_central_serverkey
                elif name == b'instance-name':
                    value = self._instance_name
                elif name == b'bind-web-address':
                    value = self._bind_web_address
                else:
                    value = None
            frames[6:] = [b'', jsonapi.dumps(value)]
            frames[3] = b''
            return frames


class PubSubService(Agent):
    def __init__(self, protected_topics_file, *args, **kwargs):
        super(PubSubService, self).__init__(*args, **kwargs)
        self._protected_topics_file = os.path.abspath(protected_topics_file)

    @Core.receiver('onstart')
    def setup_agent(self, sender, **kwargs):
        self._read_protected_topics_file()
        self.core.spawn(utils.watch_file, self._protected_topics_file,
                        self._read_protected_topics_file)
        self.vip.pubsub.add_bus('')

    def _read_protected_topics_file(self):
        _log.info('loading protected-topics file %s',
                  self._protected_topics_file)
        try:
            utils.create_file_if_missing(self._protected_topics_file)
            with open(self._protected_topics_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                topics_data = jsonapi.loads(data) if data else {}
        except Exception:
            _log.exception('error loading %s', self._protected_topics_file)
        else:
            write_protect = topics_data.get('write-protect', [])
            topics = ProtectedPubSubTopics()
            try:
                for entry in write_protect:
                    topics.add(entry['topic'], entry['capabilities'])
            except KeyError:
                _log.exception('invalid format for protected topics '
                               'file {}'.format(self._protected_topics_file))
            else:
                self.vip.pubsub.protected_topics = topics
                _log.info('protected-topics file %s loaded',
                          self._protected_topics_file)


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
        error = configure_logging(opts.log_config)
        if error:
            parser.error('{}: {}'.format(*error))

    opts.publish_address = config.expandall(opts.publish_address)
    opts.subscribe_address = config.expandall(opts.subscribe_address)
    opts.vip_address = [config.expandall(addr) for addr in opts.vip_address]
    opts.vip_local_address = config.expandall(opts.vip_local_address)
    if opts.instance_name is None:
        if len(opts.vip_address) > 0:
            opts.instance_name = opts.vip_address[0]
    import urlparse
    if opts.bind_web_address:
        parsed = urlparse.urlparse(opts.bind_web_address)
        if parsed.scheme not in ('http', 'https'):
            raise StandardError(
                'bind-web-address must begin with http or https.')
        opts.bind_web_address = config.expandall(opts.bind_web_address)
    if opts.volttron_central_address:
        parsed = urlparse.urlparse(opts.volttron_central_address)
        if parsed.scheme not in ('http', 'https', 'tcp'):
            raise StandardError(
                'volttron-central-address must begin with tcp, http or https.')
        opts.volttron_central_address = config.expandall(
            opts.volttron_central_address)
    opts.volttron_central_serverkey = opts.volttron_central_serverkey
    if getattr(opts, 'show_config', False):
        print('volttron version: {}'.format(__version__))
        for name, value in sorted(vars(opts).iteritems()):
            print(name, repr(value))
        return

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
    if opts.developer_mode:
        secretkey = None
        publickey = None
        _log.warning('developer mode enabled; '
                     'authentication and encryption are disabled!')
    else:
        keystore = KeyStore()
        _log.debug('using key-store file %s', keystore.filename)
        if not keystore.isvalid():
            _log.warning('key store is invalid; connections may fail')
        st = os.stat(keystore.filename)
        if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            _log.warning('insecure mode on key file')
        publickey = decode_key(keystore.public())
        if publickey:
            _log.info('public key: %s', encode_key(publickey))
            # Authorize the platform key:
            entry = AuthEntry(credentials=encode_key(publickey),
                        user_id='platform',
                        comments='Automatically added by platform on start')
            AuthFile().add(entry)
            # Add platform key to known-hosts file:
            known_hosts = KnownHostsStore()
            known_hosts.add(opts.vip_local_address, encode_key(publickey))
            for addr in opts.vip_address:
                known_hosts.add(addr, encode_key(publickey))
        secretkey = decode_key(keystore.secret())

    # The following line doesn't appear to do anything, but it creates
    # a context common to the green and non-green zmq modules.
    zmq.Context.instance()   # DO NOT REMOVE LINE!!

    tracker = Tracker()
    # Main loops
    def router(stop):
        try:
            Router(opts.vip_local_address, opts.vip_address,
                   secretkey=secretkey, publickey=publickey,
                   default_user_id=b'vip.service', monitor=opts.monitor,
                   tracker=tracker,
                   volttron_central_address=opts.volttron_central_address,
                   volttron_central_serverkey=opts.volttron_central_serverkey,
                   instance_name=opts.instance_name,
                   bind_web_address=opts.bind_web_address,
                   developer_mode=opts.developer_mode).run()

        except Exception:
            _log.exception('Unhandled exception in router loop')
            raise
        finally:
            stop()

    address = 'inproc://vip'
    try:

        # Start the config store before auth so we may one day have auth use it.
        config_store = ConfigStoreService( address=address, identity='config.store')

        event = gevent.event.Event()
        config_store_task = gevent.spawn(config_store.core.run, event)
        event.wait()
        del event

        # Ensure auth service is running before router
        auth_file = os.path.join(opts.volttron_home, 'auth.json')
        auth = AuthService(
            auth_file, opts.aip, address=address, identity='auth',
            allow_any=opts.developer_mode, enable_store=False)

        event = gevent.event.Event()
        auth_task = gevent.spawn(auth.core.run, event)
        event.wait()
        del event

        # Start router in separate thread to remain responsive
        thread = threading.Thread(target=router, args=(auth.core.stop,))
        thread.daemon = True
        thread.start()

        gevent.sleep(0.1)
        if not thread.isAlive():
            sys.exit()

        protected_topics_file = os.path.join(opts.volttron_home, 'protected_topics.json')
        _log.debug('protected topics file %s', protected_topics_file)

        # Launch additional services and wait for them to start before
        # auto-starting agents
        services = [
            ControlService(opts.aip, address=address, identity='control',
                           tracker=tracker, heartbeat_autostart=True,
                           enable_store=False),
            PubSubService(protected_topics_file, address=address,
                          identity='pubsub', heartbeat_autostart=True,
                          enable_store=False),
            CompatPubSub(address=address, identity='pubsub.compat',
                         publish_address=opts.publish_address,
                         subscribe_address=opts.subscribe_address),
            MasterWebService(
                serverkey=publickey, identity=MASTER_WEB,
                address=address,
                bind_web_address=opts.bind_web_address,
                volttron_central_address=opts.volttron_central_address,
                aip=opts.aip, enable_store=False)
        ]
        events = [gevent.event.Event() for service in services]
        tasks = [gevent.spawn(service.core.run, event)
                 for service, event in zip(services, events)]
        tasks.append(config_store_task)
        tasks.append(auth_task)
        gevent.wait(events)
        del events

        # Auto-start agents now that all services are up
        if opts.autostart:
            for name, error in opts.aip.autostart():
                _log.error('error starting {!r}: {}\n'.format(name, error))
        # Wait for any service to stop, signaling exit
        try:
            gevent.wait(tasks, count=1)
        except KeyboardInterrupt:
            _log.info('SIGINT received; shutting down')
            sys.stderr.write('Shutting down.\n')
            for task in tasks:
                task.kill(block=False)
            gevent.wait(tasks)
    finally:
        opts.aip.finish()


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
        ignore_unknown=True, sections=[None, 'volttron'],
        help='read configuration from FILE')
    parser.add_argument(
        '--developer-mode', action='store_true',
        help='run in insecure developer mode')
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
    #parser.add_argument(
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
        '--volttron-central-address', default=None,
        help='The web address of a volttron central install instance.')
    agents.add_argument(
        '--volttron-central-serverkey', default=None,
        help='The serverkey of volttron central.')
    agents.add_argument(
        '--instance-name', default=None,
        help='The name of the instance that will be reported to '
             'VOLTTRON central.')

    # XXX: re-implement control options
    #on
    #control.add_argument(
    #    '--allow-root', action='store_true', inverse='--no-allow-root',
    #    help='allow root to connect to control socket')
    #control.add_argument(
    #    '--no-allow-root', action='store_false', dest='allow_root',
    #    help=argparse.SUPPRESS)
    #control.add_argument(
    #    '--allow-users', action='store_list', metavar='LIST',
    #    help='users allowed to connect to control socket')
    #control.add_argument(
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
        instace_name=None,
        # allow_root=False,
        # allow_users=None,
        # allow_groups=None,
        verify_agents=True,
        resource_monitor=True,
        # mobility=True,
        developer_mode=False,
    )

    # Parse and expand options
    args = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'SKIP_VOLTTRON_CONFIG' not in os.environ:
        args = ['--config', conf] + args
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
