from functools import partial
from Base.timing import Sequence
from Base.constants import *
import Base.dipole as dip
import Base.magnetics as mag
import MidLevelSeq.MagneticTraps as MagTrap
import Base.outputwrappers as out

img_quant_current = 0.5


class CrossEvap(Sequence):
    def __init__(self, evap_parameters):
        '''
        Loads atoms into the optical dipole trap and evaporates by lowering trap depth, after PinchEvap.
        :param evap_parameters: dictionary containing parameters for evaporation trajectory
        :type evap_parameters: dict
        '''
        super().__init__()

        self.pinch_evap = MagTrap.PinchEvap()
        self.dipole = dip.DipoleBeam(depth_high=evap_parameters["high"], depth_low=evap_parameters["low"],
                                     depth_final=evap_parameters["final"], ramp_time=evap_parameters["down_time"],
                                     compress_time=evap_parameters["compress_time"], up_time=evap_parameters["up_time"],
                                     tau=evap_parameters["tau"])
        self.pinch_down1 = mag.PinchBiasSet(ip0=585, ip1=evap_parameters["pinch_low"],
                                            total_time=evap_parameters["pinch_low_time"])
        self.pinch_off = mag.PinchBiasSet(ip0=evap_parameters["pinch_low"], ip1=0,
                                          total_time=evap_parameters["pinch_off_time"])
        self.img = mag.ImagingCoil(i0=0, i1=img_quant_current, tt=10*ms)
        self.ag_off = mag.AGCoil(i0=0.5, i1=0, total_time=evap_parameters["pinch_off_time"])

        self.test_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.test_off = partial(out.digital_out, connector=3, channel=7, state=0)

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.pinch_evap.tight)
        self.rel(0.00, [self.dipole.on, self.dipole.ramp_up])
        self.rel(0.00, self.pinch_down1.ramp)
        self.rel(0.00, self.img.ramp)

        self.start_local_timing()
        self.abs(0.00, self.pinch_off.ramp)
        self.abs(0.00, self.ag_off.ramp)
        self.rel(0.00, self.pinch_off.clean_up)
        self.abs(100*ms, self.dipole.exp_ramp)
        self.end_local_timing()

        self.rel(200*ms, self.dipole.recompress)
        self.rel(100*ms)
