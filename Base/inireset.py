from Base.constants import *
from functools import partial
from Base.timing import Sequence
import Base.channels as ch
import Base.boards as brd
import Base.outputwrappers as out
import Base.magnetics as mag
import Base.masterrepump as laser
import MidLevelSeq.MOT as mot


class Reset(Sequence):
    def __init__(self):
        """ Resets the peripheral hardware of the apparatus."""
        super().__init__()
        self.dds1 = brd.AD9959(ch.ad9959_1["connector"], ch.ad9959_1["io"], ch.ad9959_1["clk"],
                               ch.ad9959_1["reset"], ch.ad9959_1["update"], ch.ad9959_1["ref_clk"],
                               ch.ad9959_1["ref_multiplier"])
        self.dds2 = brd.AD9959(ch.ad9959_2["connector"], ch.ad9959_2["io"], ch.ad9959_2["clk"],
                               ch.ad9959_2["reset"], ch.ad9959_2["update"], ch.ad9959_2["ref_clk"],
                               ch.ad9959_2["ref_multiplier"])
        self.dds_evap = brd.AD9854(ch.ad9854_evap["connector"], ch.ad9854_evap["io"], ch.ad9854_evap["clk"],
                                   ch.ad9854_evap["reset"], ch.ad9854_evap["update"], ch.ad9854_evap["ref_clk"],
                                   ch.ad9854_evap["ramp_rate_clk"])
        self.xp = brd.XPSwitch(ch.xp_switch)
        self.dac = brd.AD5372(ch.slow_dac["connector"], ch.slow_dac["io"], ch.slow_dac["clk"], ch.slow_dac["sync"],
                              ch.slow_dac["ldac"])

    @Sequence._update_time
    def general(self, seq_time):
        """Resets the DDSs for RF evaporation, lattice, dipole, microwaves, speckle, and Raman beams. Resets the slow
        DAC, crosspoint switch, and analog lines.

        :param seq_time:Execution time (sec)
        :type seq_time: float
        :rtype: float
        :return: elapsed time (500.002*ms)
        """
        self.abs(100*ms, analog_out_reset)
        self.abs(200*ms, self.dds1.reset)
        self.abs(250*ms, self.dds2.reset)
        self.abs(300*ms, self.dds_evap.reset)
        self.abs(400 * ms, self.xp.initialize)
        self.abs(500*ms, self.dac.initialize)

    @Sequence._update_time
    def laser_locks(self, seq_time):
        """Resets the AD9959 used for locking master and repump laser. Initializes the DDS for MOT.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: Elapsed time
        """
        res = partial(laser.init_laser_locks, fmaster=laser.fMOT, frepump=laser.fRepump)
        self.abs(100*ms, res)


def analog_out_reset(seq_time):
    """Sets all the analog channels to output 0V.

    :param seq_time: Execution time (s)
    :type seq_time: float
    :rtype: float
    :return: Elapsed time (2us)
    """
    out.analog_out(seq_time, 0, 1, 0)
    out.analog_out(seq_time, 0, 2, 0)
    out.analog_out(seq_time, 0, 3, 0)
    out.analog_out(seq_time, 0, 4, 0)
    out.analog_out(seq_time, 0, 5, 0)
    out.analog_out(seq_time, 0, 6, 0)
    out.analog_out(seq_time, 0, 7, 0)
    out.analog_out(seq_time, 1, 0, 0)
    out.analog_out(seq_time, 1, 1, 0)
    out.analog_out(seq_time, 1, 2, 0)
    out.analog_out(seq_time, 1, 3, 0)
    out.analog_out(seq_time, 1, 4, 0)
    out.analog_out(seq_time, 1, 5, 0)
    out.analog_out(seq_time, 1, 6, 0)
    out.analog_out(seq_time, 1, 7, 0)
    return out.analog_time_step


class Repeat(Sequence):
    def __init__(self):
        """Sets apparatus back up to begin again after an experimental sequence is run"""
        super().__init__()
        self.recap = mot.Recap()
        # dummy transition
        self.qp6 = partial(mag.cart_digital_setpoint, i=6)

    @Sequence._update_time
    def seq(self, seq_time):
        """Fills the MOT for the next shot after a sequence is run. Uses a dummy transition to make the sequencer
        wait for the MOT to refill before signaling that it is ready for the next shot.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: 0 effective elapsed time
        """
        refill_time = 30
        self.abs(100*ms, self.recap.mot_recap)
        # dummy transition to the default value to make Entangleware care about this total time
        self.rel(refill_time, self.qp6)
        self.abs(0.00)
