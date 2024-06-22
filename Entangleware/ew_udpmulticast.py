import socket
import struct


class UdpMulticaster:
    def __init__(self, mcast_group='239.255.45.57', mcast_port=50101, mcast_ttl=1):
        self.MCAST_GRP = mcast_group
        self.MCAST_PORT = mcast_port
        self.MCAST_TTL = mcast_ttl

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.MCAST_TTL)

    def close(self):
        self.sock.close()

    def sendmsg(self, tcpport):
        portpack = bytearray(struct.pack(">H", tcpport))
        self.sock.sendto(portpack, (self.MCAST_GRP, self.MCAST_PORT))
