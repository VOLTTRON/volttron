
AF_UNIX = 1
SOCK_STREAM = 1
SOL_SOCKET = 1


class socket(object):
    def accept(self):
        return (None, ('', 0))

    def bind(self, address):
        pass

    def connect(self, address):
        pass

    def listen(self, backlog):
        pass

    def makefile(self, mode='r', bufsize=-1):
        return None
