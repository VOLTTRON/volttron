# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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


from __future__ import absolute_import, print_function

import bisect
import errno
import logging
import os
import random
import re
import shutil
import uuid

import gevent
from gevent.fileobject import FileObject
from zmq import green as zmq
from volttron.platform.agent import json as jsonapi

from .agent.utils import strip_comments, create_file_if_missing, watch_file
from .vip.agent import Agent, Core, RPC
from .vip.socket import encode_key, BASE64_ENCODED_CURVE_KEY_LEN
from volttron.platform.vip.agent.errors import VIPError

_log = logging.getLogger(__name__)

_dump_re = re.compile(r'([,\\])')
_load_re = re.compile(r'\\(.)|,')


def isregex(obj):
    return len(obj) > 1 and obj[0] == obj[-1] == '/'


def dump_user(*args):
    return ','.join([_dump_re.sub(r'\\\1', arg) for arg in args])


def load_user(string):
    def sub(match):
        return match.group(1) or '\x00'

    return _load_re.sub(sub, string).split('\x00')


class AuthException(Exception):
    """General exception for any auth error"""
    pass


class AuthService(Agent):
    def __init__(self, auth_file, protected_topics_file, setup_mode, aip, *args, **kwargs):
        self.allow_any = kwargs.pop('allow_any', False)
        super(AuthService, self).__init__(*args, **kwargs)

        # This agent is started before the router so we need
        # to keep it from blocking.
        self.core.delay_running_event_set = False

        self.auth_file_path = os.path.abspath(auth_file)
        self.auth_file = AuthFile(self.auth_file_path)
        self.aip = aip
        self.zap_socket = None
        self._zap_greenlet = None
        self.auth_entries = []
        self._is_connected = False
        self._protected_topics_file = protected_topics_file
        self._protected_topics_file_path = os.path.abspath(protected_topics_file)
        self._protected_topics = {}
        self._setup_mode = setup_mode
        self._auth_failures = []

    @Core.receiver('onsetup')
    def setup_zap(self, sender, **kwargs):
        self.zap_socket = zmq.Socket(zmq.Context.instance(), zmq.ROUTER)
        self.zap_socket.bind('inproc://zeromq.zap.01')
        if self.allow_any:
            _log.warn('insecure permissive authentication enabled')
        self.read_auth_file()
        self._read_protected_topics_file()
        self.core.spawn(watch_file, self.auth_file_path, self.read_auth_file)
        self.core.spawn(watch_file, self._protected_topics_file_path, self._read_protected_topics_file)

    def read_auth_file(self):
        _log.info('loading auth file %s', self.auth_file_path)
        entries = self.auth_file.read_allow_entries()
        entries = [entry for entry in entries if entry.enabled]
        # sort the entries so the regex credentails follow the concrete creds
        entries.sort()
        self.auth_entries = entries
        _log.info('auth file %s loaded', self.auth_file_path)
        if self._is_connected:
            self._send_update()

    def get_protected_topics(self):
        protected = self._protected_topics
        return protected

    def _read_protected_topics_file(self):
        #Read protected topics file and send to router
        try:
            create_file_if_missing(self._protected_topics_file)
            with open(self._protected_topics_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                self._protected_topics = jsonapi.loads(data) if data else {}
                self._send_protected_update_to_pubsub(self._protected_topics)
        except Exception:
            _log.exception('error loading %s', self._protected_topics_file)


    def _send_update(self):
        user_to_caps = self.get_user_to_capabilities()
        peers = self.vip.peerlist().get(timeout=5)
        _log.debug("AUTH new capabilities update: {}".format(user_to_caps))
        for peer in peers:
            self.vip.rpc.call(peer, 'auth.update', user_to_caps)
        self._send_auth_update_to_pubsub()

    def _send_auth_update_to_pubsub(self):
        user_to_caps = self.get_user_to_capabilities()
        #Send auth update message to router
        json_msg = jsonapi.dumps(
            dict(capabilities=user_to_caps)
        )
        frames = [zmq.Frame(b'auth_update'), zmq.Frame(str(json_msg))]
        # <recipient, subsystem, args, msg_id, flags>
        self.core.socket.send_vip(b'', 'pubsub', frames, copy=False)

    def _send_protected_update_to_pubsub(self, contents):
        protected_topics_msg = jsonapi.dumps(contents)

        frames = [zmq.Frame(b'protected_update'), zmq.Frame(protected_topics_msg)]
        if self._is_connected:
            try:
                # <recipient, subsystem, args, msg_id, flags>
                self.core.socket.send_vip(b'', 'pubsub', frames, copy=False)
            except VIPError as ex:
                _log.error("Error in sending protected topics update to clear PubSub: " + str(ex))


    @Core.receiver('onstop')
    def stop_zap(self, sender, **kwargs):
        if self._zap_greenlet is not None:
            self._zap_greenlet.kill()

    @Core.receiver('onfinish')
    def unbind_zap(self, sender, **kwargs):
        if self.zap_socket is not None:
            self.zap_socket.unbind('inproc://zeromq.zap.01')

    @Core.receiver('onstart')
    def zap_loop(self, sender, **kwargs):
        self._is_connected = True
        self._zap_greenlet = gevent.getcurrent()
        sock = self.zap_socket
        time = gevent.core.time
        blocked = {}
        wait_list = []
        timeout = None
        self._send_auth_update_to_pubsub()
        while True:
            events = sock.poll(timeout)
            now = time()
            if events:
                zap = sock.recv_multipart()

                version = zap[2]
                if version != b'1.0':
                    continue
                domain, address, userid, kind = zap[4:8]
                credentials = zap[8:]
                if kind == b'CURVE':
                    credentials[0] = encode_key(credentials[0])
                elif kind not in [b'NULL', b'PLAIN']:
                    continue
                response = zap[:4]
                user = self.authenticate(domain, address, kind, credentials)
                if user:
                    _log.info(
                        'authentication success: domain=%r, address=%r, '
                        'mechanism=%r, credentials=%r, user_id=%r',
                        domain, address, kind, credentials[:1], user)
                    response.extend([b'200', b'SUCCESS', user, b''])
                    sock.send_multipart(response)
                else:
                    _log.info(
                        'authentication failure: domain=%r, address=%r, '
                        'mechanism=%r, credentials=%r',
                        domain, address, kind, credentials)
                    #If in setup mode, add/update auth entry
                    if self._setup_mode:
                        self._update_auth_entry(domain, address, kind, credentials[0], userid)
                        _log.info(
                            'new authentication entry added in setup mode: domain=%r, address=%r, '
                            'mechanism=%r, credentials=%r, user_id=%r',
                            domain, address, kind, credentials[:1], userid)
                        response.extend([b'200', b'SUCCESS', '', b''])
                        _log.debug("AUTH response: {}".format(response))
                        sock.send_multipart(response)
                    else:
                        self._update_auth_failures(domain, address, kind, credentials[0], userid)

                    try:
                        expire, delay = blocked[address]
                    except KeyError:
                        delay = random.random()
                    else:
                        if now >= expire:
                            delay = random.random()
                        else:
                            delay *= 2
                            if delay > 100:
                                delay = 100
                    expire = now + delay
                    bisect.bisect(wait_list, (expire, address, response))
                    blocked[address] = expire, delay
            while wait_list:
                expire, address, response = wait_list[0]
                if now < expire:
                    break
                wait_list.pop(0)
                response.extend([b'400', b'FAIL', b'', b''])
                sock.send_multipart(response)
                try:
                    if now >= blocked[address][0]:
                        blocked.pop(address)
                except KeyError:
                    pass
            timeout = (wait_list[0][0] - now) if wait_list else None

    def authenticate(self, domain, address, mechanism, credentials):
        for entry in self.auth_entries:
            if entry.match(domain, address, mechanism, credentials):
                return entry.user_id or dump_user(
                    domain, address, mechanism, *credentials[:1])
        if mechanism == 'NULL' and address.startswith('localhost:'):
            parts = address.split(':')[1:]
            if len(parts) > 2:
                pid = int(parts[2])
                agent_uuid = self.aip.agent_uuid_from_pid(pid)
                if agent_uuid:
                    return dump_user(domain, address, 'AGENT', agent_uuid)
            uid = int(parts[0])
            if uid == os.getuid():
                return dump_user(domain, address, mechanism, *credentials[:1])
        if self.allow_any:
            return dump_user(domain, address, mechanism, *credentials[:1])

    @RPC.export
    def get_user_to_capabilities(self):
        """RPC method

        Gets a mapping of all users to their capabiliites.

        :returns: mapping of users to capabilities
        :rtype: dict
        """
        user_to_caps = {}
        for entry in self.auth_entries:
            user_to_caps[entry.user_id] = entry.capabilities
        return user_to_caps

    @RPC.export
    def get_authorizations(self, user_id):
        """RPC method

        Gets capabilities, groups, and roles for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: tuple of capabiliy-list, group-list, role-list
        :rtype: tuple
        """
        use_parts = True
        try:
            domain, address, mechanism, credentials = load_user(user_id)
        except ValueError:
            use_parts = False
        for entry in self.auth_entries:
            if entry.user_id == user_id:
                return [entry.capabilities, entry.groups, entry.roles]
            elif use_parts:
                if entry.match(domain, address, mechanism, [credentials]):
                    return entry.capabilities, entry.groups, entry.roles

    @RPC.export
    def get_authorization_failures(self):
        return list(self._auth_failures)

    def _get_authorizations(self, user_id, index):
        """Convenience method for getting authorization component by index"""
        auths = self.get_authorizations(user_id)
        if auths:
            return auths[index]
        return []

    @RPC.export
    def get_capabilities(self, user_id):
        """RPC method

        Gets capabilities for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of capabilities
        :rtype: list
        """
        return self._get_authorizations(user_id, 0)

    @RPC.export
    def get_groups(self, user_id):
        """RPC method

        Gets groups for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of groups
        :rtype: list
        """
        return self._get_authorizations(user_id, 1)

    @RPC.export
    def get_roles(self, user_id):
        """RPC method

        Gets roles for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of roles
        :rtype: list
        """
        return self._get_authorizations(user_id, 2)

    def _update_auth_entry(self, domain, address, mechanism, credential, user_id):
        #Make a new entry
        fields = {
            "domain": domain,
            "address": address,
            "mechanism": mechanism,
            "credentials": credential,
            "groups": "",
            "roles": "",
            "capabilities": "",
            "comments": "Auth entry added in setup mode",
        }
        new_entry = AuthEntry(**fields)

        try:
            self.auth_file.add(new_entry, overwrite=False)
        except AuthException as err:
            _log.error('ERROR: %s\n' % err.message)

    def _update_auth_failures(self, domain, address, mechanism, credential, user_id):
        for entry in self._auth_failures:
            #Check if failure entry exists. If so, increment the failure count
            if ((entry['domain'] == domain) and
                (entry['address'] == address) and
                (entry['mechanism'] == mechanism) and
                    (entry['credentials'] == credential)):
                entry['retries'] += 1
                return
        # Add a new failure entry
        fields = {
            "domain": domain,
            "address": address,
            "mechanism": mechanism,
            "credentials": credential,
            "user_id": user_id,
            "retries": 1
        }
        self._auth_failures.append(dict(fields))
        return

class String(unicode):
    def __new__(cls, value):
        obj = super(String, cls).__new__(cls, value)
        if isregex(obj):
            obj.regex = regex = re.compile('^' + obj[1:-1] + '$')
            obj.match = lambda val: bool(regex.match(val))
        return obj

    def match(self, value):
        return value == self


class List(list):
    def match(self, value):
        for elem in self:
            if elem.match(value):
                return True
        return False


class AuthEntryInvalid(AuthException):
    """Exception for invalid AuthEntry objects"""
    pass


class AuthEntry(object):
    """An authentication entry contains fields for authenticating and
    granting permissions to an agent that connects to the platform.

    :param str domain: Name assigned to locally bound address
    :param str address: Remote address of the agent
    :param str mechanism: Authentication mechanism, valid options are
        'NULL' (no authentication), 'PLAIN' (username/password),
        'CURVE' (CurveMQ public/private keys)
    :param str credentials: Value depends on `mechanism` parameter:
        `None` if mechanism is 'NULL'; password if mechanism is
        'PLAIN'; encoded public key if mechanism is 'CURVE' (see
        :py:meth:`volttron.platform.vip.socket.encode_key` for method
        to encode public key)
    :param str user_id: Name to associate with agent (Note: this does
        not have to match the agent's VIP identity)
    :param list capabilities: Authorized capabilities for this agent
    :param list roles: Authorized roles for this agent. (Role names map
        to a set of capabilities)
    :param list groups: Authorized groups for this agent. (Group names
        map to a set of roles)
    :param str comments: Comments to associate with entry
    :param bool enabled: Entry will only be used if this value is True
    :param kwargs: These extra arguments will be ignored
    """
    def __init__(self, domain=None, address=None, mechanism='CURVE',
                 credentials=None, user_id=None, groups=None, roles=None,
                 capabilities=None, comments=None, enabled=True, **kwargs):

        self.domain = AuthEntry._build_field(domain)
        self.address = AuthEntry._build_field(address)
        self.mechanism = mechanism
        self.credentials = AuthEntry._build_field(credentials)
        self.groups = AuthEntry._build_field(groups, list, str) or []
        self.roles = AuthEntry._build_field(roles, list, str) or []
        self.capabilities = AuthEntry._build_field(capabilities, list,
                                                   str) or []
        self.comments = AuthEntry._build_field(comments)
        if user_id is None:
            user_id = str(uuid.uuid4())
        self.user_id = user_id.encode('utf-8')
        self.enabled = enabled
        if kwargs:
            _log.debug(
                'auth record has unrecognized keys: %r' % (kwargs.keys(),))
        self._check_validity()

    def __lt__(self, other):
        """Entries with non-regex credentials will be less than regex
        credentials. When sorted, the non-regex credentials will be
        checked first."""
        try:
            self.credentials.regex
        except AttributeError:
            return True
        return False

    @staticmethod
    def _build_field(value, list_class=List, str_class=String):
        if not value:
            return None
        if isinstance(value, basestring):
            return String(value)
        return List(String(elem) for elem in value)

    def add_capabilities(self, capabilities):
        caps_set = set(capabilities)
        caps_set |= set(self.capabilities)
        self.capabilities = AuthEntry._build_field(
            list(caps_set), list, str) or []

    def match(self, domain, address, mechanism, credentials):
        return ((self.domain is None or self.domain.match(domain)) and
                (self.address is None or self.address.match(address)) and
                self.mechanism == mechanism and
                (self.mechanism == 'NULL' or
                 (len(self.credentials) > 0 and
                  self.credentials.match(credentials[0]))))

    def __str__(self):
        return (u'domain={0.domain!r}, address={0.address!r}, '
                'mechanism={0.mechanism!r}, credentials={0.credentials!r}, '
                'user_id={0.user_id!r}'.format(self))

    def __repr__(self):
        cls = self.__class__
        return '%s.%s(%s)' % (cls.__module__, cls.__name__, self)

    @staticmethod
    def valid_credentials(cred, mechanism='CURVE'):
        """Raises AuthEntryInvalid if credentials are invalid"""
        AuthEntry.valid_mechanism(mechanism)
        if mechanism == 'NULL':
            return
        if cred is None:
            raise AuthEntryInvalid(
                'credentials parameter is required for mechanism {}'
                .format(mechanism))
        if isregex(cred):
            return
        if mechanism == 'CURVE' and len(cred) != BASE64_ENCODED_CURVE_KEY_LEN:
            raise AuthEntryInvalid('Invalid CURVE public key {}')

    @staticmethod
    def valid_mechanism(mechanism):
        """Raises AuthEntryInvalid if mechanism is invalid"""
        if mechanism not in ('NULL', 'PLAIN', 'CURVE'):
            raise AuthEntryInvalid(
                'mechanism must be either "NULL", "PLAIN" or "CURVE"')

    def _check_validity(self):
        """Raises AuthEntryInvalid if entry is invalid"""
        AuthEntry.valid_credentials(self.credentials, self.mechanism)


class AuthFile(object):
    def __init__(self, auth_file=None):
        if auth_file is None:
            auth_file_dir = os.path.expanduser(
                os.environ.get('VOLTTRON_HOME', '~/.volttron'))
            auth_file = os.path.join(auth_file_dir, 'auth.json')
        self.auth_file = auth_file
        self._check_for_upgrade()

    @property
    def version(self):
        return {'major': 1, 'minor': 1}

    def _check_for_upgrade(self):
        allow_list, groups, roles, version = self._read()
        if version != self.version:
            if version['major'] <= self.version['major']:
                self._upgrade(allow_list, groups, roles, version)
            else:
                _log.error('This version of VOLTTRON cannot parse {}. '
                           'Please upgrade VOLTTRON or move or delete '
                           'this file.'.format(self.auth_file))

    def _read(self):
        auth_data = {}
        try:
            create_file_if_missing(self.auth_file)
            with open(self.auth_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                before_strip_comments = FileObject(fil, close=False).read()
                data = strip_comments(before_strip_comments)
                if data != before_strip_comments:
                    _log.warn('Comments in %s are deprecated and will not be '
                              'preserved', self.auth_file)
                if data:
                    auth_data = jsonapi.loads(data)
        except Exception:
            _log.exception('error loading %s', self.auth_file)

        allow_list = auth_data.get('allow', [])
        groups = auth_data.get('groups', {})
        roles = auth_data.get('roles', {})
        version = auth_data.get('version', {'major': 0, 'minor': 0})
        return allow_list, groups, roles, version

    def read(self):
        """Gets the allowed entries, groups, and roles from the auth
        file.

        :returns: tuple of allow-entries-list, groups-dict, roles-dict
        :rtype: tuple
        """
        allow_list, groups, roles, _ = self._read()
        entries = self._get_entries(allow_list)
        self._use_groups_and_roles(entries, groups, roles)
        return entries, groups, roles

    def _upgrade(self, allow_list, groups, roles, version):
        backup = self.auth_file + '.' + str(uuid.uuid4()) + '.bak'
        shutil.copy(self.auth_file, backup)
        _log.info('Created backup of {} at {}'.format(self.auth_file, backup))

        def warn_invalid(entry, msg=''):
            _log.warn('Invalid entry {} in auth file {}. {}'
                      .format(entry, self.auth_file, msg))

        def upgrade_0_to_1(allow_list):
            new_allow_list = []
            for entry in allow_list:
                try:
                    credentials = entry['credentials']
                except KeyError:
                    warn_invalid(entry)
                    continue
                if isregex(credentials):
                    msg = 'Cannot upgrade entries with regex credentials'
                    warn_invalid(entry, msg)
                    continue
                if credentials == 'NULL':
                    mechanism = 'NULL'
                    credentials = None
                else:
                    match = re.match(r'^(PLAIN|CURVE):(.*)', credentials)
                    if match is None:
                        msg = 'Expected NULL, PLAIN, or CURVE credentials'
                        warn_invalid(entry, msg)
                        continue
                    try:
                        mechanism = match.group(1)
                        credentials = match.group(2)
                    except IndexError:
                        warn_invalid(entry, 'Unexpected credential format')
                        continue
                new_allow_list.append({
                    "domain": entry.get('domain'),
                    "address": entry.get('address'),
                    "mechanism": mechanism,
                    "credentials": credentials,
                    "user_id": entry.get('user_id'),
                    "groups": entry.get('groups', []),
                    "roles": entry.get('roles', []),
                    "capabilities": entry.get('capabilities', []),
                    "comments": entry.get('comments'),
                    "enabled": entry.get('enabled', True)
                })
            return new_allow_list

        def upgrade_1_0_to_1_1(allow_list):
            new_allow_list = []
            user_id_set = set()
            for entry in allow_list:
                user_id = entry.get('user_id')
                if user_id:
                    if user_id in user_id_set:
                        new_user_id = str(uuid.uuid4())
                        msg = ('user_id {} is already present in '
                               'authentication entry. Changed to user_id to '
                               '{}').format(user_id, new_user_id)
                        _log.warn(msg)
                        user_id_ = new_user_id
                else:
                    user_id = str(uuid.uuid4())
                user_id_set.add(user_id)
                entry['user_id'] = user_id
                new_allow_list.append(entry)
            return new_allow_list

        if version['major'] == 0:
            allow_list = upgrade_0_to_1(allow_list)
            version['major'] = 1
            version['minor'] = 0
        if version['major'] == 1 and version['minor'] == 0:
            allow_list = upgrade_1_0_to_1_1(allow_list)

        entries = self._get_entries(allow_list)
        self._write(entries, groups, roles)

    def read_allow_entries(self):
        """Gets the allowed entries from the auth file.

        :returns: list of allow-entries
        :rtype: list
        """
        return self.read()[0]

    def find_by_credentials(self, credentials):
        """Find all entries that have the given credentials

        :param str credentials: The credentials to search for
        :return: list of entries
        :rtype: list
        """
        return [entry for entry in self.read_allow_entries()
                if str(entry.credentials) == credentials]

    def _get_entries(self, allow_list):
        entries = []
        for file_entry in allow_list:
            try:
                entry = AuthEntry(**file_entry)
            except TypeError:
                _log.warn('invalid entry %r in auth file %s',
                          file_entry, self.auth_file)
            except AuthEntryInvalid as e:
                _log.warn('invalid entry %r in auth file %s (%s)',
                          file_entry, self.auth_file, e.message)
            else:
                entries.append(entry)
        return entries

    def _use_groups_and_roles(self, entries, groups, roles):
        """Add capabilities to each entry based on groups and roles"""
        for entry in entries:
            entry_roles = entry.roles
            # Each group is a list of roles
            for group in entry.groups:
                entry_roles += groups.get(group, [])
            capabilities = []
            # Each role is a list of capabilities
            for role in entry_roles:
                capabilities += roles.get(role, [])
            entry.add_capabilities(list(set(capabilities)))

    def _check_if_exists(self, entry):
        """Raises AuthFileEntryAlreadyExists if entry is already in file"""
        for index, prev_entry in enumerate(self.read_allow_entries()):
            if entry.user_id == prev_entry.user_id:
                raise AuthFileUserIdAlreadyExists(entry.user_id, [index])

            # Compare AuthEntry objects component-wise, rather than
            # using match, because match will evaluate regex.
            if (prev_entry.domain == entry.domain and
                    prev_entry.address == entry.address and
                    prev_entry.mechanism == entry.mechanism and
                    prev_entry.credentials == entry.credentials):
                raise AuthFileEntryAlreadyExists([index])

    def _update_by_indices(self, auth_entry, indices):
        """Updates all entries at given indices with auth_entry"""
        for index in indices:
            self.update_by_index(auth_entry, index)

    def add(self, auth_entry, overwrite=False):
        """Adds an AuthEntry to the auth file

        :param auth_entry: authentication entry
        :param overwrite: set to true to overwrite matching entries
        :type auth_entry: AuthEntry
        :type overwrite: bool

        .. warning:: If overwrite is set to False and if auth_entry matches an
                     existing entry then this method will raise
                     AuthFileEntryAlreadyExists
        """
        try:
            self._check_if_exists(auth_entry)
        except AuthFileEntryAlreadyExists as err:
            if overwrite:
                self._update_by_indices(auth_entry, err.indices)
            else:
                raise err
        else:
            entries, groups, roles = self.read()
            entries.append(auth_entry)
            self._write(entries, groups, roles)

    def remove_by_credentials(self, credentials):
        """Removes entry from auth file by credential

        :para credential: entries will this credential will be
            removed
        :type credential: str
        """
        entries, groups, roles = self.read()
        entries = [e for e in entries if e.credentials != credentials]
        self._write(entries, groups, roles)

    def remove_by_index(self, index):
        """Removes entry from auth file by index

        :param index: index of entry to remove
        :type index: int

        .. warning:: Calling with out-of-range index will raise
                     AuthFileIndexError
        """
        self.remove_by_indices([index])

    def remove_by_indices(self, indices):
        """Removes entry from auth file by indices

        :param indices: list of indicies of entries to remove
        :type indices: list

        .. warning:: Calling with out-of-range index will raise
                     AuthFileIndexError
        """
        indices = list(set(indices))
        indices.sort(reverse=True)
        entries, groups, roles = self.read()
        for index in indices:
            try:
                del entries[index]
            except IndexError:
                raise AuthFileIndexError(index)
        self._write(entries, groups, roles)

    def _set_groups_or_roles(self, groups_or_roles, is_group=True):
        param_name = 'groups' if is_group else 'roles'
        if not isinstance(groups_or_roles, dict):
            raise ValueError('{} parameter must be dict'.format(param_name))
        for key, value in groups_or_roles.iteritems():
            if not isinstance(value, list):
                raise ValueError('each value of the {} dict must be '
                                 'a list'.format(param_name))
        entries, groups, roles = self.read()
        if is_group:
            groups = groups_or_roles
        else:
            roles = groups_or_roles
        self._write(entries, groups, roles)

    def set_groups(self, groups):
        """Define the mapping of group names to role lists

        :param groups: dict where the keys are group names and the
                       values are lists of capability names
        :type groups: dict

        .. warning:: Calling with invalid groups will raise ValueError
        """
        self._set_groups_or_roles(groups, is_group=True)

    def set_roles(self, roles):
        """Define the mapping of role names to capability lists

        :param roles: dict where the keys are role names and the
                      values are lists of group names
        :type groups: dict

        .. warning:: Calling with invalid roles will raise ValueError
        """
        self._set_groups_or_roles(roles, is_group=False)

    def update_by_index(self, auth_entry, index):
        """Updates entry will given auth entry at given index

        :param auth_entry: new authorization entry
        :param index: index of entry to update
        :type auth_entry: AuthEntry
        :type index: int

        .. warning:: Calling with out-of-range index will raise
                     AuthFileIndexError
        """
        entries, groups, roles = self.read()
        try:
            entries[index] = auth_entry
        except IndexError:
            raise AuthFileIndexError(index)
        self._write(entries, groups, roles)

    def _write(self, entries, groups, roles):
        auth = {'allow': [vars(x) for x in entries], 'groups': groups,
                'roles': roles, 'version': self.version}

        with open(self.auth_file, 'w') as fp:
            fp.write(jsonapi.dumps(auth, indent=2))


class AuthFileIndexError(AuthException, IndexError):
    """Exception for invalid indices provided to AuthFile"""

    def __init__(self, indices, message=None):
        if not isinstance(indices, list):
            indices = [indices]
        if message is None:
            message = 'Invalid {}: {}'.format(
                'indicies' if len(indices) > 1 else 'index', indices)
        super(AuthFileIndexError, self).__init__(message)
        self.indices = indices


class AuthFileEntryAlreadyExists(AuthFileIndexError):
    """Exception if adding an entry that already exists"""

    def __init__(self, indicies, message=None):
        if message is None:
            message = ('entry matches domain, address and credentials at '
                       'index {}').format(indicies)
        super(AuthFileEntryAlreadyExists, self).__init__(indicies, message)


class AuthFileUserIdAlreadyExists(AuthFileEntryAlreadyExists):
    """Exception if adding an entry that has a taken user_id"""

    def __init__(self, user_id, indicies, message=None):
        if message is None:
            message = ('user_id {} is already in use at '
                       'index {}').format(user_id, indicies)
        super(AuthFileUserIdAlreadyExists, self).__init__(indicies, message)
