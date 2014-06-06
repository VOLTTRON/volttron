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

import sys
import traceback

from flexjsonrpc import core as jsonrpc


class TestHandler(object):
    class Handler(jsonrpc.BaseHandler):
        unaccessable = "cannot access non-property attributes"
        def _priv(self):
            return "I'm private!"
        @jsonrpc.private
        def priv(self):
            return "I'm private, too!"
        def sum(self, *args, **kwargs):
            return kwargs.pop('msg') + str(sum(args))
        @classmethod
        def clsmethod(cls):
            return "I'm a class method"
        @staticmethod
        def static():
            return "static"
        @property
        def read_only(self):
            return "I'm read-only."
        @property
        def read_write(self):
            return self.read_write_value
        @read_write.setter
        def read_write(self, value):
            self.read_write_value = value
        @property
        def full_access(self):
            return self.full_access_value
        @full_access.setter
        def full_access(self, value):
            self.full_access_value = value
        @full_access.deleter
        def full_access(self):
            del self.full_access_value

    def setup(self):
        self.handler = self.Handler()

    def _test_exception(self, name, prefix, *args, **kwargs):
        try:
            self.handler(name)(*args, **kwargs)
        except AttributeError as e:
            assert str(e).startswith(prefix), "{!r} doesn't start with {!r}".format(str(e), prefix)
        else:
            assert False

    def _test_unknown_method(self, name, *args, **kwargs):
        self._test_exception(name, 'unknown method: ', *args, **kwargs)

    def _test_py_extension(self, name, prefix, *args, **kwargs):
        self._test_exception(name, prefix + ' py extension operator: ', *args, **kwargs)

    def _test_unknown_attribute(self, name, *args, **kwargs):
        self._test_exception(name, 'unknown attribute: ', *args, **kwargs)

    def _test_py_property(self, name, *args, **kwargs):
        op = name.split('.', 2)[1]
        self._test_exception(name, "can't {} property".format(op), *args, **kwargs)

    def _test_py_method(self, name, *args, **kwargs):
        self._test_exception(name, "can't call method", *args, **kwargs)

    def test_public_method(self):
        assert self.handler('sum')(1, 2, 3, msg='The sum is ') == 'The sum is 6'

    def test_implicit_private_method(self):
        self._test_unknown_method('_priv')

    def test_explicit_private_method(self):
        self._test_unknown_method('priv')

    def test_improperly_accessed_property(self):
        self._test_unknown_method('read_only')

    def test_class_method(self):
        assert self.handler('clsmethod')() == "I'm a class method"

    def test_static_method(self):
        self._test_unknown_method('static')

    def test_instance_function(self):
        self.handler.func = lambda: 'foo'
        self._test_unknown_method('func')

    def test_unnaccessable_property(self):
        self._test_unknown_method('unaccessable')

    def test_unknown_extension(self):
        self._test_unknown_method('ext.clsmethod')

    def test_missing_py_operator(self):
        self._test_py_extension('py.', 'missing')

    def test_unknown_py_operator(self):
        self._test_py_extension('py.push.clsmethod', 'unknown')

    def test_missing_py_attribute(self):
        self._test_unknown_attribute('py.get.')

    def test_unknown_py_attribute(self):
        self._test_unknown_attribute('py.get.unknown')

    def test_implicit_private_py_attribute(self):
        self._test_unknown_attribute('py.get._priv')

    def test_explicit_private_py_attribute(self):
        self._test_unknown_attribute('py.get.priv')

    def test_unaccessable_py_attribute(self):
        self._test_py_property('py.get.unaccessable')

    def test_read_only_py_property(self):
        self.handler('py.get.read_only')() == "I'm read-only!"
        self._test_py_property('py.set.read_only', 'value')
        self._test_py_property('py.delete.read_only')

    def test_read_write_py_property(self):
        self._test_py_property('py.get.read_write')
        self.handler('py.set.read_write')('new value')
        self.handler('py.get.read_write')() == 'new value'
        self._test_py_property('py.delete.read_write')
        self.handler('py.get.read_write')() == 'new value'

    def test_full_access_py_property(self):
        self._test_py_property('py.get.full_access')
        self.handler('py.set.full_access')('new value')
        self.handler('py.get.full_access')() == 'new value'
        self.handler('py.delete.full_access')()
        self._test_py_property('py.get.full_access')

    def test_call_py_method(self):
        assert self.handler('py.apply.sum')([1, 2, 3], {'msg': 'Sum = '}) == 'Sum = 6'

    def test_call_py_class_method(self):
        assert self.handler('py.apply.clsmethod')() == "I'm a class method"

    def test_call_py_static_method(self):
        self._test_py_method('py.apply.static')


class TestDispatcher(object):
    def setup(self):
        def get_method(name):
            if name == 'hello':
                return lambda: 'Hello World!'
            if name == 'sum':
                return lambda *args: sum(args)
            if name == 'keysort':
                return lambda **kw: [kw[k] for k in sorted(kw)]
            if name == 'flop' or name == 'py.apply.flop':
                return lambda: int('abcdefg', 16)
            raise AttributeError('unknown method')
        def handle_response(ident, **kwargs):
            self.ident = ident
            self.result = kwargs.get('result')
            self.error = kwargs.get('error')
        self.dispatcher = jsonrpc.Dispatcher(get_method, handle_response)

    def _test_error(self, response, ident, code, message, has_data=True):
        assert response.pop('jsonrpc') == '2.0'
        assert response.pop('id') == ident
        error = response.pop('error', {})
        assert not response
        assert error
        assert error.pop('code') == code
        assert error.pop('message') == message
        if has_data:
            assert error.pop('data')
        assert not error

    def _test_result(self, result, ident, value):
        assert result.pop('jsonrpc') == '2.0'
        assert result.pop('id') == ident
        assert result.pop('result') == value

    def _test_bad_error_response(self, response):
        try:
            self.dispatcher.dispatch(response)
        except jsonrpc.JSONRPCError as e:
            assert e.code == -32600
            assert e.message == 'invalid error response'
        else:
            assert False

    def test_invalid_request_type(self):
        request = self.dispatcher.dispatch(())
        self._test_error(request, None, -32600, 'unknown request type')

    def test_empty_request(self):
        request = self.dispatcher.dispatch({})
        self._test_error(request, None, -32600, 'missing jsonrpc version')

    def test_id_only(self):
        request = self.dispatcher.dispatch({'id': 100})
        self._test_error(request, 100, -32600, 'missing jsonrpc version')

    def test_bad_version(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '13.2.1'})
        self._test_error(request, 100, -32600, 'unknown jsonrpc version')

    def test_missing_request(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0'})
        self._test_error(request, 100, -32600, 'unknown message type')

    def test_empty_error(self):
        self._test_bad_error_response(
            {'id': 100, 'jsonrpc': '2.0', 'error': {}})

    def test_missing_error_code(self):
        self._test_bad_error_response(
            {'id': 100, 'jsonrpc': '2.0', 'error': {'message': 'error test'}})

    def test_missing_error_message(self):
        self._test_bad_error_response(
            {'id': 100, 'jsonrpc': '2.0', 'error': {'code': -32600}})

    def test_error_not_dict(self):
        self._test_bad_error_response(
            {'jsonrpc': '2.0', 'id': 100,
             'error': ['code', '-32602', 'message', 'invalid params']})

    def test_valid_error(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'error': {'code': -32600, 'message': 'error test'}})
        assert request is None
        assert self.ident == 100
        assert isinstance(self.error, jsonrpc.JSONRPCError)

    def test_python_error(self):
        try:
            x = int('abcxyz', 16)
        except ValueError:
            exc_type, exc, tb = sys.exc_info()
        exc_data = {'exc_type': 'ValueError', 'exc_args': exc.args, 
                    'exc_tb': traceback.format_tb(tb)}
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'error': {'code': jsonrpc.PYTHON_EXCEPTION,
                          'message': str(exc), 'data': exc_data}})
        assert request is None
        assert self.ident == 100
        assert isinstance(self.error, jsonrpc.RemoteError)

    def test_result(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'result': 'abc123'})
        assert request is None
        assert (self.ident, self.result) == (100, 'abc123')

    def test_bad_params(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'hello', 'params': ()})
        self._test_error(request, 100, -32602, 'incorrect params type')

    def test_rpc_extension(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'rpc.echo'})
        self._test_error(request, 100, -32601, 'no RPC extensions are implemented', has_data=False)

    def test_no_method(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'echo'})
        self._test_error(request, 100, -32601, 'method not found')

    def test_no_params_method(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'hello'})
        self._test_result(request, 100, 'Hello World!')

    def test_list_params_method(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'sum', 'params': [1, 2, 3, 4]})
        self._test_result(request, 100, 10)

    def test_dict_params_method(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'keysort', 'params': {'z': 1, 'a': 9, 'h': 20}})
        self._test_result(request, 100, [9, 20, 1])

    def test_unhandled_exception_in_method(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0', 'method': 'flop'})
        data = request['error']['data']
        self._test_error(request, 100, jsonrpc.UNHANDLED_EXCEPTION,
                         'unhandled exception')
        assert data == "invalid platformral for int() with base 16: 'abcdefg'"

    def test_python_exception_in_method(self):
        request = self.dispatcher.dispatch({'id': 100, 'jsonrpc': '2.0',
                'method': 'py.apply.flop'})
        data = request['error']['data']
        self._test_error(request, 100, jsonrpc.PYTHON_EXCEPTION,
                         "invalid platformral for int() with base 16: 'abcdefg'")
        assert data.pop('exc_type') == 'exceptions.ValueError'
        assert data.pop('exc_args')
        assert data.pop('tb_limit') == 20
        assert data.pop('exc_tb')
        assert not data

    def test_no_ident_method(self):
        request = self.dispatcher.dispatch({'jsonrpc': '2.0', 'method': 'hello'})
        assert request is None

    def test_batch_request(self):
        request = self.dispatcher.dispatch([
            {'jsonrpc': '2.0', 'method': 'hello'},
            {'jsonrpc': '2.0', 'id': 100, 'method': 'sum', 'params': [1, 2, 3]},
            {'jsonrpc': '2.0', 'id': 101, 'method': 'hello'},
            {'jsonrpc': '2.0', 'id': 102, 'method': 'echo'},
            [{'jsonrpc': '2.0', 'id': 103, 'method': 'echo'}],
        ])
        assert len(request) == 4
        self._test_result(request[0], 100, 6)
        self._test_result(request[1], 101, 'Hello World!')
        self._test_error(request[2], 102, -32601, 'method not found')
        self._test_error(request[3], None, -32600, 'unknown request type')

    def test_no_method_callback(self):
        dispatcher = jsonrpc.Dispatcher(None, self.dispatcher.response_callback)
        request = dispatcher.dispatch({'jsonrpc': '2.0', 'id': 100,
                                       'method': 'hello'})
        self._test_error(request, 100, -32601, 'method not found')


class TestRequester(object):
    def setup(self):
        self.outgoing = []
        self.callback_called = False
        def send_request(request):
            self.outgoing.append(request)
        self.requester = jsonrpc.Requester(send_request)

    def test_notify(self):
        self.requester.notify('hello')
        self.requester.notify('hello', ['world'])
        self.requester.notify('hello', {'world': 1})
        assert self.outgoing == [{'jsonrpc': '2.0', 'method': 'hello'},
            {'jsonrpc': '2.0', 'method': 'hello', 'params': ['world']},
            {'jsonrpc': '2.0', 'method': 'hello', 'params': {'world': 1}}]

    def test_async_request(self):
        cb = lambda **kw: None
        ident = '{:x}'.format(id(cb))
        self.requester.async_request(cb, 'hello')
        self.requester.async_request(cb, 'hello', ['world'])
        self.requester.async_request(cb, 'hello', {'world': 1})
        assert self.outgoing == [
            {'jsonrpc': '2.0', 'method': 'hello', 'id': ident},
            {'jsonrpc': '2.0', 'method': 'hello', 'params': ['world'], 'id': ident},
            {'jsonrpc': '2.0', 'method': 'hello', 'params': {'world': 1}, 'id': ident}]
        assert dict(self.requester._requests) == {ident: cb}

    def test_sync_request(self):
        r0 = self.requester.sync_request('hello')
        r1 = self.requester.sync_request('hello', ['world'])
        r2 = self.requester.sync_request('hello', {'world': 1})
        id0 = '{:x}'.format(id(r0))
        id1 = '{:x}'.format(id(r1))
        id2 = '{:x}'.format(id(r2))
        assert self.outgoing == [
            {'jsonrpc': '2.0', 'method': 'hello', 'id': id0},
            {'jsonrpc': '2.0', 'method': 'hello', 'params': ['world'], 'id': id1},
            {'jsonrpc': '2.0', 'method': 'hello', 'params': {'world': 1}, 'id': id2}]
        assert dict(self.requester._requests) == {id0: r0, id1: r1, id2: r2}

    def test_send_failure(self):
        def send(chunk):
            raise ValueError('test send failure')
        self.requester = jsonrpc.Requester(send)
        cb = lambda **kw: None
        ident = '{:x}'.format(id(cb))
        try:
            self.requester.async_request(cb, 'hello')
        except ValueError as e:
            assert str(e) == 'test send failure'
        assert not self.requester._requests

    def test_sync_call_timeout(self):
        try:
            self.requester.sync_call('hello', timeout=0.1)
        except jsonrpc.Timeout:
            pass
        else:
            assert False

    def test_sync_call(self):
        def send(chunk):
            ident = self.requester._requests.keys()[0]
            self.requester.handle_response(ident, result='world')
        self.requester = jsonrpc.Requester(send)
        assert self.requester.sync_call('hello') == 'world'

    def test_sync_call_error(self):
        def send(chunk):
            ident = self.requester._requests.keys()[0]
            self.requester.handle_response(ident, error=ValueError('test error'))
        self.requester = jsonrpc.Requester(send)
        try:
            self.requester.sync_call('hello')
        except ValueError as e:
            assert str(e) == 'test error'
        else:
            assert False


class MockRequester(object):
    def __init__(self):
        self.requests = []
    def notify(self, method, params=None):
        self.requests.append(('notify', method, params))
    def async_request(self, callback, method, params=None):
        self.requests.append(('async', method, params, callback))
    def sync_call(self, method, params=None, timeout=None):
        self.requests.append(('sync', method, params, timeout))


class TestPyConnector(object):
    def setup(self):
        self.requester = MockRequester()
        self.connector = jsonrpc.PyConnector(self.requester)

    def test_call_no_timeout(self):
        self.connector.call.foo('bar')
        assert self.requester.requests == [
                ('sync', 'py.apply.foo', [('bar',), {}], None)]

    def test_call_timeout(self):
        self.connector.call(15).foo('bar')
        assert self.requester.requests == [
                ('sync', 'py.apply.foo', [('bar',), {}], 15)]

    def test_method(self):
        cb = lambda *a, **kw: None
        self.connector.method(cb).foo('bar')
        assert self.requester.requests == [
                ('async', 'py.apply.foo', [('bar',), {}], cb)]

    def test_notify(self):
        self.connector.notify.foo('bar')
        assert self.requester.requests == [
                ('notify', 'py.apply.foo', [('bar',), {}])]

    def test_get_prop_no_timeout(self):
        self.connector.prop.foo
        assert self.requester.requests == [
                ('sync', 'py.get.foo', None, None)]

    def test_get_prop_timeout(self):
        self.connector.prop(15).foo
        assert self.requester.requests == [
                ('sync', 'py.get.foo', None, 15)]

    def test_set_prop_no_timeout(self):
        self.connector.prop.foo = 'bar'
        assert self.requester.requests == [
                ('sync', 'py.set.foo', ['bar'], None)]

    def test_set_prop_timeout(self):
        self.connector.prop(15).foo = 'bar'
        assert self.requester.requests == [
                ('sync', 'py.set.foo', ['bar'], 15)]


class TestConnector(object):
    def setup(self):
        self.requester = MockRequester()
        self.connector = jsonrpc.Connector(self.requester)

    def test_call_no_timeout(self):
        self.connector.call.foo('bar')
        assert self.requester.requests == [
                ('sync', 'foo', ('bar',), None)]

    def test_call_timeout(self):
        self.connector.call(15).foo('bar')
        assert self.requester.requests == [
                ('sync', 'foo', ('bar',), 15)]

    def test_method(self):
        cb = lambda *a, **kw: None
        self.connector.method(cb).foo(kw='bar')
        assert self.requester.requests == [
                ('async', 'foo', {'kw': 'bar'}, cb)]

    def test_notify(self):
        self.connector.notify.foo(kw='bar')
        assert self.requester.requests == [
                ('notify', 'foo', {'kw': 'bar'})]

