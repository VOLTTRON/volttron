import logging

import gevent
from ws4py.server.geventserver import WebSocketWSGIApplication

from .websocket import VolttronWebSocket

_log = logging.getLogger(__name__)

AUTHORIZE_TIMEOUT = 10
_REQUEST_FIELDS = ('REMOTE_ADDR', 'PATH_INFO', 'HTTP_HOST', 'HTTP_ORIGIN')


class WebApplicationWrapper:
    """ A container class that will hold all of the applications registered
    with it.  The class provides a container for managing the routing of
    websocket, static content, and rpc function calls.
    """
    def __init__(self, platformweb, host, port):
        self.platformweb = platformweb
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
            identity = self._wsregistry[path]
            if not self._authorized(environ, identity):
                start_response('403 Forbidden', [('Content-Type', 'text/plain')])
                return [b'Forbidden']
            environ['ws4py.app'] = self
            environ['identity'] = identity
            return self.ws(environ, start_response)

        return self.platformweb.app_routing(environ, start_response)

    def _authorized(self, environ, identity):
        """Ask the owning agent before the upgrade; only an answer of True passes."""
        # Imported here because platform_web_service imports this module.
        from .platform_web_service import _first_segment, _without_login_cookie

        request = {key: environ[key] for key in _REQUEST_FIELDS if key in environ}
        if 'HTTP_COOKIE' in environ:
            request['HTTP_COOKIE'] = _without_login_cookie(environ['HTTP_COOKIE'])
        # Fail closed: Timeout is not an Exception, and any error means no upgrade.
        try:
            answer = self.platformweb.vip.rpc.call(
                identity, 'client.authorize', request).get(timeout=AUTHORIZE_TIMEOUT)
        except (Exception, gevent.Timeout) as err:
            answer = err
        if answer is True:
            return True
        _log.warning('websocket refused: owner %r, first segment %r',
                     identity, _first_segment(environ['PATH_INFO']))
        return False

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
        # Fail closed on an error or timeout. None means the owner has no
        # opened callback, which keeps the socket open.
        try:
            should_open = self.platformweb.vip.rpc.call(
                identity, 'client.opened', ip, endpoint).get(timeout=AUTHORIZE_TIMEOUT)
        except (Exception, gevent.Timeout) as err:
            _log.warning('client.opened failed for %r: %s', identity, err)
            should_open = False
        if should_open is not None and not should_open:
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
            self.platformweb.vip.rpc.call(identity, 'client.message',
                                        str(endpoint), str(message))

    def client_closed(self, client, endpoint, identity,
                      reason="Client left without proper explanation"):

        client_set = self.endpoint_clients.get(endpoint, set())

        try:
            key = (identity, client)
            client_set.remove(key)
        except KeyError:
            pass
        else:
            self.platformweb.vip.rpc.call(identity, 'client.closed', endpoint)

    def _check_owner(self, endpoint, identity):
        owner = self._wsregistry.get(endpoint)
        if owner is not None and owner != identity:
            raise PermissionError(f'websocket {endpoint!r} belongs to another agent')
        return owner

    def create_ws_endpoint(self, endpoint, identity):
        self._check_owner(endpoint, identity)
        if endpoint not in self.endpoint_clients:
            self.endpoint_clients[endpoint] = set()
        self._wsregistry[endpoint] = identity

    def destroy_ws_endpoint(self, endpoint, identity):
        """Close and remove identity's websocket; an unknown endpoint is ignored."""
        if self._check_owner(endpoint, identity) is None:
            _log.debug('no websocket registered at %r; nothing removed', endpoint)
            return
        for _, client in list(self.endpoint_clients.get(endpoint, ())):
            client.close(reason="Endpoint closed.")
        self.endpoint_clients.pop(endpoint, None)
        del self._wsregistry[endpoint]

    def destroy_owner_endpoints(self, identity):
        owned = [endpoint for endpoint, owner in self._wsregistry.items() if owner == identity]
        for endpoint in owned:
            self.destroy_ws_endpoint(endpoint, identity)

    def websocket_send(self, endpoint, message, identity):
        self._check_owner(endpoint, identity)
        _log.debug('Sending message to clients!')
        clients = self.endpoint_clients.get(endpoint, [])
        if not clients:
            _log.warning("There were no clients for endpoint {}".format(endpoint))
        for c in clients:
            identity, client = c
            _log.debug('Sending endpoint&&message {}&&{}'.format(
                endpoint, message))
            client.send(message)

