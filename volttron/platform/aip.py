# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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

# pylint: disable=W0142
#}}}


'''Component for the instantiation and packaging of agents.'''


import contextlib
from fcntl import fcntl, F_GETFL, F_SETFL
import logging
import os
from os import O_NONBLOCK
import shlex
import shutil
import signal
import subprocess
from subprocess import PIPE
import sys
import syslog

import gevent
from gevent import select
import simplejson as jsonapi
from wheel.tool import unpack
import zmq

from . import messaging
from .messaging import topics

try:
    from volttron.restricted import auth
except ImportError:
    auth = None


_log = logging.getLogger(__name__)


def _split_prefix(a, b):
    a = a.split(os.path.sep)
    b = b.split(os.path.sep)
    common = []
    i = 0
    for i in range(min([len(a), len(b)])):
        if a[i] != b[i]:
            break
        common.append(a[i])
    del a[:i], b[:i]
    return os.path.join(*common), a, len(b)


def try_unlink(filename):
    try:
        os.unlink(filename)
    except Exception:
        pass


def open_exclusive(filename, *args):
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0644)
    try:
        return os.fdopen(fd, *args)
    except:
        os.close(fd)
        try_unlink(filename)
        raise


def copyfile(src, dst, exclusive=True):
    src_file = open(src, 'rb')
    dst_file = (open_exclusive if exclusive else open)(dst, 'wb')
    try:
        while True:
            buf = src_file.read(4096)
            if not buf:
                return
            dst_file.write(buf)
    except:
        try_unlink(dst)
        raise


def process_wait(p):
    timeout = 0.01
    while True:
        result = p.poll()
        if result is not None:
            return result
        gevent.sleep(timeout)
        if timeout < 0.5:
            timeout *= 2


def gevent_readlines(fd):
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK)
    data = []
    while True:
        select.select([fd], [], [])
        buf = fd.read(4096)
        if not buf:
            break
        parts = buf.split('\n')
        if len(parts) < 2:
            data.extend(parts)
        else:
            first, rest, data = (
                ''.join(data + parts[0:1]), parts[1:-1], parts[-1:])
            yield first
            for line in rest:
                yield line
    if any(data):
        yield ''.join(data)


_level_map = {syslog.LOG_DEBUG: logging.DEBUG,
              syslog.LOG_INFO: logging.INFO,
              syslog.LOG_NOTICE: logging.INFO,
              syslog.LOG_WARNING: logging.WARNING,
              syslog.LOG_ERR: logging.ERROR,
              syslog.LOG_CRIT: logging.CRITICAL,
              syslog.LOG_ALERT: logging.CRITICAL,
              syslog.LOG_EMERG: logging.CRITICAL,}

def _log_stream(name, agent, pid, level, stream):
    log = logging.getLogger(name)
    extra = {'processName': agent, 'process': pid}
    for line in stream:
        if line[0:1] == '{' and line[-1:] == '}':
            try:
                obj = jsonapi.loads(line)
                record = logging.makeLogRecord(obj)
            except Exception:
                pass
            else:
                record.remote_name, record.name = record.name, name
                record.__dict__.update(extra)
                log.handle(record)
                continue
        if line[0:1] == '<' and line[2:3] == '>' and line[1:2].isdigit():
            yield _level_map.get(int(line[1]), level), line[3:]
        else:
            yield level, line

def log_stream(name, agent, pid, path, stream):
    log = logging.getLogger(name)
    extra = {'processName': agent, 'process': pid}
    unset = {'thread': None, 'threadName': None, 'module': None}
    for level, line in stream:
        record = logging.LogRecord(name, level, path, 0, line, [], None)
        record.__dict__.update(extra)
        record.__dict__.update(unset)
        log.handle(record)


class ExecutionEnvironment(object):
    '''Environment reserved for agent execution.

    Deleting ExecutionEnvironment objects should cause the process to
    end and all resources to be returned to the system.
    '''
    def __init__(self):
        self.process = None

    def execute(self, *args, **kwargs):
        try:
            self.process = subprocess.Popen(*args, **kwargs)
        except OSError as e:
            if e.filename:
                raise
            raise OSError(*(e.args + (args[0],)))

    def __call__(self, *args, **kwargs):
        self.execute(*args, **kwargs)


class AIPplatform(object):
    '''Manages the main workflow of receiving and sending agents.'''

    def __init__(self, env, **kwargs):
        self.env = env
        self.agents = {}

    def setup(self):
        for path in [self.run_dir, self.config_dir,
                     self.install_dir, self.autostart_dir]:
            if not os.path.exists(path):
                os.makedirs(path, 0775)

    def finish(self):
        for exeenv in self.agents.itervalues():
            if exeenv.process.poll() is None:
                exeenv.process.send_signal(signal.SIGINT)
        for exeenv in self.agents.itervalues():
            if exeenv.process.poll() is None:
                exeenv.process.terminate()
        for exeenv in self.agents.itervalues():
            if exeenv.process.poll() is None:
                exeenv.process.kill()

    def _sub_socket(self):
        sock = messaging.Socket(zmq.SUB)
        sock.connect(self.env.subscribe_address)
        return sock

    def _pub_socket(self):
        sock = messaging.Socket(zmq.PUSH)
        sock.connect(self.env.publish_address)
        return sock

    def shutdown(self):
        with contextlib.closing(self._pub_socket()) as sock:
            sock.send_message(topics.PLATFORM_SHUTDOWN,
                              {'reason': 'Received shutdown command'},
                              flags=zmq.NOBLOCK)

    subscribe_address = property(lambda me: me.env.subscribe_address)
    publish_address = property(lambda me: me.env.publish_address)

    config_dir = property(lambda me: os.path.abspath(me.env.volttron_home))
    install_dir = property(lambda me: os.path.join(me.config_dir, 'agents'))
    autostart_dir = property(lambda me: os.path.join(me.config_dir, 'autostart'))
    run_dir = property(lambda me: os.path.join(me.config_dir, 'run'))

    def autostart(self):
        names = os.listdir(self.autostart_dir)
        names.sort()
        services, agents, errors = [], [], []
        for name in names:
            if name.endswith('.service'):
                services.append(name)
            else:
                agents.append(name)
        for name in services + agents:
            try:
                self.start_agent(name)
            except Exception as e:
                errors.append((name, str(e)))
        return errors

    def install_agent(self, agent_wheel):
        unpack(agent_wheel, dest=self.install_dir)

    def remove_agent(self, agent_name):
        if os.path.sep in agent_name:
            raise ValueError('invalid agent: {!r}'.format(agent_name))
        auto_path = os.path.join(self.autostart_dir, agent_name)
        if os.path.exists(auto_path):
            os.unlink(auto_path)
        agent_path = os.path.join(self.install_dir, agent_name)
        shutil.rmtree(agent_path)

    def list_agents(self):
        return os.listdir(self.install_dir)

    def status_agents(self):
        names = set(os.listdir(self.install_dir)) | set(self.agents.keys())
        return [(name, self.is_enabled(name), self.agent_status(name))
                for name in names]

    def is_enabled(self, agent_name):
        if os.path.sep in agent_name:
            return None
        return os.path.exists(os.path.join(self.autostart_dir, agent_name))

    def enable_agent(self, agent_name):
        if os.path.sep in agent_name:
            raise ValueError('invalid agent: {!r}'.format(agent_name))
        agent_dir = self.install_dir
        auto_dir = self.autostart_dir
        agent_abspath = os.path.join(agent_dir, agent_name)
        auto_path = os.path.join(auto_dir, agent_name)
        common_path, agent_rem, auto_len = _split_prefix(agent_dir, auto_dir)
        if auto_len < 5:
            agent_dir = os.path.join(*(['..'] * auto_len + agent_rem))
        agent_path = os.path.join(agent_dir, agent_name)
        os.symlink(agent_path, auto_path)

    def disable_agent(self, agent_name):
        if os.path.sep in agent_name:
            raise ValueError('invalid agent: {!r}'.format(agent_name))
        os.unlink(os.path.join(self.autostart_dir, agent_name))

    def _check_resources(self, resmon, agent_name, dist_info):
        execreqs_json = os.path.join(dist_info, 'execreqs.json')
        if not os.path.exists(execreqs_json):
            _log.warning('agent is missing execution requirements file: %s',
                       execreqs_json)
            execreqs = {}
        else:
            try:
                with open(execreqs_json) as file:
                    execreqs = jsonapi.load(file)
            except Exception as e:
                msg = 'error reading execution requirements: {}: {}'.format(
                       execreqs_json, e)
                _log.error(msg)
                raise ValueError(msg)
        hard_reqs = execreqs.get('hard_requirements', {})
        failed_terms = resmon.check_hard_resources(hard_reqs)
        if failed_terms:
            msg = '\n'.join('  {}: {} ({})'.format(
                             term, hard_reqs[term], avail)
                            for term, avail in failed_terms.iteritems())
            _log.error('hard resource requirements not met: %r: %s',
                       agent_name, msg)
            raise ValueError('hard resource requirements not met')
        requirements = execreqs.get('requirements', {})
        execenv, failed_terms = self.env.resmon.reserve_soft_resources(requirements)
        if execenv is None:
            msg = '\n'.join('  {}: {} ({})'.format(
                             term, requirements.get(term, '<unset>'), avail)
                            for term, avail in failed_terms.iteritems())
            _log.error('soft resource requirements not met for agent %r:\n%s',
                       agent_name, msg)
            raise ValueError('soft resource requirements not met')
        return execenv

    def _launch_agent(self, agent_path, name=None):
        if name is None:
            name = agent_path
        execenv = self.agents.get(name)
        if execenv:
            if execenv.process.poll() is None:
                _log.warning('request to start already running agent: ' + name)
                raise ValueError('agent is already running')
        basename = os.path.basename(agent_path)
        dist_info = os.path.join(agent_path, basename + '.dist-info')
        if not os.path.exists(dist_info):
            _log.error('missing required agent metadata: ' + dist_info)
            raise ValueError('missing required agent metadata')
        if auth is not None and self.env.verify_agents:
            auth.UnpackedPackageVerifier(dist_info).verify()
        metadata_json = os.path.join(dist_info, 'metadata.json')
        metadata = jsonapi.load(open(metadata_json))
        try:
            module = metadata['exports']['volttron.agent']['launch']
        except KeyError:
            try:
                module = metadata['exports']['setuptools.installation']['eggsecutable']
            except KeyError:
                _log.error('no agent launch class specified in package: ' + name)
                raise ValueError('no agent launch class specified in package')
        config = os.path.join(dist_info, 'config')
        if not os.path.exists(config):
            config = None
        environ = os.environ.copy()
        environ['PYTHONPATH'] = ':'.join([agent_path] + sys.path)
        environ['PATH'] = (os.path.abspath(os.path.dirname(sys.executable)) +
                           ':' + environ['PATH'])
        if config:
            environ['AGENT_CONFIG'] = config
        elif 'AGENT_CONFIG' in environ:
            del environ['AGENT_CONFIG']
        environ['AGENT_SUB_ADDR'] = self.subscribe_address
        environ['AGENT_PUB_ADDR'] = self.publish_address
        module, _, func = module.partition(':')
        if func:
            code = '__import__({0!r}, fromlist=[{1!r}]).{1}()'.format(module, func)
            argv = [sys.executable, '-c', code]
        else:
            argv = [sys.executable, '-m', module]
        if self.env.resmon is None:
            execenv = ExecutionEnvironment()
        else:
            execenv = self._check_resources(self.env.resmon, name, dist_info)
        _log.info('starting agent ' + name)
        execenv.execute(argv, cwd=self.run_dir, env=environ, close_fds=True,
                        stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
        self.agents[name] = execenv
        pid = execenv.process.pid
        _log.info('agent {} has PID {}'.format(name, pid))
        gevent.spawn(log_stream, 'agents.stderr', name, pid, argv[0],
                     _log_stream('agents.log', name, pid, logging.ERROR,
                                 gevent_readlines(execenv.process.stderr)))
        gevent.spawn(log_stream, 'agents.stdout', name, pid, argv[0],
                     ((logging.INFO, line) for line in
                      gevent_readlines(execenv.process.stdout)))

    def launch_agent(self, agent_config):
        self._launch_agent(os.path.abspath(agent_config))

    def agent_status(self, agent_name):
        execenv = self.agents.get(agent_name)
        return (execenv and execenv.process.pid,
                execenv and execenv.process.poll())

    def start_agent(self, agent_name):
        if os.path.sep in agent_name:
            raise ValueError('invalid agent: {!r}'.format(agent_name))
        self._launch_agent(
                os.path.join(self.install_dir, agent_name), agent_name)

    def stop_agent(self, agent_name):
        if '/' in agent_name:
            agent_name = os.path.abspath(agent_name)
        execenv = self.agents.get(agent_name)
        if not execenv:
            return
        if execenv.process.poll() is None:
            execenv.process.send_signal(signal.SIGINT)
            try:
                return gevent.with_timeout(3, process_wait, execenv.process)
            except gevent.Timeout:
                execenv.process.terminate()
            try:
                return gevent.with_timeout(3, process_wait, execenv.process)
            except gevent.Timeout:
                execenv.process.kill()
            try:
                return gevent.with_timeout(3, process_wait, execenv.process)
            except gevent.Timeout:
                raise ValueError('process is unresponsive')
        return execenv.process.poll()


def replace_macros(string, macros):
    '''Replace all occurances of %x style macros in string.

    macros should be a dictionary mapping single characters to string
    replacements.  '%' characters may be escaped using a double '%'.
    Macros not in the macros dictionary are replaced with an empty
    string.
    '''
    buf = []
    escape = None
    for c in string:
        if escape:
            if c != '%':
                c = macros.get(c, '')
            escape = None
        elif c == '%':
            escape = c
            continue
        buf.append(c)
    return ''.join(buf)


def parse_agent_args(exec_string, macros):
    '''Parse exec_string into argv and return, replacing macros.'''
    argv = shlex.split(exec_string)
    argv[1:] = [replace_macros(arg, macros) for arg in argv[1:]]
    return argv

