
POLLIN = 1
POLLOUT = 2
PULL = 7
XPUB = 9


class Context:
    def instance(self):
        pass


class Poller:
    def register(self, socket, flags=POLLIN|POLLOUT):
        pass
