from Base.timing import Sequence
from Base.constants import *
from functools import partial
import Base.outputwrappers as out
import Base.masterrepump as laser
import Base.inireset as rst
import Base.magnetics as mag
import Base.channels as ch
import Base.MatlabCommunication as Comm


class ImageRepeat(Sequence):
    def __init__(self, repump_time, detune_repump):
        """ Takes 3 images (shadow, light, dark) and sets up the apparatus for the next shot.

        :param repump_time: length of time the repump beam is on for at the science cell
        :type repump_time: float
        :param detune_repump: repump on resonance if false, detuned if true
        :type detune_repump: bool
        :rtype: float
        :return: elapsed time
        """
        super().__init__()
        self.repump_time = repump_time
        self.detune = detune_repump
        self.ag = mag.AGCoil()
        self.img_coil = mag.ImagingCoil()
        self.rpt = rst.Repeat()
        self.test_off = partial(out.digital_out, connector=2, channel=16, state=0)

    # norm is the equivalent of full frame in the old sequencer code, the default function we use. Uses default
    # probe time 0.044ms
    @Sequence._update_time
    def norm(self, seq_time):
        Comm.seq_info["rawmode"] = 'normal'
        img = DoImage(self.repump_time, self.detune)
        self.abs(-1.5*ms, self.ag.off)
        self.abs(5*ms, self.img_coil.off)
        # self.abs(5*ms, self.test_off)
        self.abs(0.00, img.seq)
        self.rel(0.00, self.rpt.seq)
        self.rel(200*ms, out.arduino_low)

    @Sequence._update_time
    def fluorescence(self, seq_time):
        """ Does fluorescence imaging and sets up the apparatus to repeat

        :param seq_time: execution time (s)
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        Comm.seq_info["rawmode"] = 'normal'
        img = DoImage(self.repump_time, self.detune)
        self.abs(-1.5 * ms, self.ag.off)
        self.abs(5 * ms, self.img_coil.off)
        self.abs(0.00, img.fluorescence)
        self.rel(0.00, self.rpt.seq)
        self.rel(200 * ms, out.arduino_low)


# default value of probe_time is 0.044ms (equivalent to DoImage in old sequencer). Overwriting
# probe_time is equivalent to DoImageExt
class DoImage(Sequence):
    def __init__(self, repump_time, detune_repump, probe_time=0.044*ms):
        super().__init__()
        self.probe_time = probe_time
        self.repump_time = repump_time
        self.detune = detune_repump
        self.tuning = Repump()
        self.image = ImageF1(self.probe_time, self.repump_time)
        Comm.seq_info["repump_time"] = repump_time/us
        Comm.seq_info["detune_repump"] = detune_repump
        # self.test_on = partial(out.digital_out, connector=2, channel=16, state=1)
        # self.test_off = partial(out.digital_out, connector=2, channel=16, state=0)

    @Sequence._update_time
    def seq(self, seq_time):
        self.abs(0, self.no_cart)
        self.rel(1, out.move_cart_prun)

    @Sequence._update_time
    def no_cart(self, seq_time):
        self.abs(-100 * ms, laser.OPAOM.off)
        self.abs(-100 * ms, laser.ProbeAOM.off)
        self.abs(-7.5 * ms, laser.ProbeShutter.open)
        self.abs(-7.5 * ms, laser.RepumpShutter.open)
        if self.detune:
            self.abs(0.00, self.tuning.detune)
        else:
            self.abs(0.00, self.tuning.on_res)
        self.abs(0.00, self.image.pulse)
        self.abs(0.750, self.image.pulse)
        self.abs(1.5, self.image.background)
        self.abs(1.55, laser.ProbeShutter.close)
        self.abs(1.55, laser.OPAOM.on)

    @Sequence._update_time
    def fluorescence(self, seq_time):
        """ Doesn't open probe shutter. Use different beam (e.g., lattice) for fluorescence imaging

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        self.abs(-100 * ms, laser.OPAOM.off)
        self.abs(-100 * ms, laser.ProbeAOM.off)
        self.abs(-7.5 * ms, laser.RepumpShutter.open)
        self.abs(0.00, self.tuning.on_res)
        self.abs(0.00, self.image.pulse)
        self.abs(0.750, self.image.pulse)
        self.abs(1.5, self.image.background)
        self.abs(1.55, laser.OPAOM.on)

        self.rel(1, out.move_cart_prun)


# change Repump tuning for imaging and back
class Repump(Sequence):
    def __init__(self):
        super().__init__()
        self.repump_tuning = laser.RepumpTuning()

    @Sequence._update_time
    def on_res(self, seq_time):
        self.abs(-100*ms, self.repump_tuning.on_res)
        self.abs(1550*ms, self.repump_tuning.normal)

    @Sequence._update_time
    def detune(self, seq_time):
        self.abs(-100*ms, self.repump_tuning.imaging)
        self.abs(1550*ms, self.repump_tuning.normal)


class ImageF1(Sequence):
    def __init__(self, probe_time, repump_time):
        super().__init__()
        self.probe_time = probe_time
        self.repump_time = repump_time
        self.test_on = partial(out.digital_out, connector=3, channel=7, state=1)
        self.test_off = partial(out.digital_out, connector=3, channel=7, state=0)

    @Sequence._update_time
    def pulse(self, seq_time):
        # self.abs(-3*ms, self.test_on)
        # self.abs(0.00, self.test_off)
        # NEK was playing with the timing 09/06/2022. Should be -3ms for trigger camera
        self.abs(-3.00*ms, out.trigger_camera)
        # self.abs(-0.5 * ms, out.trigger_camera)
        if self.repump_time > 0:
            self.abs(-0.010*ms - self.repump_time, laser.RepumpAOM.on)
            self.abs(-0.010*ms, laser.RepumpAOM.off)
        self.abs(0.00, out.trigger_camera_side)
        self.abs(0.00, laser.ProbeAOM.on)
        self.abs(self.probe_time, laser.ProbeAOM.off)
        self.abs(self.probe_time)

    @Sequence._update_time
    def background(self, seq_time):
        self.abs(-3.00 * ms, out.trigger_camera)
        if self.repump_time > 0:
            self.abs(-0.010*ms - self.repump_time, laser.RepumpAOM.on)
            self.abs(-0.010*ms, laser.RepumpAOM.off)
        self.abs(0.00, out.trigger_camera_side)
        self.abs(0.00)

    @Sequence._update_time
    def side(self, seq_time):
        self.abs(0.00, out.trigger_camera_side)
        self.abs(self.probe_time)
