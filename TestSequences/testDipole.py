from Base.timing import Sequence
from Base.constants import *
from functools import partial
import Base.outputwrappers as out
import Base.MatlabCommunication as Comm
import Base.imaging as img

import MidLevelSeq.DipoleTrap as Trap
import MidLevelSeq.DipoleRelease as Release


class CrossEvaporation(Sequence):
    def __init__(self, parameters, i=0, save_images=False):
        super().__init__()
        self.tof = 17 * ms

        self.evap = Trap.CrossEvap(parameters)
        self.release = Release.CrossRelease()
        self.image = img.ImageRepeat(repump_time=300 * us, detune_repump=False)

        self.hold_time = 500*ms
        self.test_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.test_off = partial(out.digital_out, connector=3, channel=7, state=0)

        Comm.seq_info["tof"] = self.tof
        Comm.seq_info["dipole_low"] = parameters["low"]
        Comm.seq_info["dipole_high"] = parameters["high"]
        Comm.seq_info["hold_time"] = self.hold_time
        Comm.seq_info["commands"] = ["runfit(PixisRb, 1, 'gauss','fix', {'offset'}, "
                                     "'ROI', [50 350; 850 800], 'AutoROI', [300,300])",
                                     "writetoOrigin(PixisRb,{'hold_time', 'repump_time', 'detune_repump', "
                                     "'dipole_low','dipole_high' ,'tof',""'Ntot', 'result'})",
                                     "showres(PixisRb)"]
        if save_images:
            Comm.seq_info["commands"].append("writetofile(PixisRb,{'tof','repump_time','probe_power'},'saveRAW',1)")

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.evap.seq)
        self.rel(self.hold_time, self.test_on)
        self.rel(0.03*ms, [self.test_off, self.release.weak])
        self.rel(self.tof, self.image.norm)
        Comm.write()
