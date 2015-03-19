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
'''


import sys
import traceback


__all__ = ['RemoteError', 'JSONRPCError', 'Dispatcher']


UNHANDLED_EXCEPTION = -32000
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _method(ident, method, args, kwargs):
    '''Builds a JSON-RPC request object (dictionary).'''
    request = {'jsonrpc': '2.0', 'method': str(method)}
    if args and kwargs:
        request['params'] = {'*args': args, '**kwargs': kwargs}
    elif args:
        request['params'] = args
    elif kwargs:
        request['params'] = kwargs
    if ident is not None:
        request['id'] = ident
    return request


def _result(ident, result):
    '''Builds a JSON-RPC response object (dictionary).'''
    return {'jsonrpc': '2.0', 'id': ident, 'result': result}


def _error(ident, code, message, **data):
    '''Builds a JSON-RPC error object (dictionary).'''
    error = {'code': code, 'message': message}
    if data:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': ident, 'error': error}


class Error(Exception):
    '''Raised when a recoverable JSON-RPC protocol error occurs.'''
    def __init__(self, code, message, data=None):
        args = (code, message, data) if data is not None else (code, message)
        super(Error, self).__init__(*args)
        self.code = code
        self.message = message
        self.data = data

    def __str__(self):
        try:
            return str(self.data['detail'])
        except (AttributeError, KeyError, TypeError):
            return str(self.message)


class UnimplementedError(Error):
    pass


class RemoteError(Exception):
    """Report the details of an error which occurred remotely.

    message is the JSON-RPC error message. The remaining arguments are
    set from the data element associated with an error code of -32000
    (UNHANDLED_EXCEPTION). exc_type, exc_args, and exc_tb are
    stringified versions of the tuple returned from sys.exc_info() with
    the traceback limited to tb_limit levels.
    """

    def __init__(self, message, exc_type=None,
                 exc_args=None, exc_tb=None, tb_limit=None):
        args = (message,)
        super(RemoteError, self).__init__(*args)
        self.message = message
        self.exc_type = exc_type
        self.exc_args = tuple(exc_args) if exc_args else ()
        self.exc_tb = exc_tb
        self.tb_limit = tb_limit

    def __str__(self):
        return '{}({})'.format(self.exc_type or '<unknown>',
                               ', '.join(repr(arg) for arg in self.exc_args))

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


def make_exception(code, message, data=None):
    '''Return an exception suitable for raising in a caller.'''
    if code == UNHANDLED_EXCEPTION:
        exc_info = data.get('exception.py')
        if exc_info:
            return RemoteError(
                data.get('detail', message), exc_type=exc_info.get('type'),
                exc_args=exc_info.get('args'), exc_tb=exc_info.get('traceback'),
                tb_limit=exc_info.get('tb_limit'))
    elif code == METHOD_NOT_FOUND:
        return UnimplementedError(code, message, data)
    return Error(code, message, data)


class Dispatcher(object):
    '''Parses and directs JSON-RPC 2.0 requests/responses.

    Parses a JSON-RPC message conatained in a dictionary (JavaScript
    object) or a batch of messages (list of dictionaries) and dispatches
    them appropriately.

    The number of frames included in the traceback of a RemoteError can
    be controlled via the traceback_limit property.  Setting
    tramceback_limit to None inidcates an ulimited traceback.  Any other
    integer value will limit the traceback to the given number of frames
    (set to 0, the default, for now traceback).

    Subclasses must implement the serialize and deserialize methods with
    the JSON library of choice. The handle_* methods should also be
    implemented.
    '''

    def __init__(self, traceback_limit=0):
        self.traceback_limit = traceback_limit

    def serialize(self, msg):
        '''Pack a message and return as a JSON string.

        Raise ValueError or subclass on error.
        '''
        raise NotImplementedError()
        #return jsonapi.dumps(msg)

    def deserialize(self, json_string):
        '''Unpack a JSON string and return objects.

        Raise ValueError or subclass on error.
        '''
        raise NotImplementedError()
        #return jsonapi.loads(json_string)

    def dispatch(self, json_string):
        '''Dispatch a JSON-RPC message and return a response or None.'''
        try:
            msg = self.deserialize(json_string)
        except ValueError as exc:
            return self.serialize(_error(
                None, PARSE_ERROR, 'invalid JSON', detail=str(exc)))
        if isinstance(msg, list):
            response = self.dispatch_batch(msg)
        elif isinstance(msg, dict):
            response = self.dispatch_one(msg)
        else:
            response = _error(
                None, INVALID_REQUEST, 'invalid object type',
                detail='expected a list or dictionary (object); '
                       'got a {!r} instead'.format(type(msg).__name__))
        if response:
            try:
                return self.serialize(response)
            except ValueError as exc:
                self.handle_exception(response, None, str(exc))

    def dispatch_batch(self, objects):
        dispatch = self.dispatch_one
        return [x for x in (dispatch(msg) for msg in objects) if x] or None

    def dispatch_one(self, msg):
        try:
            ident = msg.get('id')
        except AttributeError:
            return _error(
                None, INVALID_REQUEST, 'invalid object type',
                detail='expected a dictionary (object); '
                       'got a {!r} instead'.format(type(msg).__name__))
        try:
            version = msg['jsonrpc']
        except KeyError:
            return _error(
                ident, INVALID_REQUEST, 'missing required member',
                detail="missing required 'jsonrpc' member")
        if version != '2.0':
            return _error(
                ident, INVALID_REQUEST, 'unsupported version',
                detail='version 2.0 supported, '
                       'but recieved version {!r}'.format(version))
        if 'error' in msg:
            self._dispatch_error(msg, ident)
        elif 'result' in msg:
            self.handle_result(msg, ident, msg['result'])
        elif 'method' in msg:
            return self._dispatch_method(msg, ident)
        else:
            return _error(
                ident, INVALID_REQUEST, 'missing required member',
                detail='the message type could not be determined because it '
                       "had no 'method', 'result', or 'error' member")

    def handle_method(self, msg, ident, method, args, kwargs):
        raise NotImplementedError()

    def handle_result(self, msg, ident, result):
        pass

    def handle_error(self, msg, ident, code, message, data=None):
        pass

    def handle_exception(self, msg, ident, message):
        pass

    def _dispatch_error(self, msg, ident):
        error = msg['error']
        try:
            code = error['code']
        except TypeError:
            self.handle_exception(
                msg, ident, "expected dict 'error' member; got {} "
                'instead'.format(type(error).__name__))
            return
        except KeyError:
            self.handle_exception(
                msg, ident, "'error' member is missing required 'code' member")
            return
        try:
            message = error['message']
        except KeyError:
            self.handle_exception(
                msg, ident, "'error' member is missing required 'message' member")
        self.handle_error(msg, ident, code, message, error.get('data'))

    def _dispatch_method(self, msg, ident):
        method = str(msg['method'])
        params = msg.get('params', [])
        if isinstance(params, dict):
            try:
                args = params['*args']
                kwargs = params['**kwargs']
            except KeyError:
                args, kwargs = [], params
            else:
                if not isinstance(args, list):
                    return _error(
                        None, INVALID_PARAMS, 'invalid object type',
                        detail='expected a list for *args; '
                               'got a {!r} instead'.format(type(args).__name__))
                if not isinstance(kwargs, dict):
                    return _error(
                        None, INVALID_PARAMS, 'invalid object type',
                        detail='expected a dictionary (object) for **kwargs; '
                               'got a {!r} instead'.format(type(kwargs).__name__))
        elif isinstance(params, list):
            args, kwargs = params, {}
        else:
            return _error(None, INVALID_PARAMS, 'invalid object type',
                          detail='expected a list or dictionary (object); '
                                 'got a {!r} instead'.format(type(params).__name__))
        try:
            result = self.handle_method(msg, ident, method, args, kwargs)
        except NotImplementedError:
            return _error(
                ident, METHOD_NOT_FOUND, 'unimplemented method',
                detail='method {!r} is not implemented'.format(method))
        except Exception:
            if ident is not None:
                exc_type, exc, exc_tb = sys.exc_info()
                exc_class = '{0.__module__}.{0.__name__}'.format(exc_type)
                exc_info = {'type': exc_class, 'args': exc.args}
                data = {'detail': str(exc), 'exception.py': exc_info}
                if self.traceback_limit is None:
                    exc_info['traceback'] = traceback.format_tb(exc_tb)
                elif self.traceback_limit:
                    exc_info['tb_limit'] = self.traceback_limit
                    exc_info['traceback'] = traceback.format_tb(
                        exc_tb, self.traceback_limit)
                return _error(ident, UNHANDLED_EXCEPTION,
                              'unhandled exception', **data)
        else:
            if ident is not None:
                return _result(ident, result)

