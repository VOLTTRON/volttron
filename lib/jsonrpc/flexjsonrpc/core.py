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
#}}}

'''Implementation of JSON-RPC 2.0 with support for bi-directional calls.

See http://www.jsonrpc.org/specification for the complete specification.

The py extension are added to make using JSON-RPC more Python friendly,
including setting and getting properties, calling functions with *args
and/or **kwargs, and advanced exception handling.  See the BaseHandler
and Dispatcher classes for more information.
'''

import logging
import sys
from threading import _Event
import traceback
import weakref


__all__ = ['RemoteError', 'Disconnected', 'Timeout', 'JSONRPCError',
           'parse_error', 'private', 'BaseHandler', 'Dispatcher',
           'Requester', 'PyConnector', 'Connector']


UNHANDLED_EXCEPTION = -32000
PYTHON_EXCEPTION = -32001
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class RemoteError(Exception):
    """Report the details of an error which occurred remotely.
    
    message is the JSON-RPC error message.  The remaining arguments are
    set from the data element associated with an error code of -32001
    (PYTHON_EXCEPTION).  exc_type, exc_args, and exc_tb are stringified
    versions of the tuple returned from sys.exc_info() with the
    traceback limited to tb_limit levels.
    """

    def __init__(self, message, exc_type=None, exc_args=None, exc_tb=None,
                 tb_limit=None):
        self.message = message
        self.args = (message,)
        self.exc_type = exc_type or None
        self.exc_args = tuple(exc_args) if exc_args else ()
        self.exc_tb = exc_tb
        self.tb_limit = tb_limit

    def __str__(self):
        return '{}({})'.format(self.exc_type or '<unknown>',
                ', '.join(map(repr, self.exc_args)))

    def print_tb(self, file=sys.stderr):
        '''Pretty print the traceback in the standard format.'''
        if self.tb_limit is not None:
            limit = ', limited to {} frames'.format(self.tb_limit)
        else:
            limit = ''
        file.write('Remote Traceback (most recent call last{}):\n'.format(limit))
        if self.exc_tb:
            file.write(''.join(self.exc_tb))
        file.write('{}: {}\n'.format(self.exc_type or '<unknown>', self.message))


class Disconnected(Exception):
    '''Raised on threads with outstanding requests on a disconnect.'''


class Timeout(Exception):
    '''Raised on synchronous requests that timeout.'''


class JSONRPCError(Exception):
    '''Raised when a recoverable JSON-RPC protocol error occurs.'''
    def __init__(self, code, message, data=None):
        args = (code, message, data) if data is not None else (code, message)
        super(JSONRPCError, self).__init__(*args)
        self.code = code
        self.message = message
        if data is not None:
            self.data = data


def _request(ident, method, params=None):
    '''Builds a JSON-RPC request object (dictionary).'''
    request = {'jsonrpc': '2.0', 'method': str(method)}
    if params:
        request['params'] = params
    if ident is not None:
        request['id'] = ident
    return request

def _response(ident, result, error=None):
    '''Builds a JSON-RPC response object (dictionary).'''
    response = {'jsonrpc': '2.0', 'id': ident}
    if error is not None:
        response['error'] = error
    else:
        response['result'] = result
    return response

def _error(ident, code, message, data=None):
    '''Builds a JSON-RPC error object (dictionary).'''
    error = {'code': code, 'message': message}
    if data:
        error['data'] = data
    return _response(ident, None, error)


def parse_error(msg=None):
    '''Builds and returns a JSON-RPC parse error response (dictionary).'''
    return _error(None, PARSE_ERROR, 'parse error', msg)


def private(method):
    '''Mark a RPC handler method as being private.'''
    method.is_private = True
    return method


class BaseHandler(object):
    '''Base class for defining exported RPC methods and properties.

    This RPC handler make use of four special Python extensions by
    appending the extension name to the front of the attribute name
    separated by a '.':
        
        py.get - call the getter on an object's property
        py.set - call the setter on an object's property
        py.delete - call the deleter on an object's property
        py.apply - call a method on the object with *args and **kwargs

    If no extension is used, the standard JSON-RPC calling convention is
    assumed.

    Only class and instance methods and properties (using descriptors)
    are accessible via the __call__ method, which is used to lookup and
    return the appropriate method given the method name.  Attributes can
    be marked private by prefixing them with at least one underscore
    (_).  Methods may additionally be marked private by using the
    private() decorator or by setting an is_private attribute on the
    method to True.  Properties may additionally become private by not
    using a descriptor to wrap access.
    '''

    def __call__(self, method_name):
        try:
            ext, name = method_name.split('.', 1)
        except ValueError:
            ext, name = None, method_name
        if ext == 'py':
            try:
                op, name = name.split('.', 1)
            except ValueError:
                raise AttributeError(
                        'missing py extension operator: {!r}'.format(method_name))
            try:
                attr = getattr(self.__class__, name)
            except AttributeError:
                raise AttributeError('unknown attribute: {!r}'.format(name))
            if name.startswith('_') or getattr(attr, 'is_private', False):
                raise AttributeError('unknown attribute: {!r}'.format(name))
            if op == 'get':
                try:
                    fget = getattr(attr, '__get__')
                except AttributeError:
                    raise AttributeError("can't get property: {!r}".format(name))
                def getter():
                    try:
                        return fget(self)
                    except AttributeError:
                        raise AttributeError("can't get property: {!r}".format(name))
                getter.__name__ = name
                return getter
            elif op == 'set':
                try:
                    fset = getattr(attr, '__set__')
                except AttributeError:
                    raise AttributeError("can't set property: {!r}".format(name))
                def setter(value):
                    try:
                        fset(self, value)
                    except AttributeError:
                        raise AttributeError("can't set property: {!r}".format(name))
                setter.__name__ = name
                return setter
            elif op == 'delete':
                try:
                    fdelete = getattr(attr, '__delete__')
                except AttributeError:
                    raise AttributeError("can't delete property: {!r}".format(name))
                def deleter():
                    try:
                        fdelete(self)
                    except AttributeError:
                        raise AttributeError("can't delete property: {!r}".format(name))
                deleter.__name__ = name
                return deleter
            elif op == 'apply':
                try:
                    fcall = getattr(attr, '__call__')
                    if attr.im_self is not None:
                        return fcall
                except AttributeError:
                    raise AttributeError("can't call method: {!r}".format(name))
                return lambda args, kwargs: fcall(self, *args, **kwargs)
            raise AttributeError('unknown py extension operator: {!r}'.format(op))
        else:
            name = method_name
        try:
            attr = getattr(self.__class__, name)
            if name.startswith('_') or getattr(attr, 'is_private', False):
                raise AttributeError
            fcall = attr.__call__
            if attr.im_self is not None:
                return fcall
            return lambda *args, **kwargs: fcall(self, *args, **kwargs)
        except AttributeError:
            pass
        raise AttributeError('unknown method: {!r}'.format(name))


def one_param(args, kwargs):
    if args and kwargs:
        raise ValueError('mixed positional and keyword arguments; '
                         'use all positional or all keyword, but not both')
    return args or kwargs or None


def make_proxy(func, name, py_ext, **fnargs):
    if py_ext:
        fn = lambda *args, **kwargs: func(
                'py.apply.' + name, [args, kwargs], **fnargs)
    else:
        fn = lambda *args, **kwargs: func(
                name, one_param(args, kwargs), **fnargs)
    fn.__name__ = name
    return fn



class NotifyProxy(object):
    '''Proxy a notification request.'''

    __slots__ = ['state']

    def __init__(self, notify, py_ext=True):
        super(NotifyProxy, self).__setattr__('state', (notify, py_ext))
    
    def __getattribute__(self, name):
        notify, py_ext = super(NotifyProxy, self).__getattribute__('state')
        return make_proxy(notify, name, py_ext)


class AsyncProxy(object):
    __slots__ = ['state']

    def __init__(self, async_request, callback=None, py_ext=True):
        super(AsyncProxy, self).__setattr__(
                'state', (async_request, callback, py_ext))
    
    def __call__(self, callback):
        async_request, _, py_ext = super(
                AsyncProxy, self).__getattribute__('state')
        return AsyncProxy(async_request, callback, py_ext)

    def __getattribute__(self, name):
        async_request, callback, py_ext = super(
                AsyncProxy, self).__getattribute__('state')
        if callback is None:
            raise ValueError('no callback set')
        func = lambda *args, **kwargs: async_request(callback, *args, **kwargs)
        return make_proxy(func, name, py_ext)


class SyncProxy(object):
    __slots__ = ['state']

    def __init__(self, sync_call, timeout=None, py_ext=True):
        super(SyncProxy, self).__setattr__('state', (sync_call, timeout, py_ext))
    
    def __call__(self, timeout):
        sync_call, _, py_ext = super(SyncProxy, self).__getattribute__('state')
        return SyncProxy(sync_call, timeout, py_ext)
    
    def __getattribute__(self, name):
        sync_call, timeout, py_ext = super(SyncProxy, self).__getattribute__('state')
        return make_proxy(sync_call, name, py_ext, timeout=timeout)


class PropProxy(object):
    __slots__ = ['state']

    def __init__(self, sync_call, timeout=None):
        super(PropProxy, self).__setattr__('state', (sync_call, timeout))

    def __call__(self, timeout):
        sync_call, _ = super(PropProxy, self).__getattribute__('state')
        return PropProxy(sync_call, timeout)

    def __getattribute__(self, name):
        sync_call, timeout = super(PropProxy, self).__getattribute__('state')
        return sync_call('py.get.' + name, timeout=timeout)

    def __setattr__(self, name, value):
        sync_call, timeout = super(PropProxy, self).__getattribute__('state')
        sync_call('py.set.' + name, [value], timeout=timeout)

    def __delattr__(self, name):
        sync_call, timeout = super(PropProxy, self).__getattribute__('state')
        sync_call('py.delete.' + name, timeout=timeout)


class Dispatcher(object):
    '''Parses and directs JSON-RPC 2.0 requests/responses.

    Parses a JSON-RPC message conatained in a JavaScript object-like
    (dictionary) or a batch of messages (list of dictionaries) and
    dispatches them appropriately.  Exported methods are looked up via
    the function passed in as lookup_method and responses are returned
    using the function passed in as response_callback.

    A server must provide a lookup_method function and clients must
    provide a response_callback function.  A client or server wishing to
    call remote functions and export functions to a remote endpoint
    must implement both.

    lookup_method is a function which takes a method name as its only
    parameter and either raises an AttributeError exception, if the
    named method does not exist, or returns the function to be called.

    response_callback will be called with errors and results from remote
    calls.  The first and only positional parameter is the identity used
    in the request.  If the response is an error, the error keyword
    parameter will be set to an instance of RemoteError or JSONRPCError.
    Otherwise, the remote call succeeded and the result keyword
    parameter will be set to the result.  Return values are ignored.

    The number of frames included in the traceback of a RemoteError can
    be controlled via the traceback_limit property.  Setting
    tramceback_limit to None inidcates an ulimited traceback.  Any other
    integer value will limit the traceback to the given number of
    frames.
    '''

    traceback_limit = 20

    __slots__ = ['response_callback', 'lookup_method']

    def __init__(self, lookup_method=None, response_callback=None):
        # one of lookup_method or response_callback must be set
        assert lookup_method is not None or response_callback is not None
        self.lookup_method = lookup_method
        self.response_callback = response_callback

    def dispatch(self, obj):
        '''Dispatch a JSON-RPC message and return a response or None.'''
        if isinstance(obj, list):
            return self._dispatch_batch(obj)
        elif isinstance(obj, dict):
            return self._dispatch_one(obj)
        return _error(None, INVALID_REQUEST,
                'unknown request type', 'a list or dictionary (object) was '
                'expected; got a {} instead'.format(type(obj).__name__))

    def _dispatch_batch(self, objects):
        return [result for result in
                map(self._dispatch_batch_item, objects) if result]

    def _dispatch_batch_item(self, obj):
        if not isinstance(obj, dict):
            return _error(None, INVALID_REQUEST, 'unknown request type',
                    'a dictionary was expected; got a {} instead'.format(
                            type(obj).__name__))
        return self._dispatch_one(obj)

    def _dispatch_one(self, obj):
        ident = obj.get('id')
        try:
            if obj['jsonrpc'] != '2.0':
                return _error(ident, INVALID_REQUEST,
                        'unknown jsonrpc version',
                        'the server uses jsonrpc version 2.0 but recieved '
                        'a version {!r} message'.format(obj['jsonrpc']))
        except KeyError:
            return _error(ident, INVALID_REQUEST,
                    'missing jsonrpc version', '"jsonrpc" is a required member'
                    'of the message, but it was missing')
        if 'error' in obj:
            return self._dispatch_error(ident, obj['error'])
        elif 'result' in obj:
            return self._dispatch_result(ident, obj['result'])
        elif 'method' in obj:
            return self._dispatch_request(ident, obj['method'], obj.get('params'))
        else:
            return _error(ident, INVALID_REQUEST, 'unknown message type',
                    'the message type could not be determined because it '
                    'had no "method", "result", or "error" member')

    def _dispatch_error(self, ident, error):
        try:
            code = error['code']
        except TypeError:
            raise JSONRPCError(INVALID_REQUEST, 'invalid error response',
                    "expected dict as response error member, got {} instead".format(
                            type(error).__name__))
        except KeyError:
            raise JSONRPCError(INVALID_REQUEST, 'invalid error response',
                    "response error member is missing required code member")
        try:
            message = error['message']
        except KeyError:
            raise JSONRPCError(INVALID_REQUEST, 'invalid error response',
                    "response error member is missing required message member")
        if code == PYTHON_EXCEPTION:
            exc = RemoteError(message, **error.get('data', {}))
        else:
            exc = JSONRPCError(code, message, error.get('data'))
        if self.response_callback is not None:
            self.response_callback(ident, error=exc)

    def _dispatch_result(self, ident, result):
        if self.response_callback is not None:
            self.response_callback(ident, result=result)

    def _dispatch_request(self, ident, method_name, params=None):
        if params is not None and not isinstance(params, (list, dict)):
            return _error(ident, INVALID_PARAMS, 'incorrect params type',
                    'params must be a list or dictionary; got {!r} '
                    'instead'.format(type(params).__name__))
        method_name = str(method_name)
        if method_name.startswith('rpc.'):
            return _error(ident, METHOD_NOT_FOUND,
                              'no RPC extensions are implemented')
        if self.lookup_method is None:
            return _error(ident, METHOD_NOT_FOUND, 'method not found',
                          'no methods are exported')
        try:
            method = self.lookup_method(method_name)
        except AttributeError as e:
            return _error(ident, METHOD_NOT_FOUND, 'method not found', str(e))
        try:
            if params is None:
                result = method()
            elif isinstance(params, list):
                result = method(*params)
            else:
                result = method(**params)
        except Exception as e:
            if ident is None:
                return
            if not method_name.startswith('py.'):
                return _error(ident, UNHANDLED_EXCEPTION, 'unhandled exception', str(e))
            exc_type, exc, tb = sys.exc_info()
            data = {'exc_type': '.'.join((exc_type.__module__, exc_type.__name__)),
                    'exc_args': exc.args}
            if self.traceback_limit is None:
                data['exc_tb'] = traceback.format_tb(tb)
            elif self.traceback_limit:
                data['tb_limit'] = self.traceback_limit
                data['exc_tb'] = traceback.format_tb(tb, self.traceback_limit)
            return _error(ident, PYTHON_EXCEPTION, str(exc), data)
        if ident is not None:
            return _response(ident, result)


class Requester(object):
    '''Object used to initiate JSON-RPC requests to a remote host.

    The send_request method, initialized on construction, must accept a
    single parameter, a Python dictionary representing a JSON-RPC
    request.  It is the responsibility of this function, or some later
    function, to convert the Python object into a JSON-encoded string
    before transmitting.
    '''

    __slots__ = ['send_request', '_requests']

    class SyncRequest(_Event):
        '''Synchronous request synchronisation event.

        Returned from a synchronous remote call.  Inherits from
        threading.Event.  Will become set when the remote call returns.
        If the error property is not None, it will contain the returned
        exception.  Otherwise, the result property contains the result.
        '''

        __slots__ = ['result', 'error']

        def __call__(self, **kwargs):
            self.error = kwargs.get('error')
            self.result = kwargs.get('result')
            self.set()

        def wait(self, timeout=None):
            '''Overrides threading.Event to allow interruption.'''
            if timeout is not None:
                return super(Requester.SyncRequest, self).wait(timeout)
            while not super(Requester.SyncRequest, self).wait(360):
                pass
            return True

    def __init__(self, send):
        self.send_request = send
        self._requests = weakref.WeakValueDictionary()

    def shutdown(self):
        '''Send Disconnected() error for all outstanding requests.'''
        for ident in self._requests.keys():
            self.handle_response(ident, error=Disconnected())

    def handle_response(self, ident, **kwargs):
        '''Called by dispatcher when a response is received.'''
        callback = self._requests.pop(ident, None)
        if callback is not None:
            callback(**kwargs)

    def notify(self, method, params=None):
        '''Send a notify request and return immediately.'''
        self.send_request(_request(None, method, params))

    def async_request(self, callback, method, params=None):
        '''Call a remote procedure asynchronously.

        Register the given callback to be called when the response is
        received and call the named method with the given parameters.
        The callback must be unique as it is used to derive the request
        ID.  A reference to the callback must be retained until the
        response is received or the entry may be removed from the
        WeakValueDictionary.  It will be called with either the error or
        result keyword parameter set to indicate an error or return the
        result.
        '''
        ident = '{:x}'.format(id(callback))
        self._requests[ident] = callback
        try:
            self.send_request(_request(ident, method, params))
        except:
            self._requests.pop(ident, None)
            raise

    def sync_request(self, method, params=None):
        '''Call a remote procedure asynchronously and return a wait event.

        Returns a SyncRequest object that can be used to either wait or
        poll for request completion.  See SyncRequest for more
        information.
        '''
        request = self.SyncRequest()
        self.async_request(request, method, params)
        return request
    
    def sync_call(self, method, params=None, timeout=None):
        '''Call a remote procedure synchronously and return the result.
        
        If timeout is None and a response is not received within the
        given time limit, a Timeout exception is raised.  If an error is
        returned from the remote call, an exception is raised.
        Otherwise, the result is returned.
        '''
        request = self.sync_request(method, params)
        if not request.wait(timeout):
            raise Timeout()
        if request.error is not None:
            raise request.error
        return request.result


class PyConnector(object):
    '''Provide easy proxy access to a Requester object.

    Allows calling of methods or accessing of properties using a Pythonic
    interface.  Here are a few examples:

        conn = PyConnector(requester)
        conn.notify.ready()
        new_value = conn.prop.some_value
        conn.call.set_new_value(new_value + 5, minimum=15)
    '''
    def __init__(self, requester):
        self.requester = requester

    @property
    def call(self):
        '''Call a remote method synchronously.

        Call the property directly with a float to set the timeout
        and get any attribute to return a proxy for that method.

        For instance, conn.call(5).hello(), calls the remote method
        named hello with a 5 second timeout.
        '''
        return SyncProxy(self.requester.sync_call)

    def method(self, callback):
        '''Call a remote method asynchronously.
        
        Upon receiving the response, the callback will be called with
        the appropriate keyword arguments set.  As with
        Requester.async_request, the callback must be unique.
        '''
        return AsyncProxy(self.requester.async_request, callback)

    @property
    def notify(self):
        '''Send a notification.'''
        return NotifyProxy(self.requester.notify)

    @property
    def prop(self):
        '''Get, set, or delete a remote property.

        As with call(), a timeout may be set by calling the property
        directly. The resulting proxy can be manipulated as a standard
        property.

            call.prop(15).period = 5
            period = call.prop.period
            del call.prop.period
        '''
        return PropProxy(self.requester.sync_call)


class Connector(object):
    '''Provide easy proxy access to a Requester object.

    The Connector object is used with systems not implementing the
    python extensions.

    See PyConnector for more information.
    '''
    def __init__(self, requester):
        self.requester = requester

    @property
    def call(self):
        '''Call a remote method synchronously.'''
        return SyncProxy(self.requester.sync_call, py_ext=False)

    def method(self, callback):
        '''Call a remote method asynchronously.'''
        return AsyncProxy(self.requester.async_request, callback, py_ext=False)

    @property
    def notify(self):
        '''Send a notification.'''
        return NotifyProxy(self.requester.notify, py_ext=False)


# vim: sts=4 sw=4 et:
