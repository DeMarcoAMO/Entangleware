import math
import Base.channels as ch
from Entangleware import ew_link as ew
from Base.constants import *
import matplotlib.pyplot as plt

digital_time_step = 1 * us
analog_time_step = 2 * us


def digital_out(seq_time, connector, channel, state):
    """
    :param seq_time: time at which digital transition occurs
    :type seq_time: float
    :param connector: FPGA connector
    :type connector: int
    :raise: ValueError if FPGA connector isn't 0-3
    :param channel: channel number on FPGA connector
    :type channel: int
    :raise: ValueError if channel isn't 0-31
    :param state: digital state
    :type state: int
    :raise: ValueError if state isn't 0 or 1
    :rtype: float
    :return: 1 us elapsed time
    """
    if connector < 0 or connector > 3:
        raise ValueError('Invalid connector number')
    if channel < 0 or channel > 31:
        raise ValueError('Invalid channel number')
    if state != 0 and state != 1:
        raise ValueError('Invalid digital state')
    ew.set_digital_state(seq_time, connector, 1 << channel, 1 << channel, state << channel)
    return digital_time_step


def analog_out(seq_time, connector, channel, value):
    """
    :param seq_time: time at which analog transition occurs
    :type seq_time: float
    :param connector: analog board to use
    :type connector: int
    :raise: ValueError if board isn't 0 or 1
    :param channel: output channel on analog board
    :type channel: int
    :raise: ValueError if channel isn't between 0 and 7
    :param value: output voltage
    :type value: float
    :raise: ValueError if value isn't between -10 and 10
    :rtype: float
    :return: 2 us elapsed time
    """
    if not (0 <= connector <= 1):
        raise ValueError('Invalid connector number')
    if not (0 <= channel <= 7):
        raise ValueError('Invalid channel number')
    if not (-10 <= value <= 10):
        raise ValueError('Output voltage not between -10 and 10V')
    ew.set_analog_state(seq_time, connector, channel, -value)
    return analog_time_step


def move_cart(seq_time):
    """ Digital trigger sent to cart controller to initiate motion
    :param seq_time: time to trigger cart motion
    :return: elapsed time
    """
    digital_out(seq_time - 40 * ms, ch.cart["connector"], ch.cart["pin"], 1)
    digital_out(seq_time - 30 * ms, ch.cart["connector"], ch.cart["pin"], 0)
    return 2 * digital_time_step - 30 * ms


def move_cart_prun(seq_time):
    """ Digital trigger sent to cart controller to initiate motion, updated timing
    :param seq_time: time to trigger cart motion
    :return: elapsed time
    """
    digital_out(seq_time - 30 * ms, ch.cart["connector"], ch.cart["pin"], 1)
    digital_out(seq_time - 20 * ms, ch.cart["connector"], ch.cart["pin"], 0)
    return 2 * digital_time_step - 20 * ms


def trigger_camera(seq_time):
    """ Digital trigger sent to camera to trigger image capture
    :param seq_time: time to trigger camera
    :return: elapsed time
    """
    digital_out(seq_time - 3.31*ms, ch.camera_sync["connector"], ch.camera_sync["pin"], 0)
    t = digital_out(seq_time - 3.2 * ms, ch.camera_sync["connector"], ch.camera_sync["pin"], 1)
    return t - 3.2*ms


def trigger_camera_side(seq_time):
    """ Digital trigger sent to second camera to trigger image capture
    :param seq_time: time to trigger camera
    :return: elapsed time
    """
    t_delay = 500*us
    digital_out(seq_time - 60.7*us-t_delay, ch.thorcam_trigger["connector"], ch.thorcam_trigger["pin"], 1)
    t = digital_out(seq_time + 39.3*us-t_delay, ch.thorcam_trigger["connector"], ch.thorcam_trigger["pin"], 0)
    return t + 39.3*us


def arduino_high(seq_time):
    """ Digital trigger sent to arduino listener to alert imaging computer to watch for income data from camera
    :param seq_time: time to trigger arduino
    :return: elapsed time
    """
    t = digital_out(seq_time, ch.arduino_trigger["connector"], ch.arduino_trigger["pin"], 1)
    return t


def arduino_low(seq_time):
    """ Sets arduino trigger back to logical low
    :param seq_time: time to change line
    :return: elapsed time
    """
    t = digital_out(seq_time, ch.arduino_trigger["connector"], ch.arduino_trigger["pin"], 0)
    return t


class AnalogRamp:
    def __init__(self, board, channel, val_start, val_end, total_time, a=0, tau=0):
        """Outputs a series of analog values to create ramps with different trajectories.
        For a given ramp trajectory, calculates when each bit flip in the analog register should occur, and calls
        for the next value at the appropriate time. 2^16 bit register spanning -10 to 10V
        :param board: analog source card
        :type board: int
        :raise: ValueError if board not 0 or 1
        :param channel: channel on card
        :type channel: int
        :raise: ValueError if channel not between 0 and 7
        :param val_start: initial voltage of ramp
        :type val_start: float
        :raise: ValueError if val_start not between -10 and 10V
        :param val_end: finial voltage of ramp
        :type val_end: float
        :raise: ValueError if val_end not between -10 and 10V
        :param total_time: duration of ramp in seconds
        :value total_time: float
        :param a: curvature of sigmoidal ramp (default value 0)
        :type a: float
        :param tau: time constant of exponential ramp (default value 0)
        :type tau: float
        """

        if not (0 <= board <= 1):
            raise ValueError('Invalid board number')
        if not (0 <= channel <= 7):
            raise ValueError('Invalid channel number')
        if not (-10 <= val_start <= 10):
            raise ValueError('Starting voltage not between -10 and 10V')
        if not (-10 <= val_end <= 10):
            raise ValueError('Ending voltage not between -10 and 10V')

        self.board = board
        self.channel = channel
        self.total_time = total_time
        self.tau = tau
        self.a = a
        # convert the start and end values into their corresponding DAC bits (16 bit DAC spanning 20V)
        self.q_val_start = int((-val_start / 20) * (2 ** 16))
        self.q_val_end = int((-val_end / 20) * (2 ** 16))
        # generate a list of DAC bits between q start and q end
        if self.q_val_start > self.q_val_end + 1:
            self.output_steps = list(range(self.q_val_end + 1, self.q_val_start))
        else:
            self.output_steps = list(range(self.q_val_start, self.q_val_end + 1))
        self.length = len(self.output_steps)
        # generate blank lists for the actual analog steps and their corresponding times
        self.time_steps = [None] * self.length
        self.analog_steps = [None] * self.length

    def _output(self):
        """ iterates through self.time_steps and self.analog_steps, outputting each voltage in self.analog_steps at
        the corresponding time in self.time_steps
        :return: None
        """
        for index in range(self.length):
            time = self.time_steps[index]
            value = self.analog_steps[index]
            ew.set_analog_state(time, self.board, self.channel, value)

    def linear(self, t_start):
        """Linear ramp between val_start and val_end over time total_time
        :param t_start: start time of ramp
        :type t_start: float
        :rtype: float
        :return:time duration of ramp (total_time)
        """
        # slope of linear ramp
        slope = (self.q_val_end - self.q_val_start) / self.total_time
        # calculate the times and convert the outputs back into voltages
        for index in range(self.length):
            self.time_steps[index] = t_start + (self.output_steps[index] - self.q_val_start) / slope
            self.analog_steps[index] = 20 * self.output_steps[index] / (2 ** 16)
        if self.q_val_start > self.q_val_end + 1:
            self.time_steps.reverse()
            self.analog_steps.reverse()
        self._output()
        return self.total_time

    def exponential(self, t_start):
        """Exponential ramp between val_start and val_end over time total_time with time constant tau
        :param t_start: start time of ramp
        :type t_start: float
        :rtype: float
        :return: time duration of ramp (total_time)
        """
        # find the actual range of the exponential decay and scale things  appropriately
        delta = math.exp(self.total_time / self.tau)
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
        return self.total_time

    def exponential_down(self, t_start):
        """Exponential ramp between val_start and val_end over time total_time with time constant tau.
        Opposite curvature from exponential
        :param t_start: start time of ramp
        :type t_start: float
        :rtype: float
        :return: time duration of ramp (total_time)
        """
        delta = math.exp(self.total_time / self.tau)
        if delta == 1:
            raise ValueError('decay_rate or the time interval is too small')
        alpha = (delta-1)/(self.q_val_start - self.q_val_end)
        for index in range(self.length):
            self.time_steps[index] = t_start + self.total_time - \
                                     self.tau*math.log(1 + (self.output_steps[index]-self.q_val_end)*alpha)
            self.analog_steps[index] = 20 * self.output_steps[index] / (2 ** 16)
        if self.q_val_start > self.q_val_end + 1:
            self.time_steps.reverse()
            self.analog_steps.reverse()
        self._output()
        return self.total_time

    def sigmoidal(self, t_start):
        """Sigmoidal ramp from val_start to val_end with curvature a.
        :param t_start: start time of ramp
        :type t_start: float
        :rtype: float
        :return: time duration of ramp (total_time)
        """
        stretch = 2 / (1 - math.exp(self.a / 2))
        for index in range(self.length):
            temp1 = ((self.output_steps[index] - self.q_val_start) / (self.q_val_end - self.q_val_start) - stretch / 2)
            temp2 = (1 - stretch) / temp1 - 1
            self.time_steps[index] = t_start + self.total_time * (-math.log(temp2) / self.a + 1 / 2)
            self.analog_steps[index] = 20 * self.output_steps[index] / (2 ** 16)
        if self.q_val_start > self.q_val_end + 1:
            self.time_steps.reverse()
            self.analog_steps.reverse()
        self._output()
        return self.total_time


class AnalogOscillate:
    def __init__(self, board, channel, amplitude, offset, frequency, total_time):
        """Outputs a series of analog values on given board and channel to create oscillations centered around offset
        with a given amplitude and frequency, lasting for time total_time
        For a given oscillation, calculates when each bit flip in the analog register should occur, and calls
        for the next value at the appropriate time. 2^16 bit register spanning -10 to 10V
        :param board: analog source card
        :type board: int
        :raise: ValueError if board isn't 0 or 1
        :param channel: output channel
        :type channel: int
        :raise: ValueError if channel isn't between 0 and 7
        :param amplitude: amplitude of oscillation in volts
        :type amplitude: float
        :param offset: offset voltage of oscillation
        :type offset: float
        :raise: ValueError if offset isn't between -10 and 10V
        :raise: ValueError if offset + amplitude is outside voltage range
        :param frequency: frequency of oscillation in hertz
        :type frequency: float
        :param total_time: duration of oscillation in seconds
        :type total_time: float
        """

        if not (0 <= board <= 1):
            raise ValueError('Invalid board number')
        if not (0 <= channel <= 7):
            raise ValueError('Invalid channel number')
        if not (-10 <= offset <= 10):
            raise ValueError('Offset not between -10 and 10V')
        if not (-10 <= offset+amplitude <= 10) or not (-10 <= offset-amplitude <= 10):
            raise ValueError('amplitude + offset outside voltage range')

        self.board = board
        self.channel = channel
        self.total_time = total_time
        self.frequency = frequency
        self.offset = offset
        self.amplitude = amplitude
        # convert the start and end values into their corresponding DAC bits (16 bit DAC spanning 20V)
        self.q_low = int((-amplitude / 20) * (2 ** 16))
        self.q_high = int((amplitude / 20) * (2 ** 16))
        # generate a list of output steps corresponding to the DAC bits between q start and q end
        self.output_steps = list(range(0, self.q_high)) + list(range(self.q_high, self.q_low, -1)) + \
                            list(range(self.q_low, 0 + 1))
        self.length = len(self.output_steps)
        # generate blank lists for the actual analog steps and their corresponding times
        self.time_steps = [None] * self.length
        self.analog_steps = [None] * self.length

    def _output(self):

        """ iterates through self.time_steps and self.analog_steps, outputting each voltage in self.analog_steps at
        the corresponding time in self.time_steps
        :return: None
        """
        for index in range(len(self.time_steps)):
            time = self.time_steps[index]
            value = self.analog_steps[index]
            ew.set_analog_state(time, self.board, self.channel, value)

    def sine(self, t_start):
        """Outputs sine wave starting at v=offset at t=t_start
        :param t_start: start time of oscillation
        :type t_start: float
        :rtype: float
        :return: duration of oscillation in seconds (total_time)
        """
        period = 1 / self.frequency
        # calculate the number of full oscillations that will occur during total_time
        n_full = math.trunc(self.total_time / period)

        # iterate through the full oscillations
        for n in range(n_full):
            # arcsin domain runs -1 to 1 (q_low to q_high)
            # handle (0,1) (1,-1) and (-1,0) separately
            output_step1 = list(range(0, self.q_high))
            output_step2 = list(range(self.q_high, self.q_low, -1))
            output_step3 = list(range(self.q_low, 0 + 1))

            time_step1 = [None] * len(output_step1)
            time_step2 = [None] * len(output_step2)
            time_step3 = [None] * len(output_step3)
            # calculate transition times
            for index in range(len(output_step1)):
                time_step1[index] = (math.asin(output_step1[index]/self.q_high)/(2*math.pi*self.frequency))
            for index in range(len(output_step2)):
                time_step2[index] = (math.pi/(2*math.pi*self.frequency) -
                                     math.asin(output_step2[index]/self.q_high)/(2*math.pi*self.frequency))
            for index in range(len(output_step3)):
                time_step3[index] = (2*math.pi/(2*math.pi*self.frequency) +
                                     math.asin(output_step3[index]/self.q_high)/(2*math.pi*self.frequency))
            self.output_steps = output_step1 + output_step2 + output_step3
            self.time_steps = time_step1 + time_step2 + time_step3
            self.time_steps = [t + t_start + n * period for t in self.time_steps]
            self.analog_steps = [-out * 20/(2**16) - self.offset for out in self.output_steps]
            self._output()
            # plot for testing
            # plt.plot(self.time_steps, self.analog_steps)
            # plt.show()

        # now deal with whatever partial sine wave is left over in total_time
        out_final = self.amplitude * math.sin(2*math.pi*self.frequency*self.total_time)
        q_final = int((out_final / 20) * (2 ** 16))
        t_frac = self.total_time - n_full*period
        # check where the end falls using the same domains as above
        if t_frac < period/4:
            output_step1 = list(range(0, q_final+1))
            time_step1 = [None] * len(output_step1)
            for index in range(len(output_step1)):
                time_step1[index] = (math.asin(output_step1[index]/self.q_high)/(2*math.pi*self.frequency))
            self.output_steps = output_step1
            self.time_steps = time_step1
        elif period/4 < t_frac < 3*period/4:
            output_step1 = list(range(0, self.q_high))
            output_step2 = list(range(self.q_high, q_final-1, -1))
            time_step1 = [None] * len(output_step1)
            time_step2 = [None] * len(output_step2)
            for index in range(len(output_step1)):
                time_step1[index] = (math.asin(output_step1[index]/self.q_high)/(2*math.pi*self.frequency))
            for index in range(len(output_step2)):
                time_step2[index] = (math.pi/(2*math.pi*self.frequency) -
                                     math.asin(output_step2[index]/self.q_high)/(2*math.pi*self.frequency))
            self.output_steps = output_step1 + output_step2
            self.time_steps = time_step1 + time_step2
        elif 3*period/4 < t_frac:
            output_step1 = list(range(0, self.q_high))
            output_step2 = list(range(self.q_high, self.q_low, -1))
            output_step3 = list(range(self.q_low, q_final + 1))
            time_step1 = [None] * len(output_step1)
            time_step2 = [None] * len(output_step2)
            time_step3 = [None] * len(output_step3)
            for index in range(len(output_step1)):
                time_step1[index] = (math.asin(output_step1[index]/self.q_high)/(2*math.pi*self.frequency))
            for index in range(len(output_step2)):
                time_step2[index] = (math.pi/(2*math.pi*self.frequency) -
                                     math.asin(output_step2[index]/self.q_high)/(2*math.pi*self.frequency))
            for index in range(len(output_step3)):
                time_step3[index] = (2*math.pi/(2*math.pi*self.frequency) +
                                     math.asin(output_step3[index]/self.q_high)/(2*math.pi*self.frequency))
            self.output_steps = output_step1 + output_step2 + output_step3
            self.time_steps = time_step1 + time_step2
        self.time_steps = [t + t_start + n_full * period for t in self.time_steps]
        self.analog_steps = [-out * 20 / (2 ** 16) - self.offset for out in self.output_steps]
        self._output()
        # plot for testing
        # plt.plot(self.time_steps, self.analog_steps)
        # plt.show()

        # set the output to be zero at the end of the oscillation
        # bug in the output somewhere, wasn't getting set to zero but the second set_analog_state fixed it
        ew.set_analog_state(self.total_time+1*us, self.board, self.channel, 0)
        ew.set_analog_state(self.total_time + 2*us, self.board, self.channel, 0)
        return self.total_time + 2*us
