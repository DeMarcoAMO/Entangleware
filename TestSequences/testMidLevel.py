from Base.timing import Sequence
from Base.constants import *
from functools import partial
import MidLevelSeq.MagneticTraps as MagTrap
import Base.imaging as img
import Base.MatlabCommunication as Comm
import Base.outputwrappers as out


class TestSciCellLoad(Sequence):
    def __init__(self, save_images=False):
        super().__init__()
        self.tof = 2 * ms
        Comm.seq_info["tof"] = self.tof
        self.load = MagTrap.SciCellLoad()
        self.release = MagTrap.CartRelease()
        self.image = img.ImageRepeat(repump_time=100*us, detune_repump=False)
        Comm.seq_info["commands"] = ["runfit(PixisRb,'gauss', 'fix', {{'offset', 'slopex', 'slopey'}},"
                                     "'guess',[0.1 800 900 100 225 200 0.001 0.001],"
                                     "'ROI', [200 300; 1000 950], 'AutoROI', [540,770])",
                                     "writetoOrigin(PixisRb,{'curTime', 'repump_time', "
                                     "'detune_repump', 'tof','Ntot','result'})", "showres(PixisRb)"]
        if save_images:
            Comm.seq_info["commands"].append("writetofile(PixisRb,{'tof','repump_time'},'saveRAW',1)")

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.load.seq)
        self.rel(20*ms, self.release.sci_cell)
        self.rel(self.tof, self.image.norm)
        self.rel(4.6, out.move_cart_prun)
        Comm.write()


class TestCartEvap(Sequence):
    def __init__(self, f_start=70, f_stop=40, rate=1.25, save_images=False):
        super().__init__()
        self.tof = 1*ms
        self.evap = MagTrap.CartEvap(start=f_start * MHz, stop=f_stop * MHz, rate=rate * MHz / sec)
        self.release = MagTrap.CartRelease()
        self.image = img.ImageRepeat(repump_time=100*us, detune_repump=False)
        self.dig_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.dig_off = partial(out.digital_out, connector=3, channel=7, state=0)
        Comm.seq_info["tof"] = self.tof
        Comm.seq_info["commands"] = ["runfit(PixisRb, 1, 'gauss', 'fix', {{'offset', 'slopex', 'slopey'}}, "
                                     "'ROI', [200 500; 1000 950], 'AutoROI', [680,710])",
                                     "writetoOrigin(PixisRb,{'repump_time', 'detune_repump', 'tof',"
                                     "'Ntot','result'})",
                                     "showres(PixisRb)"]
        if save_images:
            Comm.seq_info["commands"].append("writetofile(PixisRb,{'tof','repump_time'},'saveRAW',1)")

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.evap.tight)
        self.rel(10*ms, self.release.evap)
        self.rel(self.tof, self.image.norm)
        self.rel(2.6, out.move_cart_prun)
        self.rel(2.6, self.dig_off)
        Comm.write()


class TestPinchTransfer(Sequence):
    def __init__(self, save_images=False):
        super().__init__()
        self.tof = -1 * ms
        self.evap = MagTrap.CartEvap()
        self.transfer = MagTrap.PinchTransfer()
        self.release = MagTrap.PinchRelease()
        self.image = img.ImageRepeat(repump_time=300*us, detune_repump=False)
        Comm.seq_info["tof"] = self.tof
        Comm.seq_info["commands"] = ["runfit(PixisRb,'gauss', 'fix', {'offset'}, "
                                     "'ROI', [1 250; 1020 900], 'AutoROI', [500,500])",
                                     "writetoOrigin(PixisRb,{'repump_time', 'detune_repump', 'tof','Ntot','result'})",
                                     "showres(PixisRb)"]
        if save_images:
            Comm.seq_info["commands"].append("writetofile(PixisRb,{'tof','repump_time'},'saveRAW',1)")

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.evap.tight)
        self.rel(100*ms, self.transfer.seq)
        self.rel(200*ms, out.move_cart_prun)
        self.rel(500*ms, self.release.seq)
        self.rel(self.tof, self.image.norm)
        Comm.write()


class TestPinchLoad(Sequence):
    def __init__(self, ag_down=True, save_images=False):
        super().__init__()
        self.tof = 1.0 * ms
        self.load = MagTrap.PinchLoad(ag_down)
        self.release = MagTrap.PinchRelease()
        self.image = img.ImageRepeat(repump_time=15*us, detune_repump=False)
        Comm.seq_info["iAG"] = 5
        Comm.seq_info["tof"] = self.tof/ms
        Comm.seq_info["commands"] = ["runfit(PixisRb,'gauss', 'fix', {{'offset', 'slopex', 'slopey'}}, "
                                     "'ROI', [100 350; 950 950])",
                                     "writetoOrigin(PixisRb,{'curTime', 'iAG', 'repump_time', 'detune_repump', "
                                     "'tof','Ntot','result'})", "showres(PixisRb)"]
        if save_images:
            Comm.seq_info["commands"].append("writetofile(PixisRb,{'tof','repump_time'},'saveRAW',1)")

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.load.tight)
        self.rel(200*ms, self.release.seq)
        self.rel(self.tof, self.image.norm)
        Comm.write()


class TestPinchEvap(Sequence):
    def __init__(self, f_stop=8, save_images=False):
        super().__init__()
        self.tof = 15*ms
        self.hold_time = 0.1*ms
        self.evap = MagTrap.PinchEvap(start1=50 * MHz, stop1=f_stop * MHz, rate1=1.75 * MHz / sec)
        self.release = MagTrap.PinchRelease()
        self.image = img.ImageRepeat(repump_time=300*us, detune_repump=False)

        Comm.seq_info["hold_time"] = self.hold_time
        Comm.seq_info["tof"] = self.tof
        Comm.seq_info["commands"] = ["runfit(PixisRb, 1, 'gauss', 'fix', {'offset'},"
                                     "'ROI', [50  500; 500 850], 'AutoROI', [850,600])",
                                     "writetoOrigin(PixisRb,{'curTime', 'hold_time','repump_time', 'detune_repump', "
                                     "'tof','Ntot','result'})", "showres(PixisRb)"]
        if save_images:
            Comm.seq_info["commands"].append("writetofile(PixisRb,{'tof','repump_time'},'saveRAW',1)")

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0.00, self.evap.tight)
        self.rel(self.hold_time, self.release.seq)
        self.rel(self.tof, self.image.norm)
        Comm.write()
