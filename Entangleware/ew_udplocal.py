import socket
import struct


class UdpLocal:
    def __init__(self, udplocal_ip='127.0.0.1', udplocal_port=50101):
        self.UDP_IP = udplocal_ip
        self.UDP_PORT = udplocal_port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.MCAST_TTL)

    def close(self):
        self.sock.close()

    def sendmsg(self, tcpport):
        portpack = bytearray(struct.pack(">H", tcpport))
        self.sock.sendto(portpack, (self.UDP_IP, self.UDP_PORT))
