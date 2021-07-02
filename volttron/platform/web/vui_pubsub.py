from weakref import WeakValueDictionary

from volttron.platform.web.websocket import VolttronWebSocket
from ws4py.server.wsgiutils import WebSocketWSGIApplication


class VUIPubsubManager:
    def __init__(self):
        # TODO: What needs to be initialized for this?
        self.subscription_websockets = {} # Websockets for all topics with current subscriptions.
        self.publication_websockets = {}  # Websockets for all topics with current publication queue.
        self.user_websockets = WeakValueDictionary()  # References to all websockets for each user access_token.

    def get_socket_routes(self, access_token, topic=None):
        # TODO: return open websockets for this user.
        return {}

    def open_publication_socket(self, access_token, topic=None):
        if access_token not in self.publication_websockets.keys():
            self._create_websocket(topic, access_token, for_publication=False)
        # TODO: Set up publication websocket for the specified topic.
        return None  # Return route to this websocket. (somehow)

    def open_subscription_socket(self, access_token, topic):
        ws = self.subscription_websockets.get(topic)
        if not ws:
            ws = self._create_websocket(topic, access_token, for_publication=False)
        self.user_websockets[access_token][topic] = self.subscription_websockets[topic]
        # TODO: Create process for checking that tokens are still valid.
        return None

    def close_socket(self, access_token, topic=None):
        # TODO: Cancel subscription to a topic (or all topics for ../pubsub).
        # TODO: Remove any topic expiry monitors.
        # TODO: Close websocket if there are no additional subscribers.
        pass

    def publish(self, access_token, topic=None):
        # TODO: publish the received content to the message bus.
        # TODO: return {'number_of_subscribers': the_number}
        return {}

    def _create_websocket(self, topic, access_token, for_publication):
        ws_app = WebSocketWSGIApplication(handler_cls=VolttronWebSocket)
        if not for_publication:
            self.subscription_websockets[topic] = {
                'socket': ws_app,
                'route':
            }
        return ws_app