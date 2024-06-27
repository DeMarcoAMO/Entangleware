from Base.timing import Sequence
from Base.constants import *
import Base.dipole as dip
import Base.magnetics as mag


class CrossRelease(Sequence):
    def __init__(self, i_ag=0):
        """ Releases atoms from crossed optical dipole trap, and turns imaging coil on high for imaging.

        :param i_ag: anti-gravity coil current for long TOF images
        :type i_ag: float
        """
        super().__init__()
        self.dipole = dip.DipoleBeam()
        self.pinch = mag.PinchBiasSet(ip0=0, ib0=0)
        self.image_coil = mag.ImagingCoil()
        # for use when turning the AG coil on to support against gravity
        self.ag = mag.AGCoil(i0=0, i1=i_ag, total_time=0.2 * ms)

    # assumes pinch is on during final evap and imaging coil is off to start
    @Sequence._update_time
    def weak(self, seq_time):
        """
        Default cross release method. Does not use anti-gravity coil, turns imaging coil on right after release.
        :param seq_time: start time of method
        :type seq_time: float
        :rtype: float
        :return: 0 elapsed time
        """
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
