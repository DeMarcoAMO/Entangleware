from Base.timing import Sequence
from Base.constants import *
import Base.dipole as dip
import Base.magnetics as mag
import MidLevelSeq.DipoleTrap as Trap


class CrossRelease(Sequence):
    def __init__(self, i_ag=0):
        super().__init__()
        self.dipole = dip.DipoleBeam()
        self.pinch = mag.PinchBiasSet(ip0=0, ib0=0)
        self.image_coil = mag.ImagingCoil()
        # for use when turning the AG coil on to support against gravity
        self.ag = mag.AGCoil(i0=0, i1=i_ag, total_time=0.2 * ms)

    # assumes pinch is on during final evap and imaging coil is off to start
    @Sequence._update_time
    def weak(self, seq_time):
        self.abs(0.00, self.ag.off)
        self.abs(0.00, self.dipole.off)
        if mag.pinch_on or mag.bias_on:
            self.abs(0.00, self.pinch.off)
        else:
            self.abs(0.00, self.pinch.clean_up)
        if mag.img_on:
            self.abs(0.10*ms, self.image_coil.high)
        else:
            self.abs(0.10*ms, self.image_coil.on)
        self.abs(55.12*ms, self.image_coil.off)
        self.abs(0.00)
