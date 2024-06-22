from Base import boards as brd
from Entangleware import ew_link as ew
from functools import partial
from Base.constants import *
from Base.timing import Sequence
import math
import Base.outputwrappers as out
import Base.channels as ch


class RFSwitch:
    @staticmethod
    def on(seq_time):
        t = out.digital_out(seq_time, ch.rf_switch["connector"], ch.rf_switch["pin"], 1)
        return t

    @staticmethod
    def off(seq_time):
        t = out.digital_out(seq_time, ch.rf_switch["connector"], ch.rf_switch["pin"], 1)
        return t


class RampOff(Sequence):
    def __init__(self, power):
        super().__init__()
        self.dds = brd.AD9854(ch.ad9854_evap["connector"], ch.ad9854_evap["io"], ch.ad9854_evap["clk"],
                              ch.ad9854_evap["reset"], ch.ad9854_evap["update"], ch.ad9854_evap["ref_clk"],
                              ch.ad9854_evap["ramp_rate_clk"])
        total_time = 10*ms
        num_steps = 10
        freq_list = [0*MHz for t in range(num_steps + 1)]
        pow_list = [power + 10 * math.log(1 - t/5, 10) if (1 - t/5) > 0 else float('-inf') for t in range(num_steps)]
        self.ramp = partial(self.dds.arbitrary_output, chirp=True, total_time=total_time, freq_list=freq_list,
                            power_list=pow_list)

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0, self.ramp)


class RFSweep(Sequence):
    def __init__(self, f_start, f_stop, slope):
        super().__init__()
        tt = (f_start - f_stop)/slope
        num_steps = 5
        power = -18*dBm
        freq_list = [f_start + (f_stop - f_start)*t/num_steps for t in range(num_steps+1)]
        pow_list = [power for t in range(num_steps)]
        self.dds = brd.AD9854(ch.ad9854_evap["connector"], ch.ad9854_evap["io"], ch.ad9854_evap["clk"],
                              ch.ad9854_evap["reset"], ch.ad9854_evap["update"], ch.ad9854_evap["ref_clk"],
                              ch.ad9854_evap["ramp_rate_clk"], f_initial=f_start)
        self.sweep = partial(self.dds.arbitrary_output, chirp=True, total_time=tt, freq_list=freq_list,
                             power_list=pow_list)
        self.off = RampOff(power)

    @Sequence._update_time
    def linear(self, seq_time):
        self.abs(-10 * ms, self.dds.chirp_initialize)
        self.abs(0, RFSwitch.on)
        self.abs(0, self.sweep)
        self.rel(0, [RFSwitch.off, self.off.seq])

