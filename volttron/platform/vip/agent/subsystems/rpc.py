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



import inspect
import logging
import os
import sys
import traceback
import weakref
import re

import gevent.local
from gevent.event import AsyncResult
from volttron.platform import jsonapi
from volttron.platform.agent.utils import get_messagebus

from .base import SubsystemBase
from ..errors import VIPError
from ..results import counter, ResultsDictionary
from ..decorators import annotate, annotations, dualmethod, spawn
from .... import jsonrpc
from volttron.platform.vip.socket import Message

from zmq import Frame, NOBLOCK, ZMQError, EINVAL, EHOSTUNREACH
from zmq.green import ENOTSOCK


__all__ = ['RPC']


_ROOT_PACKAGE_PATH = os.path.dirname(
    __import__(__name__.split('.', 1)[0]).__path__[-1]) + os.sep

_log = logging.getLogger(__name__)


def _isregex(obj):
    return obj is not None and isinstance(obj, str) and len(obj) > 1 and obj[0] == obj[-1] == '/'

class Dispatcher(jsonrpc.Dispatcher):
    def __init__(self, methods, local):
        super(Dispatcher, self).__init__()
        self.methods = methods
        self.local = local
        self._results = ResultsDictionary()

    def serialize(self, json_obj):
        return jsonapi.dumps(json_obj)

    def deserialize(self, json_string):
        return jsonapi.loads(json_string)

    def batch_call(self, requests):
        methods = []
        results = []
        for notify, method, args, kwargs in requests:
            if notify:
                ident = None
            else:
                result = next(self._results)
                ident = result.ident
                results.append(result)
            methods.append((ident, method, args, kwargs))
        return super(Dispatcher, self).batch_call(methods), results

    def call(self, method, args=None, kwargs=None):
        # pylint: disable=arguments-differ
        result = next(self._results)
        return super(Dispatcher, self).call(
            result.ident, method, args, kwargs), result

    def result(self, response, ident, value, context=None):
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set(value)

    def error(self, response, ident, code, message, data=None, context=None):
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set_exception(jsonrpc.exception_from_json(code, message, data))

    def exception(self, response, ident, message, context=None):
        # XXX: Should probably wrap exception in RPC specific error
        #      rather than re-raising.
        exc_type, exc, exc_tb = sys.exc_info()   # pylint: disable=unused-variable
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set_exception(exc)

    def method(self, request, ident, name, args, kwargs,
               batch=None, context=None):
        if kwargs:
            try:
                args, kwargs = kwargs['*args'], kwargs['**kwargs']
            except KeyError:
                pass
        try:
            method = self.methods[name]
        except KeyError:
            if name == 'inspect':
                return {'methods': list(self.methods)}
            elif name.endswith('.inspect'):
                try:
                    method = self.methods[name[:-8]]
                except KeyError:
                    pass
                else:
                    return self._inspect(method)
            raise NotImplementedError(name)
        local = self.local
        local.vip_message = context
        local.request = request
        local.batch = batch
        try:
            return method(*args, **kwargs)
        except Exception as exc:   # pylint: disable=broad-except
            exc_tb = traceback.format_exc()
            _log.error('unhandled exception in JSON-RPC method %r: \n%s',
                       name, exc_tb)
            if getattr(method, 'traceback', True):
                exc.exc_info = {'exc_tb': exc_tb}
            raise
        finally:
            del local.vip_message
            del local.request
            del local.batch

    @staticmethod
    def _inspect(method):
        response = {'params': {}}
        signature = inspect.signature(method)
        for p in signature.parameters.values():
            response['params'][p.name] = {
                    'kind': p.kind.name
            }
            if p.default is not inspect.Parameter.empty:
                response['params'][p.name]['default'] = p.default
            if p.annotation is not inspect.Parameter.empty:
                annotation = p.annotation.__name__ if type(p.annotation) is type else str(p.annotation)
                response['params'][p.name]['annotation'] = annotation
        doc = inspect.getdoc(method)
        if doc:
            response['doc'] = doc
        try:
            source = inspect.getsourcefile(method)
            cut = len(os.path.commonprefix([_ROOT_PACKAGE_PATH, source]))
            source = source[cut:]
            lineno = inspect.getsourcelines(method)[1]
        except Exception:
            pass
        else:
            response['source'] = {
                'file': source,
                'line_number': lineno
            }
        ret = signature.return_annotation
        if ret is not inspect.Signature.empty:
            response['return'] = ret.__name__ if type(ret) is type else str(ret)
        return response


class RPC(SubsystemBase):
    def __init__(self, core, owner, peerlist_subsys):
        self.core = weakref.ref(core)
        self._owner = owner
        self.context = None
        self._exports = {}
        self._dispatcher = None
        self._counter = counter()
        self._outstanding = weakref.WeakValueDictionary()
        core.register('RPC', self._handle_subsystem, self._handle_error)
        core.register('external_rpc', self._handle_external_rpc_subsystem, self._handle_error)
        self._isconnected = True
        self._message_bus = self.core().messagebus
        self.peerlist_subsystem = peerlist_subsys
        self.peer_list = {}

        def export(member):   # pylint: disable=redefined-outer-name
            for name in annotations(member, set, 'rpc.exports'):
                self._exports[name] = member
        inspect.getmembers(owner, export)

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self.context = gevent.local.local()
            self._dispatcher = Dispatcher(self._exports, self.context)
        core.onsetup.connect(setup, self)
        core.ondisconnected.connect(self._disconnected)
        core.onconnected.connect(self._connected)
        self._iterate_exports()

    def _connected(self, sender, **kwargs):
        self._isconnected =True
        # Registering to 'onadd' and 'ondrop' signals to get notified whenever new peer is added/removed
        self.peerlist_subsystem.onadd.connect(self._add_new_peer)
        self.peerlist_subsystem.ondrop.connect(self._drop_new_peer)

    def _disconnected(self, sender, **kwargs):
        self._isconnected = False

    def _add_new_peer(self, sender, **kwargs):
        try:
            peer = kwargs.pop('peer')
            message_bus = kwargs.pop('message_bus')
            self.peer_list[peer] = message_bus
        except KeyError:
            pass

    def _drop_new_peer(self, sender, **kwargs):
        try:
            peer = kwargs.pop('peer')
            self.peer_list.pop(peer)
        except KeyError:
            pass

    def _iterate_exports(self):
        '''Iterates over exported methods and adds authorization checks
        as necessary
        '''
        for method_name in self._exports:
            method = self._exports[method_name]
            caps = annotations(method, set, 'rpc.allow_capabilities')
            if caps:
                self._exports[method_name] = self._add_auth_check(method, caps)

    def _add_auth_check(self, method, required_caps):
        '''Adds an authorization check to verify the calling agent has the
        required capabilities.
        '''
        def checked_method(*args, **kwargs):
            user = str(self.context.vip_message.user)
            if self._message_bus == "rmq":
                # When we address issue #2107 external platform user should
                # have instance name also included in username.
                user = user.split(".")[1]
            _log.debug("Current user in checked_method is {}".format(user))
            user_capabilites = self._owner.vip.auth.get_capabilities(user)
            _log.debug("**user caps is: {}".format(user_capabilites))
            if user_capabilites:
                user_capabilities_names = set(user_capabilites.keys())
            else:
                user_capabilities_names = set()

            _log.debug("Required caps is : {}".format(required_caps))
            _log.debug("user capability names: {}".format(user_capabilities_names))
            if not required_caps.issubset(user_capabilities_names):
                msg = ('method "{}" requires capabilities {}, but capability {} was'
                       ' provided for user {}').format(method.__name__, required_caps, user_capabilites, user)
                raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED, msg)
            else:
                # Now check if args passed to method are the ones allowed.

                for cap_name, param_dict in user_capabilites.items():
                    if param_dict and required_caps and cap_name in required_caps:
                        # if the method has required capabilities and
                        # if the user capability has argument restrictions, check if the args passed to method
                        # match the requirement
                        _log.debug("args = {} kwargs= {}".format(args, kwargs))
                        args_dict = inspect.getcallargs(method, *args, **kwargs)
                        _log.debug("dict = {}".format(args_dict))
                        _log.debug("name= {} parameters allowed={}".format(cap_name, param_dict))
                        for name, value in param_dict.items():
                            _log.debug("name= {} value={}".format(name, value))
                            if name not in args_dict:
                                raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED,
                                                                  "User {} capability is not defined "
                                                                  "properly. method {} does not have "
                                                                  "a parameter {}".format(user, method.__name__, name))
                            if _isregex(value):
                                regex = re.compile('^' + value[1:-1] + '$')
                                if not regex.match(args_dict[name]):
                                    raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED,
                                                                      "User {} can call method {} only "
                                                                      "with {} matching pattern {} but called with "
                                                                      "{}={}".format(user, method.__name__, name, value,
                                                                                     name, args_dict[name]))
                            elif args_dict[name] != value:
                                raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED,
                                                                  "User {} can call method {} only "
                                                                  "with {}={} but called with "
                                                                  "{}={}".format(user, method.__name__, name, value,
                                                                                 name, args_dict[name]))

            return method(*args, **kwargs)
        return checked_method

    @spawn
    def _handle_external_rpc_subsystem(self, message):
        ret_msg = dict()
        #_log.debug("EXT_RPC subsystem handler IN message {0}".format(message))
        op = message.args[0]
        rpc_msg = message.args[1] #jsonapi.loads(message.args[1])
        try:
            #_log.debug("EXT_RPC subsystem handler IN message {0}, {1}".format(message.peer, rpc_msg))
            method_args = rpc_msg['args']
            #message.args = [method_args]
            message.args = method_args
            for idx, msg in enumerate(message.args):
                if isinstance(msg, str):
                    message.args[idx] = jsonapi.loads(msg)
            dispatch = self._dispatcher.dispatch
            #_log.debug("External RPC IN message args {}".format(message))

            responses = [response for response in (
                dispatch(msg, message) for msg in message.args) if response]
            #_log.debug("External RPC Responses {}".format(responses))
            if responses:
                message.user = ''
                try:
                    message.peer = ''
                    message.subsystem = 'external_rpc'
                    frames = []
                    op = 'send_platform'
                    frames.append(op)
                    msg = jsonapi.dumps(dict(to_platform=rpc_msg['from_platform'],
                                             to_peer=rpc_msg['from_peer'],
                                             from_platform=rpc_msg['to_platform'],
                                             from_peer=rpc_msg['to_peer'], args=responses))
                    frames.append(msg)
                except KeyError:
                    _log.error("External RPC message did not contain proper message format")
                message.args = jsonapi.dumps(ret_msg)
                #_log.debug("EXT_RPC subsystem handler OUT message {}".format(message))
                try:
                    self.core().connection.send_vip(peer='',
                                                    subsystem='external_rpc',
                                                    args=frames,
                                                    msg_id=message.id,
                                                    user=message.user,
                                                    copy=False)
                except ZMQError as ex:
                    _log.error("ZMQ error: {}".format(ex))
                    pass
        except KeyError:
            pass

    @spawn
    def _handle_subsystem(self, message):
        dispatch = self._dispatcher.dispatch

        if self._message_bus == "rmq":
            for idx, msg in enumerate(message.args):
                if not isinstance(msg, dict):
                    message.args[idx] = jsonapi.loads(msg)

            responses = [response for response in (
                dispatch(msg, message) for msg in message.args) if response]
        else:
            responses = [response for response in (
                dispatch(msg, message) for msg in message.args) if response]
        if responses:
            message.user = ''
            message.args = responses
            try:
                if self._isconnected:
                    if self._message_bus == 'zmq':
                        self.core().connection.send_vip_object(message, copy=False)
                    else:
                        # Agent is running on RMQ message bus.
                        # Adding backward compatibility support for ZMQ. Check if the peer
                        # is running on ZMQ bus. If yes, send RPC message to proxy router
                        # agent to forward using ZMQ message bus connection
                        try:
                            msg_bus = self.peer_list[message.peer]
                        except KeyError:
                            msg_bus = self._message_bus
                        if msg_bus == 'zmq':
                            # If peer connected to ZMQ bus, send via proxy router agent
                            self.core().connection.send_vip_object_via_proxy(message)
                        else:
                            self.core().connection.send_vip_object(message, copy=False)
            except ZMQError as exc:
                if exc.errno == ENOTSOCK:
                    _log.debug("Socket send on non socket {}".format(self.core().identity))

    def _handle_error(self, sender, message, error, **kwargs):
        result = self._outstanding.pop(message.id, None)
        if isinstance(result, AsyncResult):
            result.set_exception(error)
        elif result:
            for result in result:
                result.set_exception(error)

    @dualmethod
    def export(self, method, name=None):
        self._exports[name or method.__name__] = method
        return method

    @export.classmethod
    def export(cls, name=None):   # pylint: disable=no-self-argument
        if name is not None and not isinstance(name, str):
            method, name = name, name.__name__
            annotate(method, set, 'rpc.exports', name)
            return method

        def decorate(method):
            annotate(method, set, 'rpc.exports', name)
            return method
        return decorate

    def batch(self, peer, requests):
        request, results = self._dispatcher.batch_call(requests)
        if results:
            items = weakref.WeakSet(results)
            ident = '%s.%s' % (next(self._counter), id(items))
            for result in results:
                result._weak_set = items   # pylint: disable=protected-access
            self._outstanding[ident] = items
        else:
            ident = ''
        if request:
            if self._isconnected:
                try:
                    self.core().connection.send_vip(peer, 'RPC', [request], msg_id=ident)
                except ZMQError as exc:
                    if exc.errno == ENOTSOCK:
                        _log.debug("Socket send on non socket {}".format(self.core().identity))
        return results or None

    def call(self, peer, method, *args, **kwargs):
        platform = kwargs.pop('external_platform', '')
        request, result = self._dispatcher.call(method, args, kwargs)
        ident = f'{next(self._counter)}.{hash(result)}'
        self._outstanding[ident] = result
        subsystem = None
        frames = []

        if not self._isconnected:
            return

        if self._message_bus == 'zmq':
            if platform == '':#local platform
                subsystem = 'RPC'
                frames.append(request)
            else:
                frames = []
                op = 'send_platform'
                subsystem = 'external_rpc'
                frames.append(op)
                msg = dict(to_platform=platform, to_peer=peer,
                           from_platform='', from_peer='', args=[request])
                frames.append(msg)
                peer = ''

            try:
                # _log.debug("peer: {0}, subsytem: {1}, args:{2}, id: {3}".format(peer, subsystem,
                #                                                                 args, id))
                self.core().connection.send_vip(peer,
                                                subsystem,
                                                args=frames,
                                                msg_id=ident)
            except ZMQError as exc:
                if exc.errno == ENOTSOCK:
                    _log.debug("Socket send on non socket {}".format(self.core().identity))
            # _log.debug("RPC subsystem: External platform RPC msg: {}".format(frames))
        else:
            # Agent running on RMQ message bus.
            # Adding backward compatibility support for ZMQ. Check if peer
            # is running on ZMQ bus. If yes, send RPC message to proxy router agent to
            # forward over ZMQ message bus connection
            try:
                peer_msg_bus = self.peer_list[peer]
            except KeyError:
                peer_msg_bus = self._message_bus
            if peer_msg_bus == 'zmq':
                # peer connected to ZMQ bus, send via proxy router agent
                self.core().connection.send_via_proxy(peer, 'RPC', msg_id=ident, args=[request])
            else:
                self.core().connection.send_vip(peer,
                                                'RPC',
                                                args=[request],
                                                msg_id=ident,
                                                platform=platform)

        return result

    __call__ = call

    def notify(self, peer, method, *args, **kwargs):
        platform = kwargs.pop('external_platform', '')
        request = self._dispatcher.notify(method, args, kwargs)
        frames = []
        if not self._isconnected:
            return

        if self._message_bus == 'zmq':
            subsystem = None
            if platform == '':
                subsystem = 'RPC'
                frames.append(request)
            else:
                op = 'send_platform'
                subsystem = 'external_rpc'
                frames.append(op)
                msg = dict(to_platform=platform, to_peer=peer,
                           from_platform='', from_peer='', args=[request])
                frames.append(msg)
                peer = ''

            try:
                # _log.debug("peer: {0}, subsytem: {1}, args:{2}".format(peer, subsystem,
                #                                                             frames))
                self.core().connection.send_vip(peer,
                                                subsystem,
                                                args=frames)
            except ZMQError as exc:
                if exc.errno == ENOTSOCK:
                    _log.debug("Socket send on non socket {}".format(self.core().identity))
        else:
            # Agent running on RMQ message bus.
            # Adding backward compatibility support for ZMQ. Check if peer
            # is running on ZMQ bus. If yes, send RPC message to proxy router agent to
            # forward over ZMQ message bus connection
            try:
                peer_msg_bus = self.peer_list[peer]
            except KeyError:
                #self.peer_list = self.peerlist_subsystem.list_with_messagebus().get(2)
                #_log.debug("PEERS: {}".format(self.peer_list))
                peer_msg_bus = self._message_bus
            if peer_msg_bus == 'zmq':
                # peer connected to ZMQ bus, send via proxy router agent
                self.core().connection.send_via_proxy(peer,
                                                      'RPC',
                                                      args=[request])
            else:
                self.core().connection.send_vip(peer,
                                                'RPC',
                                                args=[request],
                                                platform=platform)

    @dualmethod
    def allow(self, method, capabilities):
        if isinstance(capabilities, str):
            cap = set([capabilities])
        else:
            cap = set(capabilities)
        self._exports[method.__name__] = self._add_auth_check(method, cap)

    @allow.classmethod
    def allow(cls, capabilities):
        """
        Decorator specifies required agent capabilities to call a method.

        This is designed to be used with the export decorator:

        .. code-block:: python

            @RPC.export
            @RPC.allow('can_read_status')
            def get_status():
                ...

        Multiple capabilities can be provided in a list:
        .. code-block:: python

            @RPC.allow(['can_read_status', 'can_call_my_methods'])

        """
        def decorate(method):
            if isinstance(capabilities, str):
                annotate(method, set, 'rpc.allow_capabilities', capabilities)
            else:
                for cap in capabilities:
                    annotate(method, set, 'rpc.allow_capabilities', cap)
            return method
        return decorate
