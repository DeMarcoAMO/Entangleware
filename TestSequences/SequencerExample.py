import math
import Base.outputwrappers as out
import Base.boards as brd
from Entangleware import ew_link as ew
from functools import partial
from Base.constants import *
from Base.timing import Sequence


# create a class to handle continuous analog ramps
# "flip the axes" of the output. Figure out when each bit flip should occur for the DAC, and call for each bit flip
# at the appropriate time. Minimizes number of analog transitions and accurately reflects how the hardware works.
class AnalogRamp:
    # ramp from voltage v_start to v_end over time ramp_time
    # if exponential use time constant tau
    def __init__(self, v_start, v_end, ramp_time, tau=0):
        # initialize parent Sequence class
        super().__init__()
        # make tau and ramp_time class parameters
        self.tau = tau
        self.ramp_time = ramp_time
        # output to channel 3 on board 1:
        self.board = 1
        self.channel = 3
        # convert the start and end values into their corresponding DAC bits (16 bit DAC spanning 20V)
        self.q_val_start = int((v_start / 20) * (2 ** 16))
        self.q_val_end = int((v_end / 20) * (2 ** 16))
        # generate a list of output steps corresponding to the DAC bits between q start and q end
        if self.q_val_start > self.q_val_end + 1:
            self.output_steps = list(range(self.q_val_end + 1, self.q_val_start))
        else:
            self.output_steps = list(range(self.q_val_start, self.q_val_end + 1))
        self.length = len(self.output_steps)
        # generate blank lists for the actual analog steps and their corresponding times
        self.time_steps = [None] * self.length
        self.analog_steps = [None] * self.length

    # iterates through the list of analog steps outputting each one at the appropriate time
    def _output(self):
        for index in range(self.length):
            time = self.time_steps[index]
            value = self.analog_steps[index]
            out.analog_out(time, self.board, self.channel, value)

    # populates output lists for a linear ramp then calls output method
    def linear(self, t_start):
        # slope of linear ramp
        slope = (self.q_val_end - self.q_val_start) / self.ramp_time
        # calculate the times and convert the outputs back into voltages
        for index in range(self.length):
            self.time_steps[index] = t_start + (self.output_steps[index] - self.q_val_start) / slope
            self.analog_steps[index] = 20 * self.output_steps[index] / (2 ** 16)
        if self.q_val_start > self.q_val_end + 1:
            self.time_steps.reverse()
            self.analog_steps.reverse()
        self._output()
        return self.ramp_time

    # populates output lists for exponentialy increasing ramp then calls output method
    def exponential(self, t_start):
        # find the range of the exponential decay and scale
        delta = math.exp(self.ramp_time / self.tau)
        if delta == 1:
            raise ValueError('decay_rate or the time interval is too small')
        alpha = (self.q_val_start - self.q_val_end) / (1 - delta)
        offset = self.q_val_start - alpha
        for index in range(self.length):
            self.time_steps[index] = t_start + math.log((self.output_steps[index] - offset) / alpha) * self.tau
            self.analog_steps[index] = 20 * self.output_steps[index] / (2 ** 16)
        if self.q_val_start > self.q_val_end + 1:
            self.time_steps.reverse()
            self.analog_steps.reverse()
        self._output()
        return self.ramp_time

    # populates output lists for exponentially decreasing ramp then calls output
    def exponential_down(self, t_start):
        delta = math.exp(self.ramp_time / self.tau)
        if delta == 1:
            raise ValueError('decay_rate or the time interval is too small')
        alpha = (delta-1)/(self.q_val_start - self.q_val_end)
        for index in range(self.length):
            self.time_steps[index] = t_start + self.ramp_time - \
                                     self.tau*math.log(1 + (self.output_steps[index]-self.q_val_end)*alpha)
            self.analog_steps[index] = 20 * self.output_steps[index] / (2 ** 16)
        if self.q_val_start > self.q_val_end + 1:
            self.time_steps.reverse()
            self.analog_steps.reverse()
        self._output()
        return self.ramp_time


# create a sequence class to handle programatic generation of digital transitions
class DigitalTransitions(Sequence):
    def __init__(self):
        # initialize parent Sequence class
        super().__init__()
        # output on digital lines 16, 18 and 20 on VHDCI connector 2 of the FPGA
        connector = 2
        channel1 = 18
        channel2 = 16
        channel3 = 20
        # use partial method to fill the connector, channel, and state parameters of out.digital_out
        # creates functions on(time) and off(time) that accept one time parameter
        self.on1 = partial(out.digital_out, connector=connector, channel=channel1, state=1)
        self.off1 = partial(out.digital_out, connector=connector, channel=channel1, state=0)
        self.on2 = partial(out.digital_out, connector=connector, channel=channel2, state=1)
        self.off2 = partial(out.digital_out, connector=connector, channel=channel2, state=0)
        self.on3 = partial(out.digital_out, connector=connector, channel=channel3, state=1)
        self.off3 = partial(out.digital_out, connector=connector, channel=channel3, state=0)

    # method to repeatedly pulse channel 1 starting at t=start_time
    @Sequence._update_time
    def pulse1(self, start_time):
        # pulse on and off in 1ms intervals 25 times
        pulse_time = 1*ms
        n_pulses = 25

        # pulse line on at t = 0 (start_time
        self.abs(0.00, self.on1)
        # pulse line off and on
        for n in range(n_pulses-1):
            self.rel(pulse_time, self.off1)
            self.rel(pulse_time, self.on1)
        self.rel(pulse_time, self.off1)

    @Sequence._update_time
    def pulse2(self, start_time):
        # generate a list of pulse start times and lengths
        time_list = [1, 5, 7, 9, 12, 17, 20]
        pulse_length_list = [2, 1, 1, 2, 1, 2, 3]
        if len(time_list) != len(pulse_length_list):
            raise ValueError('Lists are of unequal lengths')

        # iterate through list
        for n in range(len(time_list)):
            self.abs(time_list[n]*ms, self.on2)
            self.rel(pulse_length_list[n]*ms, self.off2)

    @Sequence._update_time
    def pulse3(self, start_time):
        self.abs(0.00, self.on3)
        self.rel(1*ms, self.off3)


class DDSRamp(Sequence):
    def __init__(self, freq_start, freq_stop, ramp_time, n_steps):
        super().__init__()
        self.f_start = freq_start
        self.f_stop = freq_stop
        self.ramp_time = ramp_time
        self.n_steps = n_steps
        # initialize a AD9959 DDS board
        self.dds = brd.AD9959(connector=1, io_pin=1, serial_clock_pin=3, reset_pin=5, io_update_pin=7,
                              ref_clock=500e6, ref_clk_multiplier=0)
        # output f_start at -10dBm on channel 0 of dds
        # self.dds_pulse = partial(dds.arbitrary_output, channel_mask=0, freq_list=[freq_start], power_list=[-10 * dBm],
        #                          tt=1 * ms, n_steps=1)

    @Sequence._update_time
    def linear(self, start_time):
        # calculate FTWs for linear sweep from f_start to f_stop in t=ramp_time using n steps
        t_step = self.ramp_time/self.n_steps
        slope = (self.f_start - self.f_stop)/self.ramp_time
        freq_list = [self.f_start + slope*t_step*n for n in range(self.n_steps)]
        power_list = [-10*dBm for n in range(self.n_steps)]
        dds_sweep = partial(self.dds.arbitrary_output, channel_mask=0, freq_list=freq_list, power_list=power_list, tt=self.ramp_time)

        self.abs(0.00, dds_sweep)


class ExampleSequence(Sequence):
    def __init__(self):
        super().__init__()

        # initialize 2 analog ramp classes, one for a linear up ramp and the other exponential down
        self.ramp_up = AnalogRamp(v_start=0, v_end=5, ramp_time=5*ms)
        self.ramp_down = AnalogRamp(v_start=5, v_end=1, ramp_time=15*ms, tau=3*ms)
        self.analog_off = partial(out.analog_out, connector=1, channel=3, value=0)

        # initialize digital line class
        self.digital = DigitalTransitions()

        # initialize DDS ramp class
        self.dds = DDSRamp(freq_start=10*kHz, freq_stop=100*kHz, ramp_time=100*ms, n_steps=10)

    @Sequence._update_time
    def seq(self, start_time):
        self.abs(0.00, self.ramp_up.linear)
        self.rel(10*ms, self.ramp_down.exponential_down)
        self.rel(10*ms, self.analog_off)

        self.abs(0.00, self.digital.pulse3)
        self.rel(0.00, self.digital.pulse1)
        self.rel(0.00, self.digital.pulse3)
        self.abs(5*ms, self.digital.pulse2)

        self.abs(20*ms, self.dds.linear)


# run the example sequence

# connect to ECA
ew.connect(1.0)

# states here are 'default' values
# set default of the analog and digital lines used to 0
out.digital_out(0.00, 2, 16, 0)
out.digital_out(0.00, 2, 18, 0)
out.digital_out(0.00, 2, 20, 0)
out.analog_out(0.00, 1, 3, 0)

# initialize bitstream to send to hardware
# everything between build_sequence and run_sequence is deterministically timed
ew.build_sequence()

example = ExampleSequence()
example.seq(0.00)
# send bitstream to ECA
ew.run_sequence()

# disconnect from ECA
ew.disconnect()
