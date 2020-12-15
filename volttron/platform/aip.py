# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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


"""Component for the instantiation and packaging of agents."""

import errno
import grp
import logging
import os
import pwd
import shutil
import signal
import sys
import uuid

import requests
import gevent
import gevent.event
from gevent import subprocess
from gevent.subprocess import PIPE
from wheel.tool import unpack

from volttron.platform import certs
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.agent.utils import get_fq_identity, is_secure_mode
# Can't use zmq.utils.jsonapi because it is missing the load() method.
from volttron.platform import jsonapi
from volttron.platform.certs import Certs
from volttron.platform.keystore import KeyStore

from .agent.utils import (is_valid_identity,
                          get_messagebus,
                          get_platform_instance_name)
from volttron.platform import get_home
from volttron.platform.agent.utils import load_platform_config, \
    get_utc_seconds_from_epoch
from .packages import UnpackedPackage
from .vip.agent import Agent
from .auth import AuthFile, AuthEntry, AuthFileEntryAlreadyExists
from volttron.utils.rmq_mgmt import RabbitMQMgmt

try:
    from volttron.restricted import auth
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


# LOG_* constants from syslog module (not available on Windows)
_level_map = {7: logging.DEBUG,  # LOG_DEBUG
              6: logging.INFO,  # LOG_INFO
              5: logging.INFO,  # LOG_NOTICE
              4: logging.WARNING,  # LOG_WARNING
              3: logging.ERROR,  # LOG_ERR
              2: logging.CRITICAL,  # LOG_CRIT
              1: logging.CRITICAL,  # LOG_ALERT
              0: logging.CRITICAL, }  # LOG_EMERG


def log_entries(name, agent, pid, level, stream):
    log = logging.getLogger(name)
    extra = {'processName': agent, 'process': pid}
    for l in stream:
        for line in l.splitlines():
            if line.startswith('{') and line.endswith('}'):
                try:
                    obj = jsonapi.loads(line)
                    try:
                        obj['args'] = tuple(obj['args'])
                    except (KeyError, TypeError, ValueError):
                        pass
                    record = logging.makeLogRecord(obj)
                except Exception:
                    pass
                else:
                    if record.name in log.manager.loggerDict:
                        if not logging.getLogger(
                                record.name).isEnabledFor(record.levelno):
                            continue
                    elif not log.isEnabledFor(record.levelno):
                        continue
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
        if log.isEnabledFor(level):
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
        self.env = None

    def execute(self, *args, **kwargs):
        try:
            self.env = kwargs.get('env', None)
            self.process = subprocess.Popen(*args, **kwargs, universal_newlines=True)
        except OSError as e:
            if e.filename:
                raise
            raise OSError(*(e.args + (args[0],)))

    def stop(self):
        if self.process.poll() is None:
            # pylint: disable=catching-non-exception
            self.process.send_signal(signal.SIGINT)
            try:
                return gevent.with_timeout(60, process_wait, self.process)
            except gevent.Timeout:
                _log.warn("First timeout")
                self.process.terminate()
            try:
                return gevent.with_timeout(30, process_wait, self.process)
            except gevent.Timeout:
                _log.warn("2nd timeout")
                self.process.kill()
            try:
                return gevent.with_timeout(30, process_wait, self.process)
            except gevent.Timeout:
                _log.error("last timeout")
                raise ValueError('process is unresponsive')
        return self.process.poll()

    def __call__(self, *args, **kwargs):
        self.execute(*args, **kwargs)


class SecureExecutionEnvironment(object):

    def __init__(self, agent_user):
        self.process = None
        self.env = None
        self.agent_user = agent_user

    def execute(self, *args, **kwargs):
        try:
            self.env = kwargs.get('env', None)
            run_as_user = ['sudo', '-E', '-u', self.agent_user]
            run_as_user.extend(*args)
            _log.debug(run_as_user)
            self.process = subprocess.Popen(run_as_user, universal_newlines=True, **kwargs)
        except OSError as e:
            if e.filename:
                raise
            raise OSError(*(e.args + (args[0],)))

    def stop(self):
        if self.process.poll() is None:
            cmd = ["sudo", "scripts/secure_stop_agent.sh", self.agent_user, str(self.process.pid)]
            _log.debug("In aip secureexecutionenv {}".format(cmd))
            process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            _log.info("stopping agent: stdout {} stderr: {}".format(stdout, stderr))
            if process.returncode != 0:
                _log.error("Exception stopping agent: stdout {} stderr: {}".format(stdout, stderr))
                raise RuntimeError("Exception stopping agent: stdout {} stderr: {}".format(stdout, stderr))
        return self.process.poll()

    def __call__(self, *args, **kwargs):
        self.execute(*args, **kwargs)


class AIPplatform(object):
    """Manages the main workflow of receiving and sending agents."""

    def __init__(self, env, **kwargs):
        self.env = env
        self.agents = {}
        self.secure_agent_user = is_secure_mode()
        self.message_bus = get_messagebus()
        if self.message_bus == 'rmq':
            self.rmq_mgmt = RabbitMQMgmt()
        self.instance_name = get_platform_instance_name()

    def add_agent_user_group(self):
        user = pwd.getpwuid(os.getuid())
        group_name = "volttron_{}".format(self.instance_name)
        try:
            group = grp.getgrnam(group_name)
        except KeyError:
            _log.info("Creating the volttron agent group {}.".format(
                group_name))
            groupadd = ['sudo', 'groupadd', group_name]
            groupadd_process = subprocess.Popen(
                groupadd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = groupadd_process.communicate()
            if groupadd_process.returncode != 0:
                # TODO alert?
                raise RuntimeError("Add {} group failed ({}) - Prevent "
                                   "creation of agent users".
                                   format(stderr, group_name))
            group = grp.getgrnam(group_name)

    def add_agent_user(self, agent_name, agent_dir):
        """
        Invokes sudo to create a unique unix user for the agent.
        :param agent_name:
        :param agent_dir:
        :return:
        """

        # Ensure the agent users unix group exists
        self.add_agent_user_group()

        # Create a USER_ID file, truncating existing USER_ID files which
        # should at this point be considered unsafe
        user_id_path = os.path.join(agent_dir, "USER_ID")

        with open(user_id_path, "w+") as user_id_file:
            volttron_agent_user = "volttron_{}".format(
                str(get_utc_seconds_from_epoch()).replace(".", ""))
            _log.info("Creating volttron user {}".format(volttron_agent_user))
            group = "volttron_{}".format(self.instance_name)
            useradd = ['sudo', 'useradd', volttron_agent_user, '-r', '-G', group]
            useradd_process = subprocess.Popen(
                useradd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = useradd_process.communicate()
            if useradd_process.returncode != 0:
                # TODO alert?
                raise RuntimeError("Creating {} user failed: {}".format(
                    volttron_agent_user, stderr))
            user_id_file.write(volttron_agent_user)
        return volttron_agent_user

    def set_acl_for_path(self, perms, user, path):
        """
        Sets the file access control list setting for a given user/directory
        :param perms:
        :param user:
        :param directory:
        :return:
        """
        acl_perms = "user:{user}:{perms}".format(user=user, perms=perms)
        permissions_command = ['setfacl', '-m', acl_perms, path]
        _log.debug("PERMISSIONS COMMAND {}".format(permissions_command))
        permissions_process = subprocess.Popen(
            permissions_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = permissions_process.communicate()
        if permissions_process.returncode != 0:
            _log.error("Set {} permissions on {}, stdout: {}".format(
                perms, path, stdout))
            # TODO alert?
            raise RuntimeError("Setting {} permissions on {} failed: {}".format(
                perms, path, stderr))

    def set_agent_user_permissions(self, volttron_agent_user,
                                   agent_uuid, agent_dir):
        name = self.agent_name(agent_uuid)
        agent_path_with_name = os.path.join(agent_dir, name)
        # Directories in the install path have read/execute
        # except agent-data dir. agent-data dir has rwx
        self.set_acl_for_path("rx", volttron_agent_user, agent_dir)
        # creates dir if it doesn't exist
        data_dir = self._get_agent_data_dir(agent_path_with_name)

        for (root, directories, files) in os.walk(agent_dir, topdown=True):
            for directory in directories:
                if directory == os.path.basename(data_dir):
                    self.set_acl_for_path("rwx", volttron_agent_user,
                                          os.path.join(root, directory))
                else:
                    self.set_acl_for_path("rx", volttron_agent_user,
                                          os.path.join(root, directory))
        # In install directory, make all files' permissions to 400.
        # Then do setfacl -m "r" to only agent user
        self._set_agent_dir_file_permissions(agent_dir, volttron_agent_user, data_dir)

        # if messagebus is rmq.
        # TODO: For now provide read access to all agents since this is used for
        #  multi instance connections. This will not be requirement in
        #  VOLTTRON 8.0 once CSR is implemented for
        #  federation and shovel. The below lines can be removed then
        if self.message_bus == 'rmq':
            os.chmod(os.path.join(get_home(), "certificates/private"), 0o755)
            self.set_acl_for_path("r", volttron_agent_user,
                                  os.path.join(get_home(), "certificates/private", self.instance_name + "-admin.pem"))

    def _set_agent_dir_file_permissions(self, input_dir, agent_user, data_dir):
        """ Recursively change permissions to all files in given directrory to 400 but for files in
            agent-data directory
        """
        for (root, directories, files) in os.walk(input_dir, topdown=True):
            for f in files:
                permissions = "r"
                if root == data_dir:
                    permissions = "rwx"
                file_path = os.path.join(root, f)
                # in addition agent user has access
                self.set_acl_for_path(permissions, agent_user, file_path)

    def remove_agent_user(self, volttron_agent_user):
        """
        Invokes sudo to remove the unix user for the given environment.
        """
        if pwd.getpwnam(volttron_agent_user):
            _log.info("Removing volttron agent user {}".format(
                volttron_agent_user))
            userdel = ['sudo', 'userdel', volttron_agent_user]
            userdel_process = subprocess.Popen(
                userdel, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = userdel_process.communicate()
            if userdel_process.returncode != 0:
                _log.error("Remove {user} user failed: {stderr}".format(
                    user=volttron_agent_user, stderr=stderr))
                raise RuntimeError(stderr)


    def setup(self):
        """Creates paths for used directories for the instance."""
        for path in [self.run_dir, self.config_dir, self.install_dir]:
            if not os.path.exists(path):
                # others should have read and execute access to these directory
                # so explicitly set to 755.
                _log.debug("Setting up 755 permissions for path {}".format(
                    path))
                os.makedirs(path)
                os.chmod(path, 0o755)
        # Create certificates directory and its subdirectory at start of platform
        # so if volttron is run in secure mode, the first agent install would already have
        # the directories ready. In secure mode, agents will be run as separate user and will
        # not have access to create these directories
        Certs()

    def finish(self):
        for exeenv in self.agents.values():
            if exeenv.process.poll() is None:
                exeenv.process.send_signal(signal.SIGINT)
        for exeenv in self.agents.values():
            if exeenv.process.poll() is None:
                exeenv.process.terminate()
        for exeenv in self.agents.values():
            if exeenv.process.poll() is None:
                exeenv.process.kill()

    def shutdown(self):
        for agent_uuid in self.agents.keys():
            _log.debug("Stopping agent UUID {}".format(agent_uuid))
            self.stop_agent(agent_uuid)
        event = gevent.event.Event()
        agent = Agent(identity='aip', address='inproc://vip',
                      message_bus=self.message_bus)
        task = gevent.spawn(agent.core.run, event)
        try:
            event.wait()
        finally:
            agent.core.stop()
            task.kill()

    def brute_force_platform_shutdown(self):
        for agent_uuid in list(self.agents.keys()):
            _log.debug("Stopping agent UUID {}".format(agent_uuid))
            self.stop_agent(agent_uuid)
        # kill the platform
        pid = None
        pid_file = "{vhome}/VOLTTRON_PID".format(vhome=get_home())
        with open(pid_file) as f:
            pid = int(f.read())
        if pid:
            os.kill(pid, signal.SIGINT)
            os.remove(pid_file)

    subscribe_address = property(lambda me: me.env.subscribe_address)
    publish_address = property(lambda me: me.env.publish_address)

    config_dir = property(lambda me: os.path.abspath(me.env.volttron_home))
    install_dir = property(lambda me: os.path.join(me.config_dir, 'agents'))
    run_dir = property(lambda me: os.path.join(me.config_dir, 'run'))

    def autostart(self):
        agents, errors = [], []
        for agent_uuid, agent_name in self.list_agents().items():
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

    def install_agent(self, agent_wheel, vip_identity=None, publickey=None,
                      secretkey=None):

        if self.secure_agent_user:
            _log.info("Installing secure Volttron agent...")
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
                unpacker = auth.VolttronPackageWheelFile(agent_wheel,
                                                         certsobj=certs.Certs())
                unpacker.unpack(dest=agent_path)
            else:
                unpack(agent_wheel, dest=agent_path)

            # Is it ok to remove the wheel file after unpacking?
            os.remove(agent_wheel)

            final_identity = self._setup_agent_vip_id(
                agent_uuid, vip_identity=vip_identity)
            keystore = self.get_agent_keystore(agent_uuid, publickey, secretkey)

            self._authorize_agent_keys(agent_uuid, final_identity, keystore.public)

            if self.message_bus == 'rmq':
                rmq_user = get_fq_identity(final_identity,
                                           self.instance_name)
                certs.Certs().create_signed_cert_files(rmq_user, overwrite=False)

            if self.secure_agent_user:
                # When installing, we always create a new user, as anything
                # that already exists is untrustworthy
                created_user = self.add_agent_user(self.agent_name(agent_uuid),
                                                   agent_path)
                self.set_agent_user_permissions(created_user,
                                                agent_uuid,
                                                agent_path)
        except Exception:
            shutil.rmtree(agent_path)
            raise
        return agent_uuid

    def _setup_agent_vip_id(self, agent_uuid, vip_identity=None):
        agent_path = os.path.join(self.install_dir, agent_uuid)
        name = self.agent_name(agent_uuid)
        pkg = UnpackedPackage(os.path.join(agent_path, name))
        identity_template_filename = os.path.join(pkg.distinfo,
                                                  "IDENTITY_TEMPLATE")

        rm_id_template = False

        if not os.path.exists(identity_template_filename):
            agent_name = self.agent_name(agent_uuid)
            name_template = agent_name + "_{n}"
        else:
            with open(identity_template_filename, 'r') as fp:
                name_template = fp.read(64)

            rm_id_template = True

        if vip_identity is not None:
            name_template = vip_identity

        _log.debug(
            'Using name template "' + name_template + '" to generate VIP ID')

        final_identity = self._get_available_agent_identity(name_template)

        if final_identity is None:
            raise ValueError(
                "Agent with VIP ID {} already installed on platform.".format(
                    name_template))

        if not is_valid_identity(final_identity):
            raise ValueError(
                'Invalid identity detecated: {}'.format(
                    ','.format(final_identity)
                ))

        identity_filename = os.path.join(agent_path, "IDENTITY")

        with open(identity_filename, 'w') as fp:
            fp.write(final_identity)

        _log.info("Agent {uuid} setup to use VIP ID {vip_identity}".format(
            uuid=agent_uuid, vip_identity=final_identity))

        # Cleanup IDENTITY_TEMPLATE file.
        if rm_id_template:
            os.remove(identity_template_filename)
            _log.debug('IDENTITY_TEMPLATE file removed.')

        return final_identity

    def get_agent_keystore(self, agent_uuid, encoded_public=None,
                           encoded_secret=None):
        agent_path = os.path.join(self.install_dir, agent_uuid)
        agent_name = self.agent_name(agent_uuid)
        dist_info = os.path.join(agent_path, agent_name,
                                 agent_name + '.dist-info')
        keystore_path = os.path.join(dist_info, 'keystore.json')
        return KeyStore(keystore_path, encoded_public, encoded_secret)

    def _authorize_agent_keys(self, agent_uuid, identity, publickey):
        capabilities = {'edit_config_store': {'identity': identity}}

        if identity == VOLTTRON_CENTRAL_PLATFORM:
            capabilities = {'edit_config_store': {'identity': '/.*/'}}

        entry = AuthEntry(credentials=publickey, user_id=identity,
                          identity=identity,
                          capabilities=capabilities,
                          comments='Automatically added on agent install')
        try:
            AuthFile().add(entry)
        except AuthFileEntryAlreadyExists:
            pass

    def _unauthorize_agent_keys(self, agent_uuid):
        publickey = self.get_agent_keystore(agent_uuid).public
        AuthFile().remove_by_credentials(publickey)

    def _get_agent_data_dir(self, agent_path):
        pkg = UnpackedPackage(agent_path)
        data_dir = os.path.join(os.path.dirname(pkg.distinfo),
                                '{}.agent-data'.format(pkg.package_name))
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        return data_dir

    def create_agent_data_dir_if_missing(self, agent_uuid):
        new_agent_data_dir = self._get_agent_data_dir(self.agent_dir(agent_uuid))
        return new_agent_data_dir

    def _get_data_dir(self, agent_path, agent_name):
        pkg = UnpackedPackage(agent_path)
        data_dir = os.path.join(os.path.dirname(pkg.distinfo),
                                agent_name,
                                'data')
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        return data_dir

    def get_agent_identity_to_uuid_mapping(self):
        results = {}
        for agent_uuid in self.list_agents():
            try:
                agent_identity = self.agent_identity(agent_uuid)
            except ValueError:
                continue

            if agent_identity is not None:
                results[agent_identity] = agent_uuid

        return results

    def get_all_agent_identities(self):
       return list(self.get_agent_identity_to_uuid_mapping().keys())

    def _get_available_agent_identity(self, name_template):
        all_agent_identities = self.get_all_agent_identities()

        # Provided name template is static
        if name_template == name_template.format(n=0):
            return name_template if name_template not in all_agent_identities else None

        # Find a free ID
        count = 1
        while True:
            test_name = name_template.format(n=count)
            if test_name not in all_agent_identities:
                return test_name
            count += 1

    def remove_agent(self, agent_uuid, remove_auth=True):
        if self.secure_agent_user:
            _log.info("Running Volttron agents securely with Unix Users.")
        else:
            _log.info("Not running with secure users.")
        if agent_uuid not in os.listdir(self.install_dir):
            raise ValueError('invalid agent')
        self.stop_agent(agent_uuid)
        msg_bus = self.message_bus
        identity = self.agent_identity(agent_uuid)
        if msg_bus == 'rmq':
            # Delete RabbitMQ user for the agent
            instance_name = self.instance_name
            rmq_user = instance_name + '.' + identity
            try:
                self.rmq_mgmt.delete_user(rmq_user)
            except requests.exceptions.HTTPError as e:
                _log.error(f"RabbitMQ user {rmq_user} is not available to delete. Going ahead and removing agent directory")
        self.agents.pop(agent_uuid, None)
        agent_directory = os.path.join(self.install_dir, agent_uuid)
        volttron_agent_user = None
        if self.secure_agent_user:
            user_id_path = os.path.join(agent_directory, "USER_ID")
            try:
                with open(user_id_path, 'r') as user_id_file:
                    volttron_agent_user = user_id_file.readline()
            except (KeyError, IOError) as user_id_err:
                _log.warn("Volttron agent user not found at {}".format(
                    user_id_path))
                _log.warn(user_id_err)
        if remove_auth:
            self._unauthorize_agent_keys(agent_uuid)
        shutil.rmtree(agent_directory)
        if volttron_agent_user:
            self.remove_agent_user(volttron_agent_user)

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

    def active_agents(self, get_agent_user=False):
        if self.secure_agent_user and get_agent_user:
            return {agent_uuid: (execenv.name, execenv.agent_user)
                    for agent_uuid, execenv in self.agents.items()}
        else:
            return {agent_uuid: execenv.name
                    for agent_uuid, execenv in self.agents.items()}

    def clear_status(self, clear_all=False):
        remove = []
        for agent_uuid, execenv in self.agents.items():
            if execenv.process.poll() is not None:
                if clear_all:
                    remove.append(agent_uuid)
                else:
                    path = os.path.join(self.install_dir, agent_uuid)
                    if not os.path.exists(path):
                        remove.append(agent_uuid)
        for agent_uuid in remove:
            self.agents.pop(agent_uuid, None)

    def status_agents(self, get_agent_user=False):
        if self.secure_agent_user and get_agent_user:
            return [(agent_uuid, agent[0], agent[1], self.agent_status(agent_uuid))
                    for agent_uuid, agent in self.active_agents(get_agent_user=True).items()]
        else:
            return [(agent_uuid, agent_name, self.agent_status(agent_uuid))
                    for agent_uuid, agent_name in self.active_agents().items()]

    def tag_agent(self, agent_uuid, tag):
        tag_file = os.path.join(self.install_dir, agent_uuid, 'TAG')
        if not tag:
            with ignore_enoent:
                os.unlink(tag_file)
        else:
            with open(tag_file, 'w') as file:
                file.write(tag[:64])

    def agent_identity(self, agent_uuid):
        """ Return the identity of the agent that is installed.

        The IDENTITY file is written to the agent's install directory the
        the first time the agent is installed.  This function reads that
        file and returns the read value.

        @param agent_uuid:
        @return:
        """
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        identity_file = os.path.join(self.install_dir, agent_uuid, 'IDENTITY')
        with ignore_enoent, open(identity_file, 'rt') as file:
            return file.readline(64)

    def agent_tag(self, agent_uuid):
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        tag_file = os.path.join(self.install_dir, agent_uuid, 'TAG')
        with ignore_enoent, open(tag_file, 'r') as file:
            return file.readline(64)

    def agent_version(self, agent_uuid):
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        agent_path = os.path.join(self.install_dir, agent_uuid)
        name = self.agent_name(agent_uuid)
        pkg = UnpackedPackage(os.path.join(agent_path, name))
        return pkg.version

    def agent_dir(self, agent_uuid):
        if '/' in agent_uuid or agent_uuid in ['.', '..']:
            raise ValueError('invalid agent')
        return os.path.join(self.install_dir, agent_uuid,
                            self.agent_name(agent_uuid))

    def agent_versions(self):
        agents = {}
        for agent_uuid in os.listdir(self.install_dir):
            try:
                agents[agent_uuid] = (self.agent_name(agent_uuid),
                                      self.agent_version(agent_uuid))
            except KeyError:
                pass
        return agents

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

    def _check_resources(self, resmon, execreqs, reserve=False, agent_user=None):
        hard_reqs = execreqs.get('hard_requirements', {})
        failed_terms = resmon.check_hard_resources(hard_reqs)
        if failed_terms:
            msg = '\n'.join('  {}: {} ({})'.format(
                            term, hard_reqs[term], avail)
                                for term, avail in failed_terms.items())
            _log.error('hard resource requirements not met:\n%s', msg)
            raise ValueError('hard resource requirements not met')
        requirements = execreqs.get('requirements', {})
        try:
            if reserve:
                # return resmon.reserve_soft_resources(requirements)
                if agent_user:
                    return SecureExecutionEnvironment(agent_user=agent_user)
                else:
                    return ExecutionEnvironment()
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
                        for term, avail in failed_terms.items())
        _log.error('%s:\n%s', errmsg, msg)
        raise ValueError(errmsg)

    def check_resources(self, execreqs, agent_user=None):
        resmon = getattr(self.env, 'resmon', None)
        if resmon:
            return self._check_resources(resmon, execreqs, reserve=False,
                                         agent_user=agent_user)

    def _reserve_resources(self, resmon, execreqs, agent_user=None):
        return self._check_resources(resmon, execreqs, reserve=True, agent_user=agent_user)

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

    def start_agent(self, agent_uuid):
        name = self.agent_name(agent_uuid)
        agent_dir = os.path.join(self.install_dir, agent_uuid)
        agent_path_with_name = os.path.join(agent_dir, name)
        execenv = self.agents.get(agent_uuid)
        if execenv and execenv.process.poll() is None:
            _log.warning('request to start already running agent %s',
                         agent_path_with_name)
            raise ValueError('agent is already running')

        pkg = UnpackedPackage(agent_path_with_name)
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
                _log.error('no agent launch class specified in package %s',
                           agent_path_with_name)
                raise ValueError('no agent launch class specified in package')
        config = os.path.join(pkg.distinfo, 'config')
        tag = self.agent_tag(agent_uuid)
        environ = os.environ.copy()
        environ['PYTHONPATH'] = ':'.join([agent_path_with_name] + sys.path)
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
        environ['_LAUNCHED_BY_PLATFORM'] = '1'

        # For backwards compatibility create the identity file if it does not
        # exist.
        identity_file = os.path.join(self.install_dir, agent_uuid, "IDENTITY")
        if not os.path.exists(identity_file):
            _log.debug(
                'IDENTITY FILE MISSING: CREATING IDENTITY FILE WITH VALUE: {}'.
                    format(agent_uuid))
            with open(identity_file, 'w') as fp:
                fp.write(agent_uuid)

        with open(identity_file, 'r') as fp:
            agent_vip_identity = fp.read()

        environ['AGENT_VIP_IDENTITY'] = agent_vip_identity

        module, _, func = module.partition(':')
        # if func:
        #     code = '__import__({0!r}, fromlist=[{1!r}]).{1}()'.format(module,
        #                                                               func)
        #     argv = [sys.executable, '-c', code]
        # else:
        argv = [sys.executable, '-m', module]
        resmon = getattr(self.env, 'resmon', None)
        agent_user = None

        data_dir = self._get_agent_data_dir(agent_path_with_name)

        if self.secure_agent_user:
            _log.info("Starting agent securely...")
            user_id_path = os.path.join(agent_dir, "USER_ID")
            try:
                with open(user_id_path, "r") as user_id_file:
                    volttron_agent_id = user_id_file.readline()
                    pwd.getpwnam(volttron_agent_id)
                    agent_user = volttron_agent_id
                    _log.info("Found secure volttron agent user {}".format(
                        agent_user))
            except (IOError, KeyError) as err:
                _log.info("No existing volttron agent user was found at {} due "
                          "to {}".format(user_id_path, err))

                # May be switched from normal to secure mode with existing agents. To handle this case
                # create users and also set permissions again for existing files
                agent_user = self.add_agent_user(name, agent_dir)
                self.set_agent_user_permissions(agent_user,
                                                agent_uuid,
                                                agent_dir)

                # additionally give permissions to contents of agent-data dir.
                # This is needed only for agents installed before switching to
                # secure mode. Agents installed in secure mode will own files
                # in agent-data dir
                # Moved this to the top so that "agent-data" directory gets
                # created in the beginning
                #data_dir = self._get_agent_data_dir(agent_path_with_name)

                for (root, directories, files) in os.walk(data_dir,
                                                          topdown=True):
                    for directory in directories:
                        self.set_acl_for_path("rwx", agent_user,
                                                  os.path.join(root, directory))
                    for f in files:
                        self.set_acl_for_path("rwx", agent_user,
                                              os.path.join(root, f))


        if self.message_bus == 'rmq':
            rmq_user = get_fq_identity(agent_vip_identity, self.instance_name)
            _log.info("Create RMQ user {} for agent {}".format(rmq_user, agent_vip_identity))

            self.rmq_mgmt.create_user_with_permissions(rmq_user, self.rmq_mgmt.get_default_permissions(rmq_user),
                                                       ssl_auth=True)
            key_file = certs.Certs().private_key_file(rmq_user)
            if not os.path.exists(key_file):
                # This could happen when user switches from zmq to rmq after installing agent
                _log.info(f"agent certs don't exists. creating certs for agent")
                certs.Certs().create_signed_cert_files(rmq_user, overwrite=False)

            if self.secure_agent_user:
                # give read access to user to its own private key file.
                self.set_acl_for_path("r", agent_user, key_file)

        if resmon is None:
            if agent_user:
                execenv = SecureExecutionEnvironment(agent_user=agent_user)
            else:
                execenv = ExecutionEnvironment()
        else:
            execreqs = self._read_execreqs(pkg.distinfo)
            execenv = self._reserve_resources(resmon, execreqs,
                                              agent_user=agent_user)
        execenv.name = name or agent_path_with_name
        _log.info('starting agent %s', agent_path_with_name)
        # data_dir = self._get_agent_data_dir(agent_path_with_name)
        _log.info("starting agent using {} ".format(type(execenv)))
        execenv.execute(argv, cwd=agent_path_with_name, env=environ, close_fds=True,
                        stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
        self.agents[agent_uuid] = execenv
        proc = execenv.process
        _log.info('agent %s has PID %s', agent_path_with_name, proc.pid)
        gevent.spawn(log_stream, 'agents.stderr', name, proc.pid, argv[0],
                      log_entries('agents.log', name, proc.pid, logging.ERROR,
                                  proc.stderr))
        gevent.spawn(log_stream, 'agents.stdout', name, proc.pid, argv[0],
                   ((logging.INFO, line) for line in (l.splitlines() for l
                      in proc.stdout)))

        return self.agent_status(agent_uuid)

    def agent_status(self, agent_uuid):
        execenv = self.agents.get(agent_uuid)
        if execenv is None:
            return (None, None)
        return (execenv.process.pid, execenv.process.poll())

    def stop_agent(self, agent_uuid):
        try:
            execenv = self.agents[agent_uuid]
            return execenv.stop()
        except KeyError:
            return

    def agent_uuid_from_pid(self, pid):
        for agent_uuid, execenv in self.agents.items():
            if execenv.process.pid == pid:
                return agent_uuid if execenv.process.poll() is None else None
