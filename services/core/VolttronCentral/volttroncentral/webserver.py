import errno
import logging
import os
import Queue
import sys
import threading
from tempfile import TemporaryFile
import time
import tornado
import tornado.websocket
import traceback
import uuid

from zmq.utils import jsonapi

from volttron.platform.agent import utils
from volttron.platform import jsonrpc
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
                                       UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)

# By default our log reader is none.  Only when start_log_reader is called with a
# valid file path will this variable be set 
logreader = None

def get_standard_error_message(code):

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
        self.__persistence_path = None

    def authenticate(self, username, password, ip):
        '''Authenticates a user with the authenticator.

        This is the main login function for the system. 
        '''
        groups = self._authenticator.authenticate(username, password)
        if groups:
            token = str(uuid.uuid4())
            self._add_session(username, token, ip, ",".join(groups))
            self.__store_auths()
            return token
        return None

    def _add_session(self, user, token, ip, groups):
        '''Add a user session to the session cache'''
        self._sessions[user] = {'user': user, 'token': token, 'ip': ip,
                                'groups': groups}
        self._session_tokens[token] = self._sessions[user]

    def check_session(self, token, ip):
        '''Check if a user token has been authenticated.'''
        if not self._session_tokens:
            self.__load_auths(
                              )
        session = self._session_tokens.get(str(token))
        if session:
            return session['ip'] == ip

        return False

    def __store_auths(self):
        if not self.__persistence_path:
            self.__get_auth_storage()

        with open(self.__persistence_path, 'wb') as file:
            file.write(jsonapi.dumps(self._sessions))


    def __load_auths(self):
        if not self.__persistence_path:
            self.__get_auth_storage()
        try:
            with open(self.__persistence_path) as file:
                self._sessions = jsonapi.loads(file.read())

            self._session_tokens.clear()
            for k, v in self._sessions.items():
                self._session_tokens[v['token']] = v
        except IOError:
            pass

    def __get_auth_storage(self):
        if not os.environ.get('VOLTTRON_HOME', None):
                raise ValueError('VOLTTRON_HOME environment must be set!')

        db_path = os.path.join(os.environ.get('VOLTTRON_HOME'),
                               'data/volttron.central.sessions')
        db_dir  = os.path.dirname(db_path)
        try:
            os.makedirs(db_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                raise
        self.__persistence_path = db_path


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
        self.settings = settings


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
            self.message = get_standard_error_message(self.code)

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

class LogReader(object):

    def __init__(self, file):
        self.filename = file
        self.read_thread = threading.Thread(target=self.read_messages)
        self.log_queue = Queue.Queue()
        self.read_thread.start()

    def close(self):
        self.read_thread.join(5)
        
    def read_messages(self):
        logfile = open(self.filename, 'rb')
        # last byte in the file.
        logfile.seek(0, 2)
        
        self.log_queue.put("Reading logfile: {}\n".format(self.filename))
        while True:
            line = logfile.readline()
            if not line:
                time.sleep(0.01)
                continue
            #print("Queueing line {}".format(line))
            self.log_queue.put(line)
            
class LogHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        self.write_thread = None
        _log.debug("Connection open")
    
    def on_message(self, message):
        
        passed = jsonapi.loads(message)
        method = passed['method']
        params = passed['params']
        
        if method == 'start_reading':
            if params['log_path']:
                if self.write_thread == None:
                    self.log_path = params['log_path']
                    self.write_thread = threading.Thread(target=self.writing_messages,
                                                     args=[params['log_path']])
                    self.write_thread.start()
                else:
                    self.write_message("Already reading log file: {}".format(self.log_path))
            else:
                msg = "Invalid params 'log_path' must be specified"
                self.write_message(msg)
                self.close(1002, msg)
        else:
            self.write_message(message)
        #self.log_path = os.path.expanduser(params['log_path'])
        #self.logreader = LogReader(self.log_path)         
        
        _log.debug("Message was: {}".format(message))

    def writing_messages(self, log_path):
        
        log_path = os.path.expanduser(log_path)
        
        if os.path.exists(log_path):
            try:
                reader = LogReader(log_path)            
            except OSError as exc:
                if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                    raise
            
            if reader:
                
                while True:                    
                    if not reader.log_queue.empty():
                        self.write_message(reader.log_queue.get_nowait())
                        
                    time.sleep(0.5)
                    
                reader.close()
        else:
            self.write_message("Invalid log file specified {}".format(log_path))
            self.close()
        
    def on_close(self):
        self.write_thread.join(5)


#     def on_message(self, message):
#         #tornado.websocket.WebSocketHandler.on_message(self, message)
#         self.write_message("written from server "+message)


class StatusHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print("Opened!")
        #self.application.shoppingCart.register(self.callback)

    def on_close(self):
        print("Closed")
        #self.application.shoppingCart.unregister(self.callback)

    def on_message(self, message):
        self.write_message("write from server: "+message)

#     def callback(self, count):
#         self.write_message('{"inventoryCount":"%d"}' % count)

@tornado.web.stream_request_body
class ManagerRequestHandler(tornado.web.RequestHandler):
    '''The main RequestHanlder for the platform manager.

    The manager only accepts posted RpcParser methods.  The manager will parse
    the request body for valid json RpcParser.  The first call to this request
    handler must be a getAuthorization request.  The call will return an
    authorization token that will be valid for the current session.  The token
    must be passed to any other calls to the handler or a 401 Unauhthorized
    code will be returned.
    '''
    def prepare(self):
        self.tmp = TemporaryFile()

    def data_received(self, chunk):
        self.tmp.write(chunk)

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
                                              message="Invalid username or password")
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
                # call to the agent route request to send to the correct
                # platform
                async_caller.send(self._response_complete,
                                  self.application.manager.route_request,
                                  rpcRequest.id, rpcRequest.method,
                                  rpcRequest.params)

    def _response_complete(self, data):
        print("RESPONSE COMPLETE:{}".format(data))
        try:

            if (data[0] is not None):
                if isinstance(data[0], RpcResponse):
                    self.write(data[0].get_response())
                else:
                    resp = None
                    if isinstance(data[0], Exception):
                        if isinstance(data[0], NameError):
                            resp = RpcResponse(id=self.rpcrequest.id,
                                               code=METHOD_NOT_FOUND,
                                               message=data[0].msg)
                    if not resp:
                        resp = RpcResponse(id=self.rpcrequest.id,
                                           code=UNHANDLED_EXCEPTION,
                                           message=str(data[0][1]))
                    print("Writing: "+str(resp.get_response()))
                    self.write(resp.get_response())

    #                 else:
    # #                 resp = RpcResponse(code=UNHANDLED_EXCEPTION,
    # #                                    message=str(data[0][1]))
    #                     print(self.write("Error: "+str(data[0][0])
    #                                + " message: "+str(data[0][1])))
    #                     self.write("Error: "+str(data[0][0])
    #                                + " message: "+str(data[0][1]))
            else:
                if isinstance(data[1], RpcResponse):
                    self.write(data[1].get_response())
                else:
                    rpcresponse = RpcResponse(self.rpcrequest.id, result=data[1])
                    self.write(rpcresponse.get_response())
        except KeyError as e:
            self.write(data)
        print('handling request done')
        try:
            self.finish()
        except:
            print("EXCEPTION IN FINISH")
#            traceback.print_exc(file=sys.stderr)


    @tornado.web.asynchronous
    def post(self):
        _log.debug('handling request')
        self.tmp.seek(0)
        self.rpcrequest = RpcRequest(self.tmp.read())
        self.tmp.close()
        #request_body = self.request.body
        # result will be an RpcParser object  when completed
        #self.rpcrequest = RpcRequest(request_body)
        if self.rpcrequest.has_error():
            self._response_complete(
                jsonrpc.json_error(self.rpcrequest.id,
                                   self.rpcrequest.error,
                                   get_standard_error_message(self.rpcrequest.error)))
        else:
            self._route(self.rpcrequest)
