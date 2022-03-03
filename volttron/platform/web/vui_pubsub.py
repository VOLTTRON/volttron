import json
from weakref import WeakValueDictionary
from collections import defaultdict

from volttron.platform.web.websocket import VolttronWebSocket
from ws4py.server.geventserver import WebSocketWSGIApplication
from ws4py.websocket import WebSocket, EchoWebSocket
import logging

_log = logging.getLogger()


class VUIPubsubManager:
    def __init__(self, agent):
        self._agent = agent
        self.subscription_websockets = WeakValueDictionary() # Websockets for all topics with current subscriptions.
        self.publication_websockets = {}  # Websockets for all topics with current publication queue.
        self.user_websockets = defaultdict(dict)  # References to all websockets for each user access_token.

    def get_socket_routes(self, access_token, topic=None):
        _log.debug('In get_socket_routes. User_websockets is: ')
        _log.debug(self.user_websockets)
        _log.debug('In get_socket_routes. subscription_websockets is: ')
        _log.debug(self.subscription_websockets)
        return {t: str(w) for t, w in self.user_websockets[access_token].items()}

    def open_subscription_socket(self, access_token, topic):
        _log.debug('In open_subscription_socket:')
        _log.debug((f'access_token: {access_token}'))
        _log.debug(f'topic: {topic}')
        ws = self.subscription_websockets.get(topic)
        _log.debug(f'subscription_websockets has: {ws}')
        if not ws:
            _log.debug("Didn't find ws, so creating.")
            ws = self._create_websocket(topic, access_token)
            _log.debug(f'Now we have ws: {ws}')
        # TODO: Create process for checking that tokens are still valid.
        else:
            _log.debug('We had ws, so now in else block.')
            self.user_websockets[access_token][topic] = ws
            _log.debug('reached end, returning ws.')
        return ws

    def close_socket(self, access_token, topic=None):
        # TODO: Cancel subscription to a topic (or all topics for ../pubsub).
        # TODO: Remove any topic expiry monitors.
        # TODO: Close websocket if there are no additional subscribers.
        pass

    def publish(self, topic, headers, message):
        subscriber_count = self._agent.vip.pubsub.publish('pubsub', topic, headers=headers, message=message).get(timeout=5)
        return {'number_of_subscribers': subscriber_count}

    def _create_websocket(self, topic, access_token):
        ws_app = WebSocketWSGIApplication(handler_cls=VUIWebSocket)
        self.subscription_websockets[topic] = ws_app
        self.user_websockets[access_token][topic] = self.subscription_websockets[topic]
        return ws_app

    def client_opened(self, ws, topic, access_token):
        _log.debug(f'VUIPubsubManager: Subscribing to {topic}')
        self._agent.vip.pubsub.subscribe('pubsub', topic, ws.on_topic)
        self.user_websockets[access_token][topic] = ws

        # if topic not in self.subscription_websockets:
        #     err = f'Websocket opened for unintialized topic: {topic}'
        #     _log.error(err)
        #     ws.close(reason=err)
        #     return

        # TODO: Use this if we need to look over websockets connected to one subscription.
        # if ws in  self.subscription_websockets[topic]:
        #     _log.debug("IDENTITY,CLIENT: {} already in endpoint set".format(identity))
        # else:
        #     _log.debug("IDENTITY,CLIENT: {} added to endpoint set".format(identity))
        #     self.subscription_websockets[endpoint].add((identity, ws))
#
# class SubscriptionGroup:
#     def __init__(self, pubsub_interface, topic: str):
#         self.topic = topic
#         self.websockets = []
#         self.pubsub = pubsub_interface
#         self.pubsub.subscribe('pubsub', topic, self.on_publish)
#
#
#     def add(self, ws: WebSocket):
#         self.websockets.append(ws)
#
#     def on_publish(self, peer, sender, bus, topic, headers, message):
#         for ws in self.websockets:
#             if not ws.terminated:
#                 try:
#                     ws.send(message)
#                 except Exception as e:
#                     _log.warning(f'Error sending subscription data: {e}')
#
#     def remove(self, ):
#         pass


class VUIWebSocket(WebSocket):
    def __init__(self, *args, **kwargs):
        super(VUIWebSocket, self).__init__(*args, **kwargs)
        _log = logging.getLogger(self.__class__.__name__)

    def _get_topic(self):
        from volttron.platform.web import get_bearer
        path_info = self.environ['PATH_INFO']
        topic = path_info.split('/pubsub/')[1]
        access_token = get_bearer(self.environ)
        return topic, access_token

    def opened(self):
        _log.info('Socket opened')
        app = self.environ['ws4py.app']
        topic, access_token = self._get_topic()
        app.client_opened(self, topic, access_token)

    def received_message(self, m):
        # self.clients is set from within the server
        # and holds the list of all connected servers
        # we can dispatch to
        # _log.debug('Socket received message: {}'.format(m))
        # app = self.environ['ws4py.app']
        # identity, endpoint = self._get_identity_and_endpoint()
        # app.client_received(endpoint, m)
        pass

    def closed(self, code, reason="A client left the room without a proper explanation."):
        # _log.info('Socket closed!')
        # app = self.environ.pop('ws4py.app')
        # identity, endpoint = self._get_identity_and_endpoint()
        # app.client_closed(self, endpoint, identity, reason)
        pass

    def on_topic(self, peer, sender, bus, topic, headers, message):
        _log.debug('VUIWebSocket: in _on_topic')
        _log.debug(f'topic is: {topic}')
        _log.debug(f'message is: {message}')
        if not self.terminated:
            try:
                self.send(json.dumps(message))
            except Exception as e:
                _log.warning(f'Error sending subscription data: {e}')
