import logging
import tornado
import uuid

from volttron.platform.agent import utils
from volttron.platform import jsonrpc
from volttron.platform.agent.vipagent import jsonapi
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
                                       UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)


def get_standard_error_message(self, code):

    if code == INTERNAL_ERROR:
        error = 'Internal JSON-RPC error'
    elif code == INVALID_PARAMS:
        error = 'Invalid method parameter(s).'
    elif code == INVALID_REQUEST:
        error = 'The JSON sent is not a valid Request object.'
    elif code == METHOD_NOT_FOUND:
        error = 'The method does not exist / is not available.'
    elif code == PARSE_ERROR:
        error = 'Invalid JSON was received by the server. '\
                'An error occurred on the server while parsing the JSON text.'
    else:
        # UNHANDLED_EXCEPTION
        error = 'Unhandled exception happened!'

    return error


class SessionHandler:
    '''A handler for dealing with authentication of sessions

    The SessionHandler requires an authenticator to be handed in to this
    object in order to authenticate user.  The authenticator must implement
    an interface that expects a method called authenticate with parameters
    username and password.  The return value must be either a list of groups
    the user belongs two or None.

    If successful then the a session token is generated and added to a cache
    of validated users to be able to be checked against.  The user's ip address
    is stored with the token for further checking of authentication.
    '''
    def __init__(self, authenticator):
        self._sessions = {}
        self._session_tokens = {}
        self._authenticator = authenticator

    def authenticate(self, username, password, ip):
        '''Authenticates a user with the authenticator.

        This is the main login function for the system.
        '''
        groups = self._authenticator.authenticate(username, password)
        if groups:
            token = str(uuid.uuid4())
            self._add_session(username, token, ip, ",".join(groups))
            return token
        return None

    def _add_session(self, user, token, ip, groups):
        '''Add a user session to the session cache'''
        self._sessions[user] = {'user': user, 'token': token, 'ip': ip,
                                'groups': groups}
        self._session_tokens[token] = self._sessions[user]

    def check_session(self, token, ip):
        '''Check if a user token has been authenticated.'''
        session = self._session_tokens.get(str(token))
        if session:
            return session['ip'] == ip

        return False


class ManagerWebApplication(tornado.web.Application):
    '''A tornado web application wrapper class.

    This classes responsibility is to hold sessions and the agent manager
    class so that the request handler has access to these resources.

    Request handlers have access to this function through
        self.application.manager and
        self.application.sessions
    respectively.
    '''
    def __init__(self, session_handler, manager, handlers=None,
                 default_host="", transforms=None, **settings):
        super(ManagerWebApplication, self).__init__(handlers, default_host,
                                                    transforms, **settings)
        self.sessions = session_handler
        self.manager = manager


class RpcResponse:
    '''Wraps a response from rpc call in a json wrapper.'''

    def __init__(self, id, **kwargs):
        '''Initialize the response object with id and parameters.

        This method requires that either a code and message be set or a result
        be set via the kwargs.

        If code is a standard specification error then message will be set
        automatically. If message is set it will override the default message
        from the specs.

        Ex.
            RpcResponse('xwrww', code=401, message='Authorization error')
            RpcResponse('xw223', code=INVALID_PARAMS)

        '''
        self.id = id
        self.result = kwargs.get('result', None)
        self.message = kwargs.get('message', None)
        self.code = kwargs.get('code', None)

        if self.message is None and \
            self.code in (INTERNAL_ERROR, INVALID_PARAMS,
                          INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
                          UNHANDLED_EXCEPTION):
            self.message = self.get_standard_error_message(self.code)

        # There is probably a better way to move the result up a level, however
        # this was the fastest I could think of.
        if isinstance(self.result, dict) and 'result' in self.result:
            self.result = self.result['result']

    def get_response(self):
        d = {'jsonrpc': '2.0', 'id': self.id}

        if self.code is not None:
            d['error'] = {'code': self.code,
                          'message': self.message}
        else:
            d['result'] = self.result

        return d


class RpcRequest:
    PARSE_ERR = {'code': -32700, 'message': 'Parse error'}

    def has_error(self):
        return self.error is not None

    def __init__(self, request_body=None, id=None, method=None, params=None):

        try:
            self.id = None        # default for json RpcParser with parse error
            self.error = None

            if request_body:
                data = jsonapi.loads(request_body)

                if data == []:
                    self.error = INVALID_REQUEST
                    return

                if 'method' not in data:
                    self.error = METHOD_NOT_FOUND
                    return

                if 'jsonrpc' not in data or data['jsonrpc'] != '2.0':
                    self.error = PARSE_ERROR
                    return

                if 'id' not in data:
                    self.error = PARSE_ERROR
                    return

                # This is only necessary at the top level of the RpcParser stack.
                if "authorization" not in data:
                    if data['method'] != 'get_authorization':
                        self.error = 401
                        return
                if "authorization" in data:
                    self.authorization = data['authorization']
            else:
                data = {'method': method, 'id': id, 'jsonrpc': '2.0',
                        'params': params}

            self.method = data['method']
            self.jsonrpc = data['jsonrpc']
            self.id = data['id']
            if 'params' in data:
                self.params = data['params']
            else:
                self.params = []

        except:
            self.error = PARSE_ERROR


class ManagerRequestHandler(tornado.web.RequestHandler):
    '''The main RequestHanlder for the platform manager.

    The manager only accepts posted RpcParser methods.  The manager will parse
    the request body for valid json RpcParser.  The first call to this request
    handler must be a getAuthorization request.  The call will return an
    authorization token that will be valid for the current session.  The token
    must be passed to any other calls to the handler or a 401 Unauhthorized
    code will be returned.
    '''

    def _route(self, rpcRequest):
        # this is the only method that the handler truly deals with, the
        # rest will be dispatched to the manager agent itself.
        sessions = self.application.sessions

        if rpcRequest.method == 'get_authorization':
            try:
                token = sessions.authenticate(rpcRequest.params['username'],
                                              rpcRequest.params['password'],
                                              self.request.remote_ip)
                if token:
                    rpcResponse = RpcResponse(rpcRequest.id, result=str(token))
                else:
                    rpcResponse = RpcResponse(rpcRequest.id,
                                              code=401,
                                              message="invalid credentials")
            except:
                rpcResponse = RpcResponse(rpcRequest.id,
                                          code=INVALID_PARAMS,
                                          message='Invalid parameters to {}'
                                          .format(rpcRequest.method))

            self._response_complete((None, rpcResponse))
        else:
            # verify the user session
            if not sessions.check_session(rpcRequest.authorization,
                                          self.request.remote_ip):
                rpcResponse = RpcResponse(rpcRequest.id,
                                          code=401,
                                          message="Unauthorized Access")
                self._response_complete((None, rpcResponse))
            else:
                _log.debug("Calling: id: {}, method: {}, params: {}"
                           .format(rpcRequest.id, rpcRequest.method,
                                   rpcRequest.params))
                async_caller = self.application.manager.async_caller
                async_caller.send(self._response_complete,
                                  self.application.manager.route_request,
                                  rpcRequest.id, rpcRequest.method,
                                  rpcRequest.params)

    def _response_complete(self, data):
        print("RESPONSE COMPLETE:{}".format(data))
        if (data[0] is not None):
            if isinstance(data[0], RpcResponse):
                self.write(data[0].get_response())
            else:
                self.write("Error: "+str(data[0][0])
                           + " message: "+str(data[0][1]))
        else:
            if isinstance(data[1], RpcResponse):
                self.write(data[1].get_response())
            else:
                rpcresponse = RpcResponse(self.rpcrequest.id, result=data[1])
                self.write(rpcresponse.get_response())

        print('handling request done')
        self.finish()

    @tornado.web.asynchronous
    def post(self):
        _log.debug('handling request')
        request_body = self.request.body
        # result will be an RpcParser object  when completed
        self.rpcrequest = RpcRequest(request_body)
        if self.rpcrequest.has_error():
            self._response_complete(
                jsonrpc.json_error(self.rpcrequest.id,
                                   self.rpcrequest.error,
                                   get_standard_error_message(self.rpcrequest.error)))
        else:
            self._route(self.rpcrequest)
