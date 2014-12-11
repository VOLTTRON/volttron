
NOBLOCK = 1
SNDMORE = 2

POLLIN = 1
POLLOUT = 2

PUB = 1
SUB = 2
PULL = 7
PUSH = 8
XPUB = 9


class Context(object):
    def instance(self):
        return None


class Poller(object):
    def register(self, socket, flags=POLLIN|POLLOUT):
        pass

    def poll(self, timeout=None):
        return None


class Socket(object):
    def __new__(cls, socket_type, context=None):
        return None

    def bind(self, addr):
        pass

    def connect(self, addr):
        pass

    def disconnect(self, addr):
        pass

    def close(self, linger=None):
        pass

    @property
    def closed(self):
        return True

    @property
    def rcvmore(self):
        return 0

    @property
    def context(self):
        return None

    @context.setter
    def context(self, value):
        pass
    
    def send_string(self, u, flags=0, copy=True, encoding='utf-8'):
        pass

    def recv_string(self, flags=0, encoding='utf-8'):
        return u''

    def send_multipart(self, msg_parts, flags=0, copy=True, track=False):
        pass

    def recv_multipart(self, flags=0, copy=True, track=False):
        return []

    def send_json(self, obj, flags=0, **kwargs):
        pass

    def recv_json(self, flags=0, **kwargs):
        return {}
