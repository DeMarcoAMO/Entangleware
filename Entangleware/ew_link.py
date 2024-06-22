from Entangleware.ew_udpmulticast import UdpMulticaster
from Entangleware.ew_tcpserver import TcpServer
from Entangleware.ew_tcpendpoint import TcpEndPoint
from Entangleware.ew_udplocal import UdpLocal
import struct
import time
import numpy as np
import pathlib
import math

# debug max and min time global
# max_time = float('-inf')
# min_time = float('inf')

# create global max_time. Add to set_digital_state and set_analog_state something that compares the seqtime and
# updates max_time as needed. May want minimum time as well.
class ConnectionManager:
    def __init__(self):
        self.isConnected = False
        self.tcp_server = None
        self.udp_local = None
        self.tcp_endpoint = None
        self.localudp = True

    def close(self):
        self.isConnected = False

        if self.tcp_endpoint:
            self.tcp_endpoint.close()

        if self.tcp_server:
            self.tcp_server.close()

        if self.udp_local:
            self.udp_local.close()

        self.tcp_server = None
        self.udp_local = None
        self.tcp_endpoint = None


class DDS:
    def __init__(self):
        self.connector = 0
        self.mosipin = 22
        self.sclkpin = 25
        self.cspin = 24
        self.resetpin = 21
        self.ioupdatepin = 23
        self.spi_min_time = 2e-7
        self._dds_refclock = 20e6
        self._dds_refclkmultiplier = 20
        self._dds_sysclock = self._dds_refclkmultiplier * self._dds_refclock

    def _spi(self, spitime,  bytes_to_write):
        # IOUpdate Low
        set_digital_state(spitime+self.spi_min_time, self.connector, 1 << self.ioupdatepin, 1 << self.ioupdatepin,
                          0 << self.ioupdatepin)

        chanselect = ((1 << self.ioupdatepin) | (1 << self.cspin))
        outenable = chanselect
        state = chanselect

        # CS high and ioupdate high
        set_digital_state(spitime, self.connector, chanselect, outenable, state)

        thistime = spitime
        chanselect = ((1 << self.mosipin) | (1 << self.sclkpin) | (1 << self.cspin))
        outenable = chanselect
        thistime -= self.spi_min_time
        state = ((0 << self.mosipin) | (0 << self.sclkpin) | (0 << self.cspin))

        # set last sclk falling edge
        set_digital_state(thistime, self.connector, chanselect, outenable, state)

        for individualbytes in reversed(bytes_to_write):
            for individualbits in range(8):
                thistime -= self.spi_min_time
                state = ((((individualbytes >> individualbits) & 1) << self.mosipin) | (1 << self.sclkpin) | (
                    0 << self.cspin))
                set_digital_state(thistime, self.connector, chanselect, outenable, state)
                thistime -= self.spi_min_time
                state = ((((individualbytes >> individualbits) & 1) << self.mosipin) | (0 << self.sclkpin) | (
                    0 << self.cspin))
                set_digital_state(thistime, self.connector, chanselect, outenable, state)

    def set_freq(self, ddstime, channel_mask, freq):
        payload0 = bytearray([0, channel_mask << 4, 4])
        payload4 = struct.pack('>L', round((1 << 32) * freq / self._dds_sysclock))
        payload_combined = payload0 + payload4
        self._spi(ddstime, payload_combined)
        return

    def set_amplitude(self, ddstime, channel_mask, amplitude):
        payload0 = bytearray([0, channel_mask << 4])
        payload6 = struct.pack('>BBH', 6, 0, ((1 << 12) | (int(amplitude) & 0x03FF)))
        payload_combined = payload0 + payload6
        #print(payload_combined.hex())
        self._spi(ddstime, payload_combined)
        return

    def set_phase(self, ddstime, channel_mask, phase):
        pass

    def initialize(self, ddstime):
        # FR1 register
        register = 1
        payload1 = (self._dds_refclkmultiplier << 2)
        payload2 = 0
        payload3 = 0
        #print(payload1)
        datatosend = bytearray([register, payload1, payload2, payload3])
        #print(datatosend.hex())
        self._spi(ddstime, datatosend)
        return

    def reset(self, ddstime):
        thistime = ddstime
        chanselect = ((1 << self.resetpin) | (1 << self.cspin))
        outenable = chanselect
        state = ((0 << self.resetpin) | (1 << self.cspin))

        # change resetpin to low
        set_digital_state(thistime, self.connector, chanselect, outenable, state)

        thistime -= 800*self.spi_min_time
        state = ((1 << self.resetpin) | (1 << self.cspin))

        set_digital_state(thistime, self.connector, chanselect, outenable, state)


# look at self.seq after the sequence runs
class Sequence:
    def __init__(self):
        self.building = False
        self.local = True
        self.seqendindex = 0
        self.lengthpayload = 24
        self.lengthsequence = 2**20
        self.sizeofbytearray = self.lengthpayload * self.lengthsequence

        # Initial Settings
        self.seq = bytearray(self.sizeofbytearray)
        self.seqview = memoryview(self.seq)
        self.seqchainfirstcall = True
        self.seqchainlastruntime = 0

    def addElement(self, element):
        # element is a byte array whose length is a multiple of self.lengthpayload
        length_element = len(element)
        if (length_element % self.lengthpayload) != 0:
            raise ValueError('Length of \'element\' is not correct')

        length_buffer = len(self.seq)
        start_index = int(self.seqendindex * self.lengthpayload)
        length_empty_seq = int(length_buffer - start_index)

        if length_element > length_empty_seq:
            self.seqview.release()
            self.seq = self.seq + bytearray(self.sizeofbytearray * math.ceil(length_element / self.sizeofbytearray))
            self.seqview = memoryview(self.seq)
            print('new seqview')

        # print(start_index)
        # print(length_element)
        self.seqview[start_index:(start_index + length_element)] = element
        self.seqendindex += length_element / self.lengthpayload


    # def addElement(self, element):
    #     lengthelement = len(element)
    #     startindex = self.seqendindex * self.lengthpayload
    #     self.seqview[startindex:(startindex + lengthelement)] = element
    #     self.seqendindex += 1
    #     if self.seqendindex % self.lengthsequence == 0:
    #         self.seq = self.seq + bytearray(self.lengthpayload * self.lengthsequence)
    #         self.seqview.release()
    #         self.seqview = memoryview(self.seq)
    #         print('new seqview')

    def clear(self):
        self.building = False
        self.seqview.release()
        self.seq = bytearray(self.lengthpayload * self.lengthsequence)
        self.seqview = memoryview(self.seq)
        self.seqendindex = 0


def connect(timeout_sec=None):
    if(connmgr.localudp):
        connmgr.udp_local = UdpLocal()
    else:
        connmgr.udp_local = UdpMulticaster()
    connmgr.tcp_server = TcpServer()

    connmgr.udp_local.sendmsg(int(connmgr.tcp_server.serverport))
    try:
        (tcp_local, (lvip, lvport)) = connmgr.tcp_server.accept()
        print('Entangleware Software IP address:', lvip)
        if timeout_sec:
            tcp_local.settimeout(timeout_sec)
        connmgr.tcp_endpoint = TcpEndPoint(tcp_local)
        connmgr.isConnected = True
    except:
        print('Connection failed, shutting down...')


def disconnect():
    if connmgr.isConnected:
        connmgr.close()


def build_sequence():
    if msgseq.local:
        msgseq.building = True
    else:
        tosend = bytearray(0)
        connmgr.tcp_endpoint.sendmsg(tosend, 0, 16)
    return


def clear_sequence():
    if msgseq.local:
        msgseq.clear()
    else:
        tosend = bytearray(0)
        connmgr.tcp_endpoint.sendmsg(tosend, 0, 17)
    return


def rerun_last_sequence():
    pathtoTemp = pathlib.Path().absolute().__str__()+'\\LastCompiledRun.dat'
    with open(pathtoTemp, "rb") as in_file:
        tcpmessage = in_file.read()
    connmgr.tcp_endpoint.sendmsg(tcpmessage, 0, 22)
    runreturn = connmgr.tcp_endpoint.getmsg()
    runtime = struct.unpack('>d', runreturn[0])
    print(runtime[0])
    connmgr.tcp_endpoint._sock.settimeout(runtime[0]+20.5)
    donemsg = connmgr.tcp_endpoint.getmsg()
    connmgr.tcp_endpoint._sock.settimeout(10)
    return donemsg


# where it is packing up everything and sending over to entangleware software
def run_sequence():
    number_cycles = 1  # Don't Change (feature not yet implemented)
    tosend = bytearray(struct.pack('>l', number_cycles))
    tcpmessage = b""
    msgseq.seqendindex = int(msgseq.seqendindex)
    if msgseq.local:
        print(msgseq.seqendindex)
        tcpmessage = tosend + msgseq.seqview.tobytes()[:msgseq.seqendindex*msgseq.lengthpayload]
        connmgr.tcp_endpoint.sendmsg(tcpmessage, 0, 22)
        msgseq.clear()
    else:
        connmgr.tcp_endpoint.sendmsg(tosend, 0, 18)
    runreturn = connmgr.tcp_endpoint.getmsg()
    runtime = struct.unpack('>d', runreturn[0])
    print(runtime[0])
    pathtoTemp = pathlib.Path().absolute().__str__()+'\\LastCompiledRun.dat'
    with open(pathtoTemp, "wb") as out_file:
        out_file.write(tcpmessage)
    # 20.5 is a fudge factor to have a longer buffer for a timeout
    connmgr.tcp_endpoint._sock.settimeout(runtime[0]+20.5)
    # when we're waiting for deadtime we're waiting for this donemsg
    # sequence has a method .seq which is the sequence
    donemsg = connmgr.tcp_endpoint.getmsg()
    # print(donemsg == (bytearray(b'Done'), 15, 15)) # Returns 'True'
    connmgr.tcp_endpoint._sock.settimeout(10)
    # print("Sequence max time: ", max_time)
    # print("Sequence min time: ", min_time)
    return donemsg


def run_sequence_chain():
    if not msgseq.seqchainfirstcall:
        connmgr.tcp_endpoint._sock.settimeout(msgseq.seqchainlastruntime + 20.5)
        donemsg = connmgr.tcp_endpoint.getmsg()
        if donemsg != (bytearray(b'Done'), 15, 15):
            raise ValueError('Return from LV is unexpected')
        connmgr.tcp_endpoint._sock.settimeout(10)

    number_cycles = 1  # Don't Change (feature not yet implemented)
    tosend = bytearray(struct.pack('>l', number_cycles))
    tcpmessage = b""
    if msgseq.local:
        print(msgseq.seqendindex)
        tcpmessage = tosend + msgseq.seqview.tobytes()[:msgseq.seqendindex*msgseq.lengthpayload]
        connmgr.tcp_endpoint.sendmsg(tcpmessage, 0, 22)
        msgseq.clear()
    else:
        connmgr.tcp_endpoint.sendmsg(tosend, 0, 18)
    runreturn = connmgr.tcp_endpoint.getmsg()
    runtime = struct.unpack('>d', runreturn[0])
    msgseq.seqchainlastruntime = runtime[0]
    pathtoTemp = pathlib.Path().absolute().__str__()+'\\LastCompiledRun.dat'
    with open(pathtoTemp, "wb") as out_file:
        out_file.write(tcpmessage)
    msgseq.seqchainfirstcall = False
    return


def stop_sequence():
    number_cycles = 1
    tosend = bytearray(struct.pack('>l', number_cycles))
    connmgr.tcp_endpoint.sendmsg(tosend, 0, 19)
    return


def set_digital_state(seqtime, connector, channel_mask, output_enable_state, output_state):
    """Sets the digital output state.

    If 'build_sequence' hasn't been executed before this method, the method will ignore 'time' and immediately change
    the digital state.

    If 'build_sequence' has been executed before this method, the method will queue this state into the sequence which
    will execute, in time-order, after 'run_sequence' has been executed.

    Parameters:

        :param seqtime: Absolute time, in seconds, when state will change. (double)

        :param connector: Connector of the 7820R (unsigned 32-bit integer)

        :param channel_mask: Mask of the channel(s) to be changed (unsigned 32-bit integer)

        :param output_enable_state: State of output enable for the channel(s) to be changed (unsigned 32-bit integer)

        :param output_state: State of the channel(s) starting at 'time' (unsigned 32-bit integer)


    Returns:

        :return:
    """
    # global min_time
    # global max_time
    # if seqtime < min_time:
    #     min_time = seqtime
    # if seqtime > max_time:
    #     max_time = seqtime

    if msgseq.building and msgseq.local:
        if connector < 0 or connector > 3:
            connector = 0
        else:
            connector = connector + 1
        tosend = bytearray(struct.pack('>dLLLL', seqtime, connector, channel_mask, output_enable_state, output_state))
        msgseq.addElement(tosend)
    else:
        tosend = bytearray(struct.pack('>dLLLL', seqtime, connector, channel_mask, output_enable_state, output_state))
        connmgr.tcp_endpoint.sendmsg(tosend, 0, 20)
    return


def set_analog_state(seq_time, board, channel, value):
    # global min_time
    # global max_time
    # if seq_time < min_time:
    #     min_time = seq_time
    # if seq_time > max_time:
    #     max_time = seq_time

    numtype = (int, float)
    # print(type(seq_time))
    if isinstance(seq_time, numtype) and isinstance(board, numtype) and isinstance(channel, numtype) and \
            isinstance(value, numtype):
        if msgseq.building and msgseq.local:
            board_in_range = (board == 0 or board == 1)
            channel_in_range = (0 <= channel <= 7)
            output_enable_state = 0
            output_state = int((value / 20  ) * 2 ** 16)

            if output_state > (2**15 - 1):
                output_state = (2**15 - 1)

            if output_state < -2**15:
                output_state = -2**15

            if board_in_range and channel_in_range:
                shift_amount = board * 8 + channel
                connector = 5
                channel_mask = 1 << shift_amount
                to_send = bytearray(
                    struct.pack('>dLLLl', seq_time, connector, channel_mask, output_enable_state, output_state))
                msgseq.addElement(to_send)

        else:
            to_send = bytearray(struct.pack('>dBBd', seq_time, board, channel, value))
            connmgr.tcp_endpoint.sendmsg(to_send, 0, 21)
    elif isinstance(seq_time, list) and isinstance(board, numtype) and isinstance(channel, numtype) and \
            isinstance(value, list):
        print('in list mode')
        if msgseq.building and msgseq.local:
            board_in_range = (board == 0 or board == 1)
            channel_in_range = (0 <= channel <= 7)
            output_enable_state = 0

            if board_in_range and channel_in_range:
                shift_amount = board * 8 + channel
                connector = 5
                channel_mask = 1 << shift_amount

                length_payload = min(len(seq_time), len(value))
                seq_time = seq_time[:length_payload]
                connector = [connector]*length_payload
                channel_mask = [channel_mask]*length_payload
                output_enable_state = [output_enable_state]*length_payload

                value = value[:length_payload]
                output_state = [0]*length_payload

                for indx in range(length_payload):
                    output_state[indx] = int((value[indx] / 20) * 2 ** 16)

                    if output_state[indx] > (2 ** 15 - 1):
                        output_state[indx] = (2 ** 15 - 1)

                    if output_state[indx] < -2 ** 15:
                        output_state[indx] = -2 ** 15

                str_fmt = '>'+'dLLLl'*length_payload
                data_to_pack = [0]*5*length_payload
                data_to_pack[0::5] = seq_time
                data_to_pack[1::5] = connector
                data_to_pack[2::5] = channel_mask
                data_to_pack[3::5] = output_enable_state
                data_to_pack[4::5] = output_state
                to_send = bytearray(struct.pack(str_fmt, *data_to_pack))
                msgseq.addElement(to_send)
        else:
            raise ValueError
    else:
        raise ValueError
    return


connmgr = ConnectionManager()
dds = DDS()
msgseq = Sequence()
msgseq.local = True

if __name__ == "__main__":
    for numbers in range(5):
        print(str(numbers)+' connecting...')
        connect()
        if connmgr.isConnected:
            print('sending message to echo server...')
            connmgr.tcp_endpoint.sendmsg(b'Hello LV', numbers, 0x80000000)
            print(connmgr.tcp_endpoint.getmsg())
            time.sleep(1)
        else:
            print('not connected')

        time.sleep(0)
        print('disconnecting...')
        disconnect()
