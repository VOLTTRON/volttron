import logging

from ws4py.websocket import WebSocket

_log = logging.getLogger(__name__)


class VolttronWebSocket(WebSocket):

    def __init__(self, *args, **kwargs):
        super(VolttronWebSocket, self).__init__(*args, **kwargs)
        _log = logging.getLogger(self.__class__.__name__)

    def _get_identity_and_endpoint(self):
        identity = self.environ['identity']
        endpoint = self.environ['PATH_INFO']
        return identity, endpoint

    def opened(self):
        _log.info('Socket opened')
        app = self.environ['ws4py.app']
        identity, endpoint = self._get_identity_and_endpoint()
        app.client_opened(self, endpoint, identity)

    def received_message(self, m):
        # self.clients is set from within the server
        # and holds the list of all connected servers
        # we can dispatch to
        _log.debug('Socket received message: {}'.format(m))
        app = self.environ['ws4py.app']
        identity, endpoint = self._get_identity_and_endpoint()
        app.client_received(endpoint, m)

    def closed(self, code, reason="A client left the room without a proper explanation."):
        _log.info('Socket closed!')
        app = self.environ.pop('ws4py.app')
        identity, endpoint = self._get_identity_and_endpoint()
        app.client_closed(self, endpoint, identity, reason)
