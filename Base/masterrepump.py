from functools import partial
from Base import boards as brd
from Base.timing import Sequence
from Entangleware import ew_link as ew
from Base.constants import *
import Base.outputwrappers as out
import Base.channels as ch

lock_dds = brd.AD9959(ch.ad9959_3["connector"], ch.ad9959_3["io"], ch.ad9959_3["clk"],
                      ch.ad9959_3["reset"], ch.ad9959_3["update"], ch.ad9959_3["ref_clk"],
                      ch.ad9959_3["ref_multiplier"])
xp_switch = brd.XPSwitch(ch.xp_switch)
master_channel = 0
repump_channel = 1
mod_channel = 4

fMOT = 68 * MHz
# fCMOT = 58 * MHz
# Changed 02/09/2022 by N.E.K.
fCMOT = 55 * MHz
fRepump = 208.45 * MHz
# Default is for repump detuning to be twice as much as the master detuning
# fRepumpCMOT = fRepump + 2 * (fCMOT - fMOT)/32
# Changed 02/09/2022 by N.E.K. to be 40MHz closer to resonance
fRepumpCMOT = fRepump + -(50*MHz)/32


# laser frequency sequences
class Detuning(Sequence):
    def __init__(self):
        super().__init__()
        self.cmot = partial(jumpECDLs, fmaster=fCMOT, frepump=fRepumpCMOT)
        self.mot = partial(jumpECDLs, fmaster=fMOT, frepump=fRepump)
        self.align = partial(jumpECDLs, fmaster=60*MHz, frepump=fRepump)
        self.dig_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.dig_off = partial(out.digital_out, connector=3, channel=7, state=0)

    @Sequence._update_time
    def cmot(self, seq_time):
        self.abs(0, self.cmot)
        self.abs(0, MasterCurrent.cmot)

    @Sequence._update_time
    def mot(self, seq_time):
        self.abs(0, self.mot)
        self.abs(0, MasterCurrent.mot)

    @Sequence._update_time
    def align(self, seq_time):
        self.abs(0, self.align)
        self.abs(0, MasterCurrent.mot)

    @Sequence._update_time
    def jump_test(self, seq_time):
        self.abs(0, self.cmot)
        self.abs(0, MasterCurrent.cmot)
        self.abs(0, self.dig_on)
        self.abs(1, self.mot)
        self.abs(1, MasterCurrent.mot)
        self.rel(1, self.dig_off)


class RepumpTuning(Sequence):
    def __init__(self):
        super().__init__()
        self.img = partial(jumpRepumpECDL, fset=fRepump - 80*MHz/32)
        self.on_resonance = partial(jumpRepumpECDL, fset=fRepump - 6*MHz/32)
        self.norm = partial(jumpRepumpECDL, fset=fRepump)

    @Sequence._update_time
    def imaging(self, seq_time):
        self.abs(0.00, self.img)

    @Sequence._update_time
    def on_res(self, seq_time):
        self.abs(0.00, self.on_resonance)

    @Sequence._update_time
    def normal(self, seq_time):
        self.abs(0.00, self.norm)


# Laser Powers XP Switch
class MasterCurrent:

    @staticmethod
    def cmot(seq_time):
        t_delay = 0.184 * ms
        xp_switch.switch(seq_time, 1, 15, 14)
        return t_delay

    @staticmethod
    def mot(seq_time):
        t_delay = 0.184 * ms
        xp_switch.switch(seq_time, 1, 14, 15)
        return t_delay


class RepumpCurrent:

    @staticmethod
    def cmot(seq_time):
        t_delay = 0.184 * ms
        xp_switch.switch(seq_time, 2, 15, 2)
        return t_delay

    @staticmethod
    def mot(seq_time):
        t_delay = 0.184 * ms
        xp_switch.switch(seq_time, 2, 2, 15)
        return t_delay

    @staticmethod
    def molasses(seq_time):
        t_delay = 0.184 * ms
        xp_switch.switch(seq_time, 2, 2, 15)
        return t_delay


# AOM sequences
class RepumpAOM:

    @staticmethod
    def on(seq_time):
        t = out.digital_out(seq_time, ch.aom["connector"], ch.aom["repump"], 0)
        return t

    @staticmethod
    def off(seq_time):
        t = out.digital_out(seq_time, ch.aom["connector"], ch.aom["repump"], 1)
        return t


class OPAOM:

    @staticmethod
    def on(seq_time):
        t = out.digital_out(seq_time, ch.aom["connector"], ch.aom["op"], 0)
        return t

    @staticmethod
    def off(seq_time):
        t = out.digital_out(seq_time, ch.aom["connector"], ch.aom["op"], 1)
        return t


class ProbeAOM:

    @staticmethod
    def on(seq_time):
        t = out.digital_out(seq_time, ch.aom["connector"], ch.aom["probe"], 0)
        return t

    @staticmethod
    def off(seq_time):
        t = out.digital_out(seq_time, ch.aom["connector"], ch.aom["probe"], 1)
        return t


# Shutters
class TrapShutter:

    def __init__(self):
        self.trap1 = ch.mot_shutters["one"]
        self.trap2 = ch.mot_shutters["two"]
        self.trap3 = ch.mot_shutters["three"]
        self.connector = ch.mot_shutters["connector"]

    def close(self, seq_time, trap):
        if trap == 1:
            channel = self.trap1
            offset = 1.16 * ms
        if trap == 2:
            channel = self.trap2
            offset = 1.46 * ms
        if trap == 3:
            channel = self.trap3
            offset = 1.58 * ms
        t = out.digital_out(seq_time - offset, self.connector, channel, 1)
        return -offset + t

    def close_full(self, seq_time, trap):
        if trap == 1:
            channel = self.trap1
            offset = 1.425 * ms
        if trap == 2:
            channel = self.trap2
            offset = 1.18 * ms
        if trap == 3:
            channel = self.trap3
            offset = 1.72 * ms
        t = out.digital_out(seq_time - offset, self.connector, channel, 1)
        return -offset + t

    def open(self, seq_time, trap):
        if trap == 1:
            channel = self.trap1
            offset = 1.43 * ms
        if trap == 2:
            channel = self.trap2
            offset = 1.46 * ms
        if trap == 3:
            channel = self.trap3
            offset = 1.72 * ms
        t = out.digital_out(seq_time - offset, self.connector, channel, 0)
        return -offset + t

    def open_full(self, seq_time, trap):
        if trap == 1:
            channel = self.trap1
            offset = 1.63 * ms
        if trap == 2:
            channel = self.trap2
            offset = 1.58 * ms
        if trap == 3:
            channel = self.trap3
            offset = 1.79 * ms
        t = out.digital_out(seq_time - offset, self.connector, channel, 0)
        return -offset + t

    def open_start(self, seq_time, trap):
        if trap == 1:
            channel = self.trap1
            offset = 1.15 * ms
        if trap == 2:
            channel = self.trap2
            offset = 1.40 * ms
        if trap == 3:
            channel = self.trap3
            offset = 1.67 * ms
        t = out.digital_out(seq_time - offset, self.connector, channel, 0)
        return -offset + t

    def open_all(self, seq_time):
        self.open(seq_time, 1)
        self.open(seq_time, 2)
        t = self.open(seq_time, 3)
        return t

    def close_all(self, seq_time):
        self.close(seq_time, 1)
        self.close(seq_time, 2)
        t = self.close(seq_time, 3)
        return t

    def close_all_full(self, seq_time):
        self.close_full(seq_time, 1)
        self.close_full(seq_time, 2)
        t = self.close_full(seq_time, 3)
        return t


class RepumpShutter:
    @staticmethod
    def open(seq_time):
        offset = 1.76 * ms
        t = out.digital_out(seq_time - offset, ch.repump_shutter["connector"], ch.repump_shutter["pin"], 0)
        return t - offset

    @staticmethod
    def close(seq_time):
        offset = 1.16 * ms
        t = out.digital_out(seq_time - offset, ch.repump_shutter["connector"], ch.repump_shutter["pin"], 1)
        return t - offset

    @staticmethod
    def open_full(seq_time):
        offset = 1.90 * ms
        t = out.digital_out(seq_time - offset, ch.repump_shutter["connector"], ch.repump_shutter["pin"], 0)
        return t - offset

    @staticmethod
    def open_start(seq_time):
        offset = 1.63 * ms
        t = out.digital_out(seq_time - offset, ch.repump_shutter["connector"], ch.repump_shutter["pin"], 0)
        return t - offset

    @staticmethod
    def close_full(seq_time):
        offset = 1.61 * ms
        t = out.digital_out(seq_time - offset, ch.repump_shutter["connector"], ch.repump_shutter["pin"], 1)
        return t - offset


class ProbeShutter:
    @staticmethod
    def open(seq_time):
        offset = 1.18 * ms
        t = out.digital_out(seq_time - offset, ch.probe_shutter["connector"], ch.probe_shutter["pin"], 1)
        return t - offset

    @staticmethod
    def close(seq_time):
        offset = 1.28 * ms
        t = out.digital_out(seq_time - offset,  ch.probe_shutter["connector"], ch.probe_shutter["pin"], 0)
        return t - offset


class OPShutter:
    @staticmethod
    def open(seq_time):
        offset = 1.46 * ms
        t = out.digital_out(seq_time - offset, ch.op_shutter["connector"], ch.op_shutter["pin"], 1)
        return t - offset

    @staticmethod
    def close(seq_time):
        offset = 0.96 * ms
        t = out.digital_out(seq_time - offset, ch.op_shutter["connector"], ch.op_shutter["pin"], 0)
        return t - offset


class ProbePulse:
    @staticmethod
    def pulse(seq_time):
        t = seq_time
        probe_time = 0.044*ms
        ProbeAOM().off(t - 10*ms)
        ProbeShutter().open(t - 1*ms)
        t += ProbeAOM().on(t)
        t += probe_time
        t += ProbeAOM().off(t)
        ProbeShutter().close(t+2*ms)
        return t - seq_time

    @staticmethod
    def pulse_fast_aom(seq_time, probe_time=0.044*ms):
        """Pulses the probe beam on and off again. Makes sure the AOM is off and opens the shutter

        :param seq_time: execution time
        :type seq_time: float
        :param probe_time: duration of probe pulse
        :type probe_time: float
        :rtype: float
        :return: elapsed time
        """
        t = seq_time
        # probe_time = 0.044*ms
        ProbeAOM().off(t - 1.1 * ms)
        ProbeShutter().open(t - 1 * ms)
        t += ProbeAOM().on(t)
        t += probe_time
        t += ProbeAOM().off(t)
        ProbeShutter().close(t + 2 * ms)
        return t - seq_time

# functions for changing the master/repump DDS
def init_laser_locks(seq_time, fmaster, frepump):
    time = seq_time
    time += lock_dds.reset(time)
    time += 10*ms
    time += lock_dds.arbitrary_output(time, master_channel, [fmaster], [-9 * dBm], 1 * ms)
    time += 10*ms
    time += lock_dds.arbitrary_output(time, repump_channel, [frepump], [-15 * dBm], 1 * ms)
    return time


def jumpECDLs(seq_time, fmaster, frepump):
    t = 1 * ms
    lock_dds.arbitrary_output(seq_time, master_channel, [fmaster], [-9 * dBm], t)
    lock_dds.arbitrary_output(seq_time - 2 * ms, repump_channel, [frepump], [-15 * dBm], t, no_ud=True)
    return t - 2*ms


def jumpMasterECDL(seq_time, fset):
    t = 1 * ms
    lock_dds.arbitrary_output(seq_time, master_channel, [fset], [-9 * dBm], t)
    return t


def jumpRepumpECDL(seq_time, fset):
    t = 1 * ms
    lock_dds.arbitrary_output(seq_time, repump_channel, [fset], [-15 * dBm], t)
    return t


def align_lock(seq_time):
    t = jumpMasterECDL(seq_time + 100*ms, 60*MHz)
    return t
