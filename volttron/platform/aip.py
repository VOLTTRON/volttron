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
import errno
from fcntl import fcntl, F_GETFL, F_SETFL
import logging
import os
from os import O_NONBLOCK
import shutil
import signal
import subprocess
from subprocess import PIPE
import sys
import syslog
import uuid

import gevent
from gevent import select
import simplejson as jsonapi
from wheel.tool import unpack
import zmq

from . import messaging
from .messaging import topics
from .packages import UnpackedPackage

try:
    from volttron.restricted import auth
    from volttron.restricted import certs
    from volttron.restricted.resmon import ResourceError
except ImportError:
    auth = None


_log = logging.getLogger(__name__)


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


class IgnoreErrno(object):
    ignore = []
    def __init__(self, errno, *more):
        self.ignore = [errno]
        self.ignore.extend(more)
    def __enter__(self):
        return
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return exc_value.errno in self.ignore
        except AttributeError:
            pass

ignore_enoent = IgnoreErrno(errno.ENOENT)


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
        for path in [self.run_dir, self.config_dir, self.install_dir]:
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
    run_dir = property(lambda me: os.path.join(me.config_dir, 'run'))

    def autostart(self):
        agents, errors = [], []
        for agent_uuid, agent_name in self.list_agents().iteritems():
            try:
                priority = self._agent_priority(agent_uuid)
            except EnvironmentError as exc:
                errors.append((agent_uuid, str(exc)))
                continue
            if priority is not None:
                agents.append((priority, agent_uuid))
        agents.sort(reverse=True)
        for _, agent_uuid in agents:
            try:
                self.start_agent(agent_uuid)
            except Exception as exc:
                errors.append((agent_uuid, str(exc)))
        return errors

    def land_agent(self, agent_wheel):
        if auth is None:
            raise NotImplementedError()
        agent_uuid = self.install_agent(agent_wheel)
        try:
            self.start_agent(agent_uuid)
            self.prioritize_agent(agent_uuid)
        except:
            self.remove_agent(agent_uuid)
            raise
        return agent_uuid

    def install_agent(self, agent_wheel):
        while True:
            agent_uuid = str(uuid.uuid4())
            if agent_uuid in self.agents:
                continue
            agent_path = os.path.join(self.install_dir, agent_uuid)
            try:
                os.mkdir(agent_path)
                break
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
        try:
            if auth is not None and self.env.verify_agents:
                unpacker = auth.VolttronPackageWheelFile(agent_wheel, certsobj=certs.Certs())
                unpacker.unpack(dest=agent_path)
            else:
                unpack(agent_wheel, dest=agent_path)
        except Exception:
            shutil.rmtree(agent_path)
            raise
        return agent_uuid

    def remove_agent(self, agent_uuid):
        if agent_uuid not in os.listdir(self.install_dir):
            raise ValueError('invalid agent')
        self.stop_agent(agent_uuid)
        self.agents.pop(agent_uuid, None)
        shutil.rmtree(os.path.join(self.install_dir, agent_uuid))

    def agent_name(self, agent_uuid):
        agent_path = os.path.join(self.install_dir, agent_uuid)
        for agent_name in os.listdir(agent_path):
            dist_info = os.path.join(
                agent_path, agent_name, agent_name + '.dist-info')
            if os.path.exists(dist_info):
                return agent_name
        raise KeyError(agent_uuid)

    def list_agents(self):
        agents = {}
        for agent_uuid in os.listdir(self.install_dir):
            try:
                agents[agent_uuid] = self.agent_name(agent_uuid)
            except KeyError:
                pass
        return agents

    def active_agents(self):
        return {agent_uuid: execenv.name
                for agent_uuid, execenv in self.agents.iteritems()}

    def clear_status(self, clear_all=False):
        remove = []
        for agent_uuid, execenv in self.agents.iteritems():
            if execenv.process.poll() is not None:
                if clear_all:
                    remove.append(agent_uuid)
                else:
                    path = os.path.join(self.install_dir, agent_uuid)
                    if not os.path.exists(path):
                        remove.append(agent_uuid)
        for agent_uuid in remove:
            self.agents.pop(agent_uuid, None)

    def status_agents(self):
        return [(agent_uuid, agent_name, self.agent_status(agent_uuid))
                for agent_uuid, agent_name in self.active_agents().iteritems()]

    def tag_agent(self, agent_uuid, tag):
        tag_file = os.path.join(self.install_dir, agent_uuid, 'TAG')
        if not tag:
            with ignore_enoent:
                os.unlink(tag_file)
        else:
            with open(tag_file, 'w') as file:
                file.write(tag[:64])

    def agent_tag(self, agent_uuid):
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        tag_file = os.path.join(self.install_dir, agent_uuid, 'TAG')
        with ignore_enoent, open(tag_file, 'r') as file:
            return file.readline(64)

    def _agent_priority(self, agent_uuid):
        autostart = os.path.join(self.install_dir, agent_uuid, 'AUTOSTART')
        with ignore_enoent, open(autostart) as file:
            return file.readline(100).strip()

    def agent_priority(self, agent_uuid):
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        return self._agent_priority(agent_uuid)

    def prioritize_agent(self, agent_uuid, priority='50'):
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        autostart = os.path.join(self.install_dir, agent_uuid, 'AUTOSTART')
        if priority is None:
            with ignore_enoent:
                os.unlink(autostart)
        else:
            with open(autostart, 'w') as file:
                file.write(priority.strip())

    def _check_resources(self, resmon, execreqs, reserve=False):
        hard_reqs = execreqs.get('hard_requirements', {})
        failed_terms = resmon.check_hard_resources(hard_reqs)
        if failed_terms:
            msg = '\n'.join('  {}: {} ({})'.format(
                             term, hard_reqs[term], avail)
                            for term, avail in failed_terms.iteritems())
            _log.error('hard resource requirements not met:\n%s', msg)
            raise ValueError('hard resource requirements not met')
        requirements = execreqs.get('requirements', {})
        try:
            if reserve:
                return resmon.reserve_soft_resources(requirements)
            else:
                failed_terms = resmon.check_soft_resources(requirements)
                if failed_terms:
                    errmsg = 'soft resource requirements not met'
                else:
                    return
        except ResourceError as exc:
            errmsg, failed_terms = exc.args
        msg = '\n'.join('  {}: {} ({})'.format(
                         term, requirements.get(term, '<unset>'), avail)
                        for term, avail in failed_terms.iteritems())
        _log.error('%s:\n%s', errmsg, msg)
        raise ValueError(errmsg)

    def check_resources(self, execreqs):
        resmon = getattr(self.env, 'resmon', None)
        if resmon:
            return self._check_resources(resmon, execreqs, reserve=False)

    def _reserve_resources(self, resmon, execreqs):
        return self._check_resources(resmon, execreqs, reserve=True)

    def get_execreqs(self, agent_uuid):
        name = self.agent_name(agent_uuid)
        pkg = UnpackedPackage(os.path.join(self.install_dir, agent_uuid, name))
        return self._read_execreqs(pkg.distinfo)

    def _read_execreqs(self, dist_info):
        execreqs_json = os.path.join(dist_info, 'execreqs.json')
        try:
            with ignore_enoent, open(execreqs_json) as file:
                return jsonapi.load(file)
        except Exception as exc:
            msg = 'error reading execution requirements: {}: {}'.format(
                   execreqs_json, exc)
            _log.error(msg)
            raise ValueError(msg)
        _log.warning('missing execution requirements: %s', execreqs_json)
        return {}

    def _launch_agent(self, agent_uuid, agent_path, name=None):
        execenv = self.agents.get(agent_uuid)
        if execenv and execenv.process.poll() is None:
            _log.warning('request to start already running agent %s', agent_path)
            raise ValueError('agent is already running')

        pkg = UnpackedPackage(agent_path)
        if auth is not None and self.env.verify_agents:
            auth.UnpackedPackageVerifier(pkg.distinfo).verify()
        metadata = pkg.metadata
        try:
            exports = metadata['extensions']['python.exports']
        except KeyError:
            try:
                exports = metadata['exports']
            except KeyError:
                raise ValueError('no entry points exported')
        try:
            module = exports['volttron.agent']['launch']
        except KeyError:
            try:
                module = exports['setuptools.installation']['eggsecutable']
            except KeyError:
                _log.error('no agent launch class specified in package %s', agent_path)
                raise ValueError('no agent launch class specified in package')
        config = os.path.join(pkg.distinfo, 'config')
        tag = self.agent_tag(agent_uuid)

        environ = os.environ.copy()
        environ['PYTHONPATH'] = ':'.join([agent_path] + sys.path)
        environ['PATH'] = (os.path.abspath(os.path.dirname(sys.executable)) +
                           ':' + environ['PATH'])
        if os.path.exists(config):
            environ['AGENT_CONFIG'] = config
        else:
            environ.pop('AGENT_CONFIG', None)
        if tag:
            environ['AGENT_TAG'] = tag
        else:
            environ.pop('AGENT_TAG', None)
        environ['AGENT_SUB_ADDR'] = self.subscribe_address
        environ['AGENT_PUB_ADDR'] = self.publish_address
        environ['AGENT_UUID'] = agent_uuid

        module, _, func = module.partition(':')
        if func:
            code = '__import__({0!r}, fromlist=[{1!r}]).{1}()'.format(module, func)
            argv = [sys.executable, '-c', code]
        else:
            argv = [sys.executable, '-m', module]
        resmon = getattr(self.env, 'resmon', None)
        if resmon is None:
            execenv = ExecutionEnvironment()
        else:
            execreqs = self._read_execreqs(pkg.distinfo)
            execenv = self._reserve_resources(resmon, execreqs)
        execenv.name = name or agent_path
        _log.info('starting agent %s', agent_path)
        data_dir = os.path.join(os.path.dirname(pkg.distinfo),
                                '{}.agent-data'.format(pkg.package_name))
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        execenv.execute(argv, cwd=data_dir, env=environ, close_fds=True,
                        stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
        self.agents[agent_uuid] = execenv
        pid = execenv.process.pid
        _log.info('agent %s has PID %s', agent_path, pid)
        gevent.spawn(log_stream, 'agents.stderr', name, pid, argv[0],
                     _log_stream('agents.log', name, pid, logging.ERROR,
                                 gevent_readlines(execenv.process.stderr)))
        gevent.spawn(log_stream, 'agents.stdout', name, pid, argv[0],
                     ((logging.INFO, line) for line in
                      gevent_readlines(execenv.process.stdout)))

    def launch_agent(self, agent_path):
        while True:
            agent_uuid = str(uuid.uuid4())
            if not (agent_uuid in self.agents or
                    os.path.exists(os.path.join(self.install_dir, agent_uuid))):
                break
        if not os.path.exists(agent_path):
            msg = 'agent not found: {}'.format(agent_path)
            _log.error(msg)
            raise ValueError(msg)
        self._launch_agent(agent_uuid, os.path.abspath(agent_path))

    def agent_status(self, agent_uuid):
        execenv = self.agents.get(agent_uuid)
        if execenv is None:
            return (None, None)
        return (execenv.process.pid, execenv.process.poll())

    def start_agent(self, agent_uuid):
        name = self.agent_name(agent_uuid)
        self._launch_agent(
            agent_uuid, os.path.join(self.install_dir, agent_uuid, name), name)

    def stop_agent(self, agent_uuid):
        try:
            execenv = self.agents[agent_uuid]
        except KeyError:
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
