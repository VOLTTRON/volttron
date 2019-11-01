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

"""Implementation of JSON-RPC 2.0 with support for bi-directional calls.

See http://www.jsonrpc.org/specification for the complete specification.
"""

import sys
from contextlib import contextmanager

from volttron.platform import jsonapi

__all__ = ['Error', 'MethodNotFound', 'RemoteError', 'Dispatcher',
           'json_result', 'json_validate_request', 'json_validate_response']


PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# implementation-defined server-errors:
UNHANDLED_EXCEPTION = -32000
UNAUTHORIZED = -32001
UNABLE_TO_REGISTER_INSTANCE = -32002
DISCOVERY_ERROR = -32003
UNABLE_TO_UNREGISTER_INSTANCE = -32004
UNAVAILABLE_PLATFORM = -32005
UNAVAILABLE_AGENT = -32006


def json_validate_request(jsonrequest):
    assert jsonrequest.get('id', None)
    assert jsonrequest.get('jsonrpc', None) == '2.0'
    assert jsonrequest.get('method', None)


def json_validate_response(jsonresponse):
    assert jsonresponse.get('id', None)
    assert jsonresponse.get('jsonrpc', None) == '2.0'
    result = jsonresponse.get('result', None)
    # if result is null then there is no result so we check to see if we have
    # an error.  If error is also None then this is an invalid response.
    if result is None:
        assert jsonresponse.get('error', None)


def json_method(ident, method, args, kwargs):
    """Builds a JSON-RPC request object (dictionary)."""
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


def json_result(ident, result):
    """Builds a JSON-RPC response object (dictionary)."""
    return {'jsonrpc': '2.0', 'id': ident, 'result': result}


def json_error(ident, code, message, **data):
    """Builds a JSON-RPC error object (dictionary)."""
    error = {'code': code, 'message': message}
    if data:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': ident, 'error': error}


class ParseError(Exception):
    pass


class JsonRpcData(object):
    """ A `JsonRpcData` reprepresents the data associated with an rpc request.
    """
    def __init__(self, id, version, method, params, authorization):
        self.id = id
        self.version = version
        self.method = method
        self.params = params
        self.authorization = authorization

    @staticmethod
    def parse(jsonstr):
        # Allow parse to handle dictionary data instead
        # of just string data.
        if isinstance(jsonstr, dict):
            data = jsonstr.copy()
        else:
            data = jsonapi.loads(jsonstr)
        id = data.get('id', None)
        version = data.get('jsonrpc', None)
        method = data.get('method', None)
        params = data.get('params', None)
        authorization = data.get('authorization', None)

        if id == None:
            raise ParseError("Invalid id")
        if version != '2.0':
            print("VERSION IS: {}".format(version))
            raise ParseError('Invalid jsonrpc version')
        if method == None:
            raise ParseError('Method not specified.')

        return JsonRpcData(id, version, method, params, authorization)


class Error(Exception):
    """Raised when a recoverable JSON-RPC protocol error occurs."""
    def __init__(self, code, message, data=None):
        args = (code, message, data) if data is not None else (code, message)
        super(Error, self).__init__(*args)   # pylint: disable=star-args
        self.code = code
        self.message = message
        self.data = data

    def __str__(self):
        try:
            return str(self.data['detail'])
        except (AttributeError, KeyError, TypeError):
            return str(self.message)


class MethodNotFound(Error):
    """Raised when remote method is not implemented."""
    pass


class RemoteError(Exception):
    """Report the details of an error which occurred remotely.

    Instances of this exception are usually created by
    exception_from_json(), which uses the 'detail' element of the
    JSON-RPC error for message, if it is set, otherwise the JSON-RPC
    error message.  The exc_info argument is set from the 'exception.py'
    element associated with an error code of -32000
    (UNHANDLED_EXCEPTION). Typical keys in exc_info are exc_type,
    exc_args, and exc_tb (if tracebacks are allowed) which are
    stringified versions of the tuple returned from sys.exc_info().
    """

    def __init__(self, message, **exc_info):
        if exc_info:
            try:
                exc_type = exc_info['exc_type']
                exc_args = exc_info['exc_args']
            except KeyError:
                msg = message
            else:
                args = ', '.join(repr(arg) for arg in exc_args)
                msg = '%s(%s)' % (exc_type, args)
        super(RemoteError, self).__init__(msg)
        self.message = message
        self.exc_info = exc_info

    def __repr__(self):
        exc_type = self.exc_info.get('exc_type', '<unknown>')
        try:
            exc_args = ', '.join(repr(arg) for arg in
                                 self.exc_info['exc_args'])
        except KeyError:
            exc_args = '...'
        return '%s(%s)' % (exc_type, exc_args)

    def print_tb(self, file=sys.stderr):
        """Pretty print the traceback in the standard format."""
        exc_type = self.exc_info.get('exc_type', '<unknown>')
        file.write('Remote Traceback (most recent call last):\n')
        try:
            exc_tb = self.exc_info['exc_tb']
        except KeyError:
            file.write('  (traceback omitted)\n')
        else:
            file.write(''.join(exc_tb))
        file.write('%s: %s\n' % (exc_type, self.message))



def exception_from_json(code, message, data=None):
    """Return an exception suitable for raising in a caller."""
    if code == UNHANDLED_EXCEPTION:
        return RemoteError(data.get('detail', message),
                           **data.get('exception.py', {}))
    elif code == METHOD_NOT_FOUND:
        return MethodNotFound(code, message, data)
    return Error(code, message, data)


class Dispatcher(object):
    """Parses and directs JSON-RPC 2.0 requests/responses.

    Parses a JSON-RPC message conatained in a dictionary (JavaScript
    object) or a batch of messages (list of dictionaries) and dispatches
    them appropriately.

    Subclasses must implement the serialize and deserialize methods with
    the JSON library of choice. The exception, result, error, method and
    batch handling methods should also be implemented.
    """

    def serialize(self, json_obj):
        """Pack compatible Python objects into and return JSON string."""
        raise NotImplementedError()

    def deserialize(self, json_string):
        """Unpack a JSON string and return Python object(s)."""
        raise NotImplementedError()

    def batch_call(self, requests):
        """Create and return a request for a batch of method calls.

        requests is an iterator of lists or tuples with 4 items each:
        ident, method, args, kwargs. These are the same 4 arguments
        required by the call() method. The first (ident) element may be
        None to indicate a notification.
        """
        return self.serialize([json_method(ident, method, args, kwargs)
                               for ident, method, args, kwargs in requests])

    def call(self, ident, method, args=None, kwargs=None):
        """Create and return a request for a single method call."""
        return self.serialize(json_method(
            ident, method, args or (), kwargs or {}))

    def notify(self, method, args=None, kwargs=None):
        """Create and return a request for a single notification."""
        return self.serialize(json_method(
            None, method, args or (), kwargs or {}))

    def exception(self, response, ident, message, context=None):
        """Called for response errors.

        Typically called when a response, such as an error, does not
        contain all the necessary members and sending an error to the
        remote peer is not possible. Also called when serializing a
        response fails.
        """
        pass

    def result(self, response, ident, result, context=None):
        """Called when a result response is received."""
        pass

    def error(self, response, ident, code, message, data=None, context=None):
        """Called when an error resposne is received."""
        pass

    def method(self, request, ident, name, args, kwargs,
               batch=None, context=None):
        """Called to get make method call and return results.

        request is the original JSON request (as dict). name is the name
        of the method requested. Only one of args or kwargs will contain
        parameters. If method is being executed as part of a batch
        request, batch will be the value returned from the batch()
        context manager.

        This method should raise NotImplementedError() if the method is
        unimplemented. Otherwise, it should return the result of the
        method call or raise an exception. If the raised exception has a
        traceback attribute, which should be a string (if set), it will
        be sent back in the returned error. An exc_info attribute may
        also be set which must be a dictionary and will be used as the
        basis for the exception.py member of the returned error.
        """
        raise NotImplementedError()

    @contextmanager
    def batch(self, request, context=None):
        """Context manager for batch requests.

        Entered before processing a batch request and exited afterward.
        """
        # pylint: disable=unused-argument
        yield

    def dispatch(self, message: (dict, list), context: str = None):
        """Dispatch a JSON-RPC message and return a response or None."""
        if isinstance(message, list):
            dispatch = self._dispatch_one
            with self.batch(message) as batch:
                responses = (dispatch(msg, batch, context) for msg in message)
                response = [response for response in responses if response]
        elif isinstance(message, dict):
            response = self._dispatch_one(message, None, context)
        else:
            response = json_error(
                None, INVALID_REQUEST, 'invalid object type',
                detail='expected a list or dictionary (object); '
                       'got a {!r} instead'.format(type(message).__name__))
        if response:
            try:
                return self.serialize(response)
            except ValueError as exc:
                self.exception(response, None, str(exc), context=context)

    def _dispatch_one(self, msg, batch, context):
        """Dispatch a single JSON-RPC message."""
        try:
            ident = msg.get('id')
        except AttributeError:
            return json_error(None, INVALID_REQUEST, 'invalid object type',
                              detail='expected a dictionary (object); '
                              'got a {!r} instead'.format(type(msg).__name__))
        try:
            version = msg['jsonrpc']
        except KeyError:
            return json_error(ident, INVALID_REQUEST, 'missing required member',
                              detail="missing required 'jsonrpc' member")
        if version != '2.0':
            return json_error(ident, INVALID_REQUEST, 'unsupported version',
                              detail='version 2.0 supported, '
                              'but recieved version {!r}'.format(version))
        if 'error' in msg:
            error = msg['error']
            try:
                code = error['code']
            except TypeError:
                self.exception(
                    msg, ident, "expected dict 'error' member; got "
                    '{} instead'.format(type(error).__name__), context=context)
                return
            except KeyError:
                self.exception(
                    msg, ident, "'error' member is missing 'code' member",
                    context=context)
                return
            try:
                message = error['message']
            except KeyError:
                self.exception(
                    msg, ident, "'error' member is missing 'message' member",
                    context=context)
                return
            self.error(msg, ident, code, message, error.get('data'),
                       context=context)
        elif 'result' in msg:
            self.result(msg, ident, msg['result'], context=context)
        elif 'method' in msg:
            name = str(msg['method'])
            params = msg.get('params')
            if isinstance(params, list):
                args, kwargs = params, {}
            elif isinstance(params, dict):
                args, kwargs = (), params
            elif params is None:
                args, kwargs = (), {}
            else:
                return json_error(
                    None, INVALID_PARAMS, 'invalid object type',
                    detail='expected a list or dictionary (object); '
                           'got a {!r} instead'.format(type(params).__name__))
            try:
                result = self.method(msg, ident, name, args, kwargs,
                                     batch=batch, context=context)
            except NotImplementedError:
                if ident is None:
                    return
                return json_error(
                    ident, METHOD_NOT_FOUND, 'unimplemented method',
                    detail='method {!r} is not implemented'.format(name))
            except Exception as exc:   # pylint: disable=broad-except
                if ident is None:
                    return
                exc_info = getattr(exc, 'exc_info', {})
                if 'exc_type' not in exc_info:
                    exc_type = type(exc)
                    if exc_type.__module__ == 'exceptions':
                        exc_info['exc_type'] = exc_type.__name__
                    else:
                        exc_info['exc_type'] = '.'.join(
                            [exc_type.__module__, exc_type.__name__])
                if 'exc_args' not in exc_info:
                    try:
                        exc_info['exc_args'] = exc.args
                    except AttributeError:
                        pass
                error = {'detail': str(exc), 'exception.py': exc_info}
                return json_error(ident, UNHANDLED_EXCEPTION,   # pylint: disable=star-args
                                  'unhandled exception', **error)
            if ident is not None:
                return json_result(ident, result)
