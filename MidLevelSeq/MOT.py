from Base.timing import Sequence
import Base.masterrepump as laser
from Base.constants import *
from functools import partial
import Entangleware.ew_link as ew
import Base.magnetics as mag
import Base.outputwrappers as out
import Base.inireset as rst


class OpticalPumping(Sequence):

    @Sequence._update_time
    def on(self, seq_time):
        self.abs(-15 * ms, laser.OPAOM.off)
        self.abs(-7.5 * ms, laser.OPShutter().open)
        self.abs(0, laser.OPAOM.on)

    @Sequence._update_time
    def off(self, seq_time):
        self.abs(0, laser.OPAOM.off)
        self.abs(7.5 * ms, laser.OPShutter().close)
        self.abs(15 * ms, laser.OPAOM.on)


class QPCaptureF1(Sequence):
    def __init__(self):
        super().__init__()
        self.qp0 = partial(mag.cart_digital_setpoint, i=0)
        self.qp_on = mag.CartQP()

    @Sequence._update_time
    def seq(self, seq_time):
        # molasses on
        self.abs(-7.50 * ms, mag.Shims().molasses)
        self.abs(-7 * ms, self.qp0)  # Quadrupole coils off
        # self.abs(-6.50 * ms, mag.Shims().molasses)
        # self.abs(-6.00 * ms, self.qp0)  # Quadrupole coils off
        # molasses time
        self.abs(-3 * ms, laser.TrapShutter().close_all_full)
        self.abs(-2.50 * ms, laser.RepumpAOM.off)
        # optical pumping
        self.abs(-2.50 * ms, mag.Shims().op)
        self.abs(-2.50 * ms, laser.Detuning().mot)
        self.abs(-2 * ms, laser.RepumpShutter().close)
        self.abs(0 * ms, OpticalPumping().on)
        self.abs(1 * ms, OpticalPumping().off)
        self.abs(1 * ms, self.qp_on.on)
        self.abs(50 * ms, mag.Shims().mot)
        self.abs(50 * ms, laser.RepumpCurrent().mot)


class Recap(Sequence):
    def __init__(self):
        super().__init__()
        self.detune = laser.Detuning()
        self.qp_cap = QPCaptureF1()
        self.reset = rst.Reset()
        self.trap_shutter = laser.TrapShutter()
        self.repump_shutter = laser.RepumpShutter()
        self.repump_aom = laser.RepumpAOM()
        self.cart_supply = mag.CartSupply()
        self.qp6 = partial(mag.cart_digital_setpoint, i=6)
        self.dig_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.dig_off = partial(out.digital_out, connector=3, channel=7, state=0)

    @Sequence._update_time
    def mot_recap(self, seq_time):
        self.abs(0.00, self.qp6)
        self.abs(0.63*ms, self.trap_shutter.open_all)
        self.abs(0.63*ms, self.repump_shutter.open)
        self.abs(0.63*ms, self.repump_aom.on)
        self.abs(5*ms, self.cart_supply.mot)

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(25*ms, self.detune.cmot)
        self.abs(100*ms, self.dig_on)
        self.abs(100*ms, self.qp_cap.seq)
        self.abs(200*ms, self.mot_recap)
        self.abs(200*ms, self.dig_off)
        self.abs(8, self.reset.general)
