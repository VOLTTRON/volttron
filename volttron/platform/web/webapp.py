import logging

from ws4py.server.geventserver import WebSocketWSGIApplication

from .websocket import VolttronWebSocket

_log = logging.getLogger(__name__)


class WebApplicationWrapper(object):
    """ A container class that will hold all of the applications registered
    with it.  The class provides a contianer for managing the routing of
    websocket, static content, and rpc function calls.
    """
    def __init__(self, masterweb, host, port):
        self.masterweb = masterweb
        self.port = port
        self.host = host
        self.ws = WebSocketWSGIApplication(handler_cls=VolttronWebSocket)
        self.clients = []
        self.endpoint_clients = {}
        self._wsregistry = {}

    def __call__(self, environ, start_response):
        """
        Good ol' WSGI application. This is a simple demo
        so I tried to stay away from dependencies.
        """
        if environ['PATH_INFO'] == '/favicon.ico':
            return self.favicon(environ, start_response)

        path = environ['PATH_INFO']
        if path in self._wsregistry:
            environ['ws4py.app'] = self
            environ['identity'] = self._wsregistry[environ['PATH_INFO']]
            return self.ws(environ, start_response)

        return self.masterweb.app_routing(environ, start_response)

    def favicon(self, environ, start_response):
        """
        Don't care about favicon, let's send nothing.
        """
        status = '200 OK'
        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return ""

    def client_opened(self, client, endpoint, identity):

        ip = client.environ['REMOTE_ADDR']
        should_open = self.masterweb.vip.rpc.call(identity, 'client.opened',
                                                  ip, endpoint)
        if not should_open:
            _log.error("Authentication failure, closing websocket.")
            client.close(reason='Authentication failure!')
            return

        # In order to get into endpoint_clients create_ws must be called.
        if endpoint not in self.endpoint_clients:
            _log.error('Unknown endpoint detected: {}'.format(endpoint))
            client.close(reason="Unknown endpoint! {}".format(endpoint))
            return

        if (identity, client) in  self.endpoint_clients[endpoint]:
            _log.debug("IDENTITY,CLIENT: {} already in endpoint set".format(identity))
        else:
            _log.debug("IDENTITY,CLIENT: {} added to endpoint set".format(identity))
            self.endpoint_clients[endpoint].add((identity, client))

    def client_received(self, endpoint, message):
        clients = self.endpoint_clients.get(endpoint, [])
        for identity, _ in clients:
            self.masterweb.vip.rpc.call(identity, 'client.message',
                                        str(endpoint), str(message))

    def client_closed(self, client, endpoint, identity,
                      reason="Client left without proper explaination"):

        client_set = self.endpoint_clients.get(endpoint, set())

        try:
            key = (identity, client)
            client_set.remove(key)
        except KeyError:
            pass
        else:
            self.masterweb.vip.rpc.call(identity, 'client.closed', endpoint)

    def create_ws_endpoint(self, endpoint, identity):
        if endpoint not in self.endpoint_clients:
            self.endpoint_clients[endpoint] = set()
        self._wsregistry[endpoint] = identity

    def destroy_ws_endpoint(self, endpoint):
        clients = self.endpoint_clients.get(endpoint, [])
        for identity, client in clients:
            client.close(reason="Endpoint closed.")
        try:
            del self.endpoint_clients[endpoint]
        except KeyError:
            pass

    def websocket_send(self, endpoint, message):
        _log.debug('Sending message to clients!')
        clients = self.endpoint_clients.get(endpoint, [])
        if not clients:
            _log.warning("There were no clients for endpoint {}".format(endpoint))
        for c in clients:
            identity, client = c
            _log.debug('Sending endpoint&&message {}&&{}'.format(
                endpoint, message))
            client.send(message)

