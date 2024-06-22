import socket


class TcpServer:
    def __init__(self, serveraddress=('', 0), timeout=1.0, backlog=1):
        # private data ####
        self._timeout = timeout
        self._initaddress = serveraddress
        self._backlog = backlog
        self._listensock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # setup options, bind, listen
        self._listensock.settimeout(self._timeout)
        self._listensock.bind(self._initaddress)
        self._listensock.listen(self._backlog)

        # public data ####
        self.serverport = self._listensock.getsockname()[1]

    def accept(self):
        return self._listensock.accept()

    def close(self):
        self._listensock.close()
