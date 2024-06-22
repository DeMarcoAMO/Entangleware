import socket
import struct


class TcpEndPoint:
    def __init__(self, connection):
        if isinstance(connection, socket.socket):
            self._sock = connection
            self._sock.settimeout(30)
        else:
            raise Exception('connection is not a socket.socket type')

    def close(self):
        self._sock.close()

    def sendmsg(self, msg, msgid, msgtype):
        bytemsg = bytearray(msg)
        header = bytearray(struct.pack(">QLL", msgid, msgtype, len(bytemsg)))
        completemsg = header + bytemsg
        msglength = len(completemsg)
        chunksize = 512
        startaddr = 0
        # chunk size to break the data stream up into more managable
        while msglength:
            lastelem = startaddr + chunksize
            bytessent = self._sock.send(completemsg[startaddr:lastelem])
            startaddr += bytessent  # bytessent should equal chunksize but if not, start at proper startaddr
            msglength -= bytessent

    def getmsg(self):
        header = bytearray(self._sock.recv(16))
        msgid, msgtype, msglength = struct.unpack(">QLL", header)
        msg = bytearray(msglength) # allocate buffer
        msgview = memoryview(msg)  # create buffer reference
        while msglength:
            nbytes = self._sock.recv_into(msgview, msglength)
            msglength -= nbytes
        return msg, msgid, msgtype
