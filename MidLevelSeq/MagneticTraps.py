from functools import partial
from Base.timing import Sequence
from Base.constants import *
import MidLevelSeq.MOT as MOT
import Base.masterrepump as laser
import Base.outputwrappers as out
import Base.magnetics as mag
import Base.channels as ch
import Base.rf as rf

# transfer parameters
transfer_ag_current = 5.0
transfer_bias_current = 0
final_ag_current = 0.5


class SciCellLoad(Sequence):
    def __init__(self):
        """Loads the atoms into the cart quadrupole trap from the MOT and moves them down to the science cell.
        """
        super().__init__()
        # duration of compressed MOT (CMOT) stage
        self.t_cmot = 50
        self.qp_cap = MOT.QPCaptureF1()
        self.arduino_trigger = partial(out.digital_out, connector=ch.arduino_trigger["connector"],
                                       channel=ch.arduino_trigger["pin"], state=1)

        self.dig_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.dig_off = partial(out.digital_out, connector=3, channel=7, state=0)

    @Sequence._update_time
    def seq(self, seq_time):
        """Executes QP Capture and moves cart to science cell.
        Triggers arduino to signal imaging computer that sequence has begun.

        :param seq_time: Execution time (sec)
        :type seq_time: float
        :rtype: float
        :return: Elapsed time 3.7s
        """
        self.abs(0, self.arduino_trigger)
        self.abs(100*ms - self.t_cmot * ms, laser.Detuning().cmot)
        self.abs(100 * ms, self.qp_cap.seq)
        self.abs(200 * ms, out.move_cart_prun)
        self.abs(3700 * ms)


class CartEvap(Sequence):
    def __init__(self, start=65*MHz, stop=5*MHz, rate=1.5*MHz/sec):
        """RF evaporation of atoms in cart QP trap in science cell after loading science cell.

        :param start: starting frequency for variable evaporation (Hz)
        :type start: float
        :param stop: final frequency for variable evaporation (Hz)
        :type stop: float
        :param rate: rate of frequency change (Hz/s)
        :type rate: float
        """
        super().__init__()
        self.sci_load = SciCellLoad()
        self.start = start
        self.stop = stop
        self.rate = rate

    @Sequence._update_time
    def tight(self, seq_time):
        """Does SciCellLoad and fixed evaporation in CartQP. Used for loading into pinch quadrupole.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (24.2 sec)
        """
        evap = rf.RFSweep(70*MHz, 40*MHz, 1.25*MHz/sec)
        # evap = rf.RFSweep(65 * MHz, 40 * MHz, 1.25 * MHz / sec)
        self.abs(0.00, self.sci_load.seq)
        self.rel(200*ms, evap.linear)

    @Sequence._update_time
    def variable(self, seq_time):
        """Load science cell and variable evaporation in cart trap, using instance parameters.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (0.02s + (start-stop)/rate)
        """
        evap = rf.RFSweep(self.start, self.stop, self.rate)
        self.abs(0.00, self.sci_load.seq)
        self.rel(20 * ms, evap.linear)


class PinchTransfer(Sequence):
    def __init__(self, ag_down=True):
        super().__init__()
        self.ag_down = ag_down
        self.qp = mag.CartQP()
        self.ag = mag.AGCoil(i0=transfer_ag_current, i1=final_ag_current, total_time=1)
        # self.ag = mag.AGSet(i0=final_ag_current, i1=final_ag_current, total_time=1)
        self.pinch_bias = mag.PinchBiasSet(ip0=585.0-transfer_bias_current, ib0=transfer_bias_current)

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.qp.off)
        self.abs(-1*ms, self.ag.snap_on)
        self.abs(-1*ms, self.pinch_bias.snap_on)
        if self.ag_down:
            self.abs(100*ms, self.ag.ramp)
        self.abs(200*ms)


class PinchLoad(Sequence):
    def __init__(self, ag_down=True):
        super().__init__()
        self.cart_evap = CartEvap()
        self.transfer = PinchTransfer(ag_down)
        self.pb_ramp = mag.PinchBiasSet(ip0=585.0-transfer_bias_current, ip1=585, ib0=transfer_bias_current, ib1=0,
                                        total_time=1000*ms)
        self.bias_dig_off = partial(mag.bias_digital_setpoint, i=0)

        self.test_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.test_off = partial(out.digital_out, connector=3, channel=7, state=0)

    # N.E.K. 07/26/2023 added ramp bias off and pinch up to 585
    @Sequence._update_time
    def tight(self, seq_time):
        self.abs(0.00, self.cart_evap.tight)
        self.rel(100 * ms, self.transfer.seq)
        self.rel(200 * ms, out.move_cart_prun)
        # self.rel(200*ms, [self.test_on, out.move_cart_prun, self.pb_ramp.ramp])
        # self.rel(0.00, self.bias_dig_off)
        # self.rel(0.00, self.test_off)


# this sequence combines the old PinchQP_TightEvap and PinchQP_Evap3 into 1. Watch timing if adding back in AG pre-tilt
class PinchEvap(Sequence):
    def __init__(self, start1=50*MHz, stop1=8*MHz, rate1=1.75*MHz/sec, start2=8*MHz, stop2=3.5*MHz, rate2=4*MHz/sec):
        super().__init__()
        self.load = PinchLoad()
        self.evap1 = rf.RFSweep(start1, stop1, rate1)
        self.evap2 = rf.RFSweep(start2, stop2, rate2)

    @Sequence._update_time
    def tight(self, seq_time):
        # evap1 = rf.RFSweep(50 * MHz, 12 * MHz, 1.75 * MHz / sec)
        evap1 = rf.RFSweep(50*MHz, 8*MHz, 1.75*MHz/sec)
        evap2 = rf.RFSweep(8*MHz, 3.5*MHz, 4*MHz/sec)
        self.abs(0.00, self.load.tight)
        self.rel(200*ms, evap1.linear)
        self.rel(25*ms, evap2.linear)

    @Sequence._update_time
    def var(self, seq_time):
        self.abs(0.00, self.load.tight)
        self.rel(200*ms, self.evap1.linear)
        # self.rel(25*ms, self.evap2.linear)


class CartRelease(Sequence):
    def __init__(self):
        super().__init__()
        self.qp0 = partial(mag.cart_digital_setpoint, i=0)
        self.img_coil = mag.ImagingCoil()
        self.qp = mag.CartQP()
        self.ag = mag.AGCoil()
        self.test_on = partial(out.digital_out, connector=2, channel=16, state=1)
        self.test_off = partial(out.digital_out, connector=2, channel=16, state=0)

    # use with sci cell load
    @Sequence._update_time
    def sci_cell(self, seq_time):
        self.abs(0, self.qp0)
        self.abs(5*ms, mag.CartSupply.mot)
        # imaging coil must turn on when trapping field shuts off
        self.abs(0.2*ms, self.img_coil.on)
        self.abs(0.2*ms, self.test_on)
        self.abs(55.12*ms, self.img_coil.off)
        self.abs(55.12*ms, self.test_off)
        self.abs(0.00)

    # For use with cart evap sequences
    # basically the same as the above sequence, but with slightly different imaging coil timing
    @Sequence._update_time
    def evap(self, seq_time):
        self.abs(0.00, self.ag.off)
        self.abs(0.00, self.qp.off)
        self.abs(0.10*ms, self.img_coil.on)
        self.abs(0.10*ms, self.test_on)
        self.abs(55.12*ms, self.img_coil.off)
        self.abs(55.12*ms, self.test_off)
        self.abs(0.00)


class PinchRelease(Sequence):
    def __init__(self, ip=126.5, i_bias=14.5):
        super().__init__()
        self.pinch = mag.PinchBiasSet(ip)
        self.image_coil = mag.ImagingCoil()
        self.ag = mag.AGCoil(i0=0, i1=25, total_time=0.2 * ms)

        self.bias = mag.BiasSet(total_time=0.75 * ms, ib0=0, ib1=i_bias)
        self.bias_off = mag.BiasSet(total_time=0.75*ms, ib0=i_bias, ib1=0)
        self.test_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.test_off = partial(out.digital_out, connector=3, channel=7, state=0)

        # servo/supply states and ramps needed to ramp the pinch and bias for bias quant imaging
        # when the pinch turns off from 585A and then the bias ramps on to i_bias ramp the supply appropriately over 1ms
        voltage = mag.pinch_bias_voltage(ip=585.0-transfer_bias_current, ib=0)
        voltage1 = mag.pinch_bias_voltage(ip=0, ib=i_bias)
        self.voltage_ramp = out.AnalogRamp(board=ch.pinch_bias_supply["connector"],
                                           channel=ch.pinch_bias_supply["channel"], val_start=voltage, val_end=voltage1,
                                           total_time=0.5*ms)
        # ramp the bias servo on
        bias_setpt = mag.bias_setpoint(0)
        bias_setpt1 = mag.bias_setpoint(i_bias)
        self.dig_bias = partial(mag.bias_digital_setpoint, i=1)
        self.bias0 = partial(out.analog_out, connector=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                             value=bias_setpt)
        self.bias_ramp = out.AnalogRamp(board=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                        val_start=bias_setpt, val_end=bias_setpt1, total_time=0.75*ms)

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.ag.off)
        self.abs(-1 * ms, self.pinch.off_qp)
        self.abs(-3*ms, self.image_coil.on)
        # self.abs(-3*ms, self.test_on)
        self.abs(55.12*ms, self.image_coil.off)
        # self.abs(55.12*ms, self.test_off)
        self.abs(0.00)

    @Sequence._update_time
    def seq_ag(self, seq_time):
        self.abs(-1 * ms, self.pinch.off_qp)
        self.abs(-3 * ms, self.image_coil.on)
        self.abs(0.00, self.ag.switch_on)
        self.abs(2 * ms, self.ag.ramp)
        self.abs(55.12 * ms, self.image_coil.off)
        self.abs(0.00)
