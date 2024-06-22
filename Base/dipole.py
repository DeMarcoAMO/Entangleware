from Base.timing import Sequence
from functools import partial
from Base.constants import *
import Base.outputwrappers as out
import Base.channels as ch
import Base.boards as brd


# calibration done by PR 09/25/2015
def d1_power(p):
    """Returns servo setpoint voltage for a desired dipole power (calibrated to photodetector)

    :param p: dipole power (mW)
    :type p: float
    :rtype: float
    :return: Servo setpoint voltage (V)
    """
    # v = (p*0.0003295) + 0.0023
    # updated 04/25/24 Rb#27 pg. 23
    v = (p*.00035041) - 0.05739
    return v


class DipoleBeam(Sequence):
    def __init__(self, depth_high=10000*mW, depth_low=1700*mW, depth_final=1800*mW, ramp_time=10*sec, up_time=200*ms,
                 compress_time=200*ms, tau=5*sec):
        """Controls 20W 1064nm IPG Fiber laser used for optical dipole trap.

        :param depth_high: Initial power of the laser/optical trap depth (W)
        :type depth_high: float
        :param depth_low: End power of the evaporative cooling ramp (lowest optical trap depth) (W)
        :type depth_low: float
        :param depth_final: Final laser power after recompressing the trap (W)
        :type depth_final: float
        :param ramp_time: Evaporative cooling ramp duration (s)
        :type ramp_time: float
        :param up_time: Time to turn laser on to depth_high (s)
        :type up_time: float
        :param compress_time: Duration of recompression ramp (s)
        :type compress_time: float
        :param tau: Time constant for exponential evaporative cooling ramp (s)
        :type tau: float
        """
        super().__init__()
        # power = min(p_down, 0)
        pow_off = 0
        # Instance of AD9959 used to generate RF signal for dipole beam AOM
        dds = brd.AD9959(connector=ch.ad9959_1["connector"], io_pin=ch.ad9959_1["io"], serial_clock_pin=ch.ad9959_1["clk"],
                         reset_pin=ch.ad9959_1["reset"], io_update_pin=ch.ad9959_1["update"],
                         ref_clock=ch.ad9959_1["ref_clk"], ref_clk_multiplier=ch.ad9959_1["ref_multiplier"])
        channel = 3

        # Set servo setpoint negative to force laser off
        self.unlock = partial(out.analog_out, connector=ch.dipole_servo["connector"],
                              channel=ch.dipole_servo["channel"], value=-1.00)
        self.bias = partial(out.analog_out, connector=ch.dipole_servo["connector"], channel=ch.dipole_servo["channel"],
                            value=-0.002)
        self.dds_on = partial(dds.arbitrary_output, channel_mask=channel, freq_list=[80 * MHz], power_list=[pow_off], tt=1 * ms)
        self.dds_off = partial(dds.arbitrary_output, channel_mask=channel, freq_list=[0 * MHz], power_list=[float('-inf')], tt=0)

        pow0 = d1_power(depth_high)
        pow1 = d1_power(depth_low)
        pow2 = d1_power(depth_final)
        self.ramp = out.AnalogRamp(board=ch.dipole_servo["connector"], channel=ch.dipole_servo["channel"],
                                   val_start=pow0, val_end=pow1, total_time=ramp_time, tau=tau)
        self.on_ramp = out.AnalogRamp(board=ch.dipole_servo["connector"], channel=ch.dipole_servo["channel"],
                                      val_start=d1_power(0), val_end=pow0, total_time=up_time)
        self.comp_ramp = out.AnalogRamp(board=ch.dipole_servo["connector"], channel=ch.dipole_servo["channel"],
                                        val_start=pow1, val_end=pow2, total_time=compress_time, a=10)

    @Sequence._update_time
    def on(self, seq_time):
        """Sets laser on to zero power. Start AD9959 outputting 80MHz and gets servo loop ready to turn on.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (0s)
        """
        # force VGA off
        self.abs(-300*ms, self.unlock)
        # setup DDS
        self.abs(-200*ms, self.dds_on)
        # bias servo
        self.abs(-30*ms, self.bias)
        self.abs(0.00)

    @Sequence._update_time
    def off(self, seq_time):
        """Turns laser off. Stops AD9959 and sets servo setpoint to be negative.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (0.252*ms)
        """
        self.abs(0.00, self.dds_off)
        self.abs(0.25*ms, self.unlock)

    @Sequence._update_time
    def linear_ramp(self, seq_time):
        """Linearly change laser power from depth_high to depth_low over time ramp_time.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (ramp_time)
        """
        self.abs(0.00, self.ramp.linear)

    @Sequence._update_time
    def exp_ramp(self, seq_time):
        """Exponential change laser power from depth_high to depth_low over time ramp_time with time constant tau.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (ramp_time)
        """
        self.abs(0.00, self.ramp.exponential_down)

    @Sequence._update_time
    def ramp_up(self, seq_time):
        """Linearly increased laser power from 0 up to depth_high over time up_time.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (up_time)
        """
        self.abs(0.00, self.on_ramp.linear)

    @Sequence._update_time
    def recompress(self, seq_time):
        """Sigmoidally changes laser power from depth_low to depth_final over time compress_time

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (compress_time)
        """
        self.abs(0.00, self.comp_ramp.sigmoidal)


class DDSKick(Sequence):
    def __init__(self, p_down, delta, kick_time, depth_final=0):
        super().__init__()
        dds = brd.AD9959(connector=ch.ad9959_1["connector"], io_pin=ch.ad9959_1["io"], serial_clock_pin=ch.ad9959_1["clk"],
                         reset_pin=ch.ad9959_1["reset"], io_update_pin=ch.ad9959_1["update"],
                         ref_clock=ch.ad9959_1["ref_clk"], ref_clk_multiplier=ch.ad9959_1["ref_multiplier"])
        channel = 3
        power = min(p_down, 0)
        self.time = kick_time
        self.dds_change = partial(dds.arbitrary_output, channel_mask=channel, freq_list=[80 * MHz + delta], power_list=[power],
                                  tt=1*ms)
        self.dds0 = partial(dds.arbitrary_output, channel_mask=channel, freq_list=[80 * MHz], power_list=[power], tt=0.2 * ms)
        self.dds_off = partial(dds.arbitrary_output, channel_mask=channel, freq_list=[80 * MHz], power_list=[float('-inf')],
                               tt=0.2*ms)
        self.unlock = partial(out.analog_out, connector=ch.dipole_servo["connector"],
                              channel=ch.dipole_servo["channel"], value=-1.00)
        pow_final = d1_power(depth_final)
        self.analog_final = partial(out.analog_out, connector=ch.dipole_servo["connector"],
                                    channel=ch.dipole_servo["channel"], value=pow_final)

    @Sequence._update_time
    def kick(self, seq_time):
        self.abs(0.00, self.dds_change)
        self.abs(self.time, self.dds0)

    @Sequence._update_time
    def drop(self, seq_time):
        self.abs(0.00, self.dds_off)
        self.abs(-10*us, self.unlock)
        self.abs(self.time, self.dds0)
        self.abs(self.time-210*us, self.analog_final)
        self.abs(self.time)
