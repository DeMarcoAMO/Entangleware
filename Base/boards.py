from Entangleware import ew_link as ew
import struct
import warnings
from Base.constants import *
from Base.outputwrappers import digital_time_step


class PeripheralBoard:
    def __init__(self, connector, io_pin, serial_clock_pin, **kwargs):
        """Parent class for communication with peripheral hardware. Uses serial communication to write instructions and
        tells the board to execute the instructions at a deterministic time in the sequence.

        :param connector: FPGA output connector for the digital lines used for serial communication
        :type connector: int
        :param io_pin: serial communication pin
        :type io_pin: int
        :param serial_clock_pin: serial clock pin
        :type serial_clock_pin: int
        :param reset_pin: reset pin
        :type reset_pin: int
        :param io_update_pin: update trigger pin
        :type io_update_pin: int
        """
        self.connector = connector
        self.io_pin = io_pin
        self.serial_clock_pin = serial_clock_pin
        if 'reset_pin' in kwargs:
            self.reset_pin = kwargs.get('reset_pin')
        if 'io_update_pin' in kwargs:
            self.io_update_pin = kwargs.get('io_update_pin')
        self.spi_min_time = digital_time_step

    def _spi(self, spi_time, bytes_to_write, register):
        """Transmits data to eval board. Pulses serial clock pin on/off while sending information
        in bytes_to_write. First writes the 1 byte control register number.

        :param spi_time: time at which to finish writing information to board
        :type spi_time: float
        :param bytes_to_write: control bytes to be sent to board
        :type bytes_to_write: bytes or bytearray
        :param register: control register being addressed
        :type register: int
        :rtype: int
        :return: 0 (effective elapsed time)
        """

        # Write data to the IO pin while cycling the clock pin
        current_time = spi_time
        channel_select = ((1 << self.io_pin) | (1 << self.serial_clock_pin))
        out_enable = channel_select

        # for loops loop the data LSB first, but the timing is reverse chronological
        # so the data is written MSB first
        for individual_bytes in reversed(bytes_to_write):
            for individual_bits in range(8):
                current_time -= self.spi_min_time
                state = ((((individual_bytes >> individual_bits) & 1) << self.io_pin) | (1 << self.serial_clock_pin))
                ew.set_digital_state(current_time, self.connector, channel_select, out_enable, state)
                current_time -= self.spi_min_time
                state = ((((individual_bytes >> individual_bits) & 1) << self.io_pin) | (0 << self.serial_clock_pin))
                ew.set_digital_state(current_time, self.connector, channel_select, out_enable, state)

        for individual_bits in range(8):
            current_time -= self.spi_min_time
            state = ((((register >> individual_bits) & 1) << self.io_pin) | (1 << self.serial_clock_pin))
            ew.set_digital_state(current_time, self.connector, channel_select, out_enable, state)
            current_time -= self.spi_min_time
            state = ((((register >> individual_bits) & 1) << self.io_pin) | (0 << self.serial_clock_pin))
            ew.set_digital_state(current_time, self.connector, channel_select, out_enable, state)
        return 0

    def _update_output(self, spi_time):
        """Pulse the update pin to instruct DDS to enact commands contained in on-chip memory buffer

        :param spi_time: time at which to begin pulse
        :type spi_time: float
        :rtype: float
        :return: time to pulse pin (2 x digital transition time)
        """
        this_time = spi_time
        ew.set_digital_state(this_time, self.connector, 1 << self.io_update_pin, 1 << self.io_update_pin,
                             1 << self.io_update_pin)
        this_time += self.spi_min_time
        ew.set_digital_state(this_time, self.connector, 1 << self.io_update_pin, 1 << self.io_update_pin,
                             0 << self.io_update_pin)
        return 2 * self.spi_min_time


class AD9959(PeripheralBoard):
    def __init__(self, connector, io_pin, serial_clock_pin, reset_pin, io_update_pin, ref_clock, ref_clk_multiplier):
        """Serial communication with an AD9959 evaluation board

        :param connector: FPGA output that the serial lines are located on
        :type connector: int
        :param io_pin: digital line for serial IO
        :type io_pin: int
        :param serial_clock_pin: digital line for serial clock
        :type serial_clock_pin: int
        :param reset_pin: digital line to reset DDS
        :type reset_pin: int
        :param io_update_pin: digital line to trigger DDS update
        :type io_update_pin: int
        :param ref_clock: frequency of reference clock being sent to DDS from clock distribution hardware
        :type ref_clock: float
        :param ref_clk_multiplier: Internal PLL multiplier applied to refclock to generate internal system clock
        :type ref_clk_multiplier: int
        """
        super().__init__(connector=connector, io_pin=io_pin, serial_clock_pin=serial_clock_pin, reset_pin=reset_pin,
                         io_update_pin=io_update_pin)
        self._AD9959_ref_clock = ref_clock
        self._AD9959_ref_clk_multiplier = ref_clk_multiplier
        if ref_clk_multiplier == 0:
            self._AD9959_sys_clock = self._AD9959_ref_clock
        else:
            self._AD9959_sys_clock = self._AD9959_ref_clk_multiplier * self._AD9959_ref_clock

    def initialize(self, dds_time):
        """ Initialize DDS board. Set the reference clock multiplier and VCO gain control.

        :param dds_time: time to enact instructions
        :type dds_time: float
        :rtype: int
        :return: 0 (effective elapsed time)
        """
        # FR1 register
        register = 0x01
        # FR1 [22:18] is the PLL divider ratio
        # FR1 [23] is the VCO gain control
        payload1 = (self._AD9959_ref_clk_multiplier << 2) | (1 << 7)
        payload2 = 0
        payload3 = 0
        data_to_send = bytearray([payload1, payload2, payload3])
        self._spi(dds_time, data_to_send, register)
        self._update_output(dds_time)
        return 0

    def reset(self, dds_time):
        """ Reset DDS by pulsing reset pin, then reinitialize by calling initialize method.

        :param dds_time: Time at which reset command is sent
        :type dds_time: float
        :rtype: float
        :return: elapsed time for reset and initialization of board, 0.02 seconds
        """
        # pulse reset pin
        this_time = dds_time
        channel_select = (1 << self.reset_pin)
        out_enable = channel_select
        state = (1 << self.reset_pin)
        # change reset pin to high
        ew.set_digital_state(this_time, self.connector, channel_select, out_enable, state)
        this_time += .010
        state = (0 << self.reset_pin)
        ew.set_digital_state(this_time, self.connector, channel_select, out_enable, state)
        this_time += .010
        self.initialize(this_time)
        tt = .020
        return tt

    def arbitrary_output(self, dds_time, channel_mask, freq_list, power_list, tt, no_ud=False):
        """Generic output function for the AD9959. Calls for the DDS to output each frequency in freq_list with
        corresponding power in power_list over time tt on given channel(s).

        :param dds_time: time to output first frequency and power in list
        :type dds_time: float
        :param channel_mask: channel(s) to output on (0-3)
        :type channel_mask: list [int] or int
        :param freq_list: frequencies to output (Hz)
        :type freq_list: list [int]
        :param power_list: powers to output (dBm)
        :type power_list: list [float]
        :param tt: total time
        :type tt: float
        :param no_ud: if true doesn't pulse update pin after writing. Allows multiple instructions to enact at once
        :type no_ud: bool
        :rtype: float
        :return: elapsed time, minimum 2*spi_min_time
        """
        if len(freq_list) != len(power_list):
            raise ValueError('AD9959arb: Number of frequencies and powers are not equal')

        n_steps = len(freq_list)
        if n_steps == 0:
            raise ValueError('AD9959arb: No frequency/power')

        last_freq = float('-inf')
        last_mult = float('-inf')
        send_ud = False
        minimum_step_time = 200 * self.spi_min_time

        # make sure the total time is at least the minimum time needed to complete 1 full step
        if tt < minimum_step_time:
            if tt != 0:
                warnings.warn("AD9959arb: total time is negative or too small. Using single step")
            n_steps = 1
            # This is the time for the up_clk function. Does each dds function return a time of 2 * min_time?
            tt = 2 * self.spi_min_time
            dt = tt
        else:
            dt = tt/n_steps
            if dt < minimum_step_time:
                raise ValueError("AD9959arb: time step too small")

        # write the channel select register, option for a list of multiple channels
        temp_time = dds_time - 144 * self.spi_min_time
        if type(channel_mask) is list:
            chan_list = 0
            for chan in channel_mask:
                chan_list |= (1 << chan)
            payload0 = bytearray([chan_list << 4])
        else:
            payload0 = bytearray([(1 << channel_mask) << 4])
        self._spi(temp_time, payload0, 0x00)

        # each step occurs at a time interval determined by the total time and number of steps
        # the step itself is done in negative time, so that it finishes at the appropriate step time
        for i in range(n_steps):
            step_time = i * dt + dds_time
            temp_time = step_time
            freq = freq_list[i]
            if freq != last_freq:
                payload4 = struct.pack('>L', round((1 << 32) * freq / self._AD9959_sys_clock))
                self._spi(temp_time, payload4, 0x04)
                last_freq = freq
                send_ud = True
                temp_time -= 80 * self.spi_min_time

            mult1 = 10 ** (power_list[i] / 10 - 3)
            mult = 1023 * (100 * mult1) ** 0.5 / 0.149
            mult = min(mult, 1023)
            if mult != last_mult:
                payload6 = struct.pack('>BH', 0, ((1 << 12) | int(mult)))
                self._spi(temp_time, payload6, 0x06)
                last_mult = mult
                send_ud = True
                temp_time -= 64 * self.spi_min_time
            if send_ud and not no_ud:
                self._update_output(step_time)
                send_ud = False
        return tt

    def _disable_modulation(self, dds_time):
        payload1 = 0
        payload2 = 1 | (1 << 1)
        payload3 = 0
        payload_combined = bytearray([payload1, payload2, payload3])
        self._spi(dds_time, payload_combined, 0x03)

    def amplitude_mod(self, dds_time, channel_mask, a0, a1):
        """Uses on-board capability to modulate amplitude between a0 and a1 on given channel. Amplitude
        follows voltage applied to additional profile pin on eval_board.

        :param dds_time: time at which amplitude modulation is enabled
        :type dds_time: float
        :param channel_mask: output channel(s)
        :type channel_mask: list [int] or int
        :param a0: amplitude when profile pin voltage low
        :type a0: float
        :param a1: amplitude when profile pin voltage high
        :type a1: float
        :rtype: float
        :return: elapsed time (pulse update pin)
        """

        # write channel select register (0x00)
        this_time = dds_time - 208 * self.spi_min_time
        if type(channel_mask) is list:
            chan_list = 0
            for chan in channel_mask:
                chan_list |= (1 << chan)
            payload0 = bytearray([chan_list << 4])
        else:
            payload0 = bytearray([(1 << channel_mask) << 4])
        self._spi(this_time, payload0, 0x00)

        # if a0 = a1 disable amplitude modulation in register 0x03 (CFR)
        if a0 == a1:
            self._disable_modulation(dds_time)

        else:
            # enable amplitude modulation in register 0x03 (CFR)
            this_time = dds_time - 144 * self.spi_min_time
            payload1 = 1 << 6
            payload2 = 1 | (1 << 1)
            payload3 = 0
            payload_combined = bytearray([payload1, payload2, payload3])
            self._spi(this_time, payload_combined, 0x03)

            # write a1 to channel word 1 (register 0X0A)
            # print("a1: ", a1)
            mult1 = 10 ** (a1 / 10 - 3)
            mult = 1023 * (100 * mult1) ** 0.5 / 0.149
            if mult > 1023:
                mult = 1023
            payload4 = struct.pack('>HBB', (int(mult) << 6), 0, 0)
            this_time = dds_time - 64 * self.spi_min_time
            self._spi(this_time, payload4, 0x0A)

            # write a0 to amplitude control register (register 0x06)
            mult1 = 10**(a0/10 - 3)
            mult = 1023 * (100 * mult1) ** 0.5 / 0.149
            if mult > 1023:
                mult = 1023
            payload5 = struct.pack('>BH', 0, ((1 << 12) | int(mult)))
            self._spi(dds_time, payload5, 0x06)

        t = self._update_output(dds_time)

        return t

    def freq_mod(self, dds_time, channel_mask, freq0, freq1, ramp_time, ramp_step):
        """Uses on-board capability to modulate frequency between freq0 and freq1 on given channel. Frequency
        follows voltage applied to additional profile pin on eval_board. Frequency changes in n=rampstep discrete steps
        over time ramptime.

        :param dds_time: time at which frequency modulation is enabled (seconds)
        :type dds_time: float
        :param channel_mask: output channel(s)
        :type channel_mask: list[int] or int
        :param freq0: frequency when profile pin is held logical low
        :type freq0: float
        :param freq1: frequency when profile pin is held logical high
        :type freq1: float
        :param ramp_time: time to ramp from freq0 to freq1 (and vice versa)
        :type ramp_time: float
        :param ramp_step: number of discrete frequency steps between freq0 and freq1
        :type ramp_step: int
        :rtype: float
        :return: elapsed time (2us update pulse)
        """
        # sequence proceeds backwards from t = 0
        t = self._update_output(dds_time)
        if freq0 == freq1:
            self._disable_modulation(dds_time)
        else:
            # 32 bits (64 cycles) for word 1, 32 for word 0, 32 for rising word, 32 for falling word, 16 for ramp rate
            # register, 24 to enable freq modulation, 24 to clear sweep accumulator, 8 for channel select register

            # write f1 to channel word 1 (register 0x0A)
            this_time = dds_time
            payload4 = struct.pack('>L', round((1 << 32) * freq1 / self._AD9959_sys_clock))
            self._spi(this_time, payload4, 0x0A)
            this_time -= 80 * self.spi_min_time

            # write f0 to frequency tuning word register (0x04)
            payload5 = struct.pack('>L', round((1 << 32) * freq0 / self._AD9959_sys_clock))
            self._spi(this_time, payload5, 0x04)
            this_time -= 80 * self.spi_min_time

            if ramp_time != 0:
                if ramp_step > 255:
                    ramp_step = 255
                    raise ValueError("AD9959 freq_mod: ramp step must be an integer between 1 and 255")
                delta_word = ((freq1-freq0) / ramp_time / self._AD9959_sys_clock) * (ramp_step / self._AD9959_ref_clock)
                # print("delta_word: ", delta_word)
                # print("round: ", round((1 << 32) * delta_word))
                payload6 = struct.pack('>L', round((1 << 32) * delta_word))
                self._spi(this_time, payload6, 0x08)
                this_time -= 80*self.spi_min_time
                self._spi(this_time, payload6, 0x09)
                this_time -= 80 * self.spi_min_time

                payload7 = bytearray([ramp_step, ramp_step])
                self._spi(this_time, payload7, 0x07)
                this_time -= 48 * self.spi_min_time

                # Enable freq modulation with linear sweep
                payload1 = 1 << 7
                payload2 = 1 | (1 << 1) | (1 << 6)
                payload3 = 0
                payload_combined = bytearray([payload1, payload2, payload3])
                self._spi(this_time, payload_combined, 0x03)
                this_time -= 64 * self.spi_min_time

                # Clear Sweep Accumulator
                this_time -= 2 * self.spi_min_time
                self._update_output(this_time)
                payload1 = 0
                payload2 = 1 | (1 << 1)
                payload3 = 1 << 3
                payload_combined = bytearray([payload1, payload2, payload3])
                self._spi(this_time, payload_combined, 0x03)
                this_time -= 64 * self.spi_min_time
            else:
                print("AD9959 freq modulation without linear sweep disables amplitude multiplier")
                payload1 = 1 << 7
                payload2 = 1 | 1 << 1
                payload3 = 0
                payload_combined = bytearray([payload1, payload2, payload3])
                self._spi(this_time, payload_combined, 0x03)
                this_time -= 64 * self.spi_min_time
            payload0 = bytearray([(1 << channel_mask) << 4])
            self._spi(this_time, payload0, 0x00)

        return t


class AD9854(PeripheralBoard):
    def __init__(self, connector, io_pin, serial_clock_pin, reset_pin, io_update_pin, ref_clock, ramp_rate_clock,
                 f_initial=65 * MHz, ref_clock_multiplier=6):
        """Serial communication with an AD9959 evaluation board

        :param connector: FPGA output that the serial lines are located on
        :type connector: int
        :param io_pin: digital line for serial IO
        :type io_pin: int
        :param serial_clock_pin: digital line for serial clock
        :type serial_clock_pin: int
        :param reset_pin: digital line to reset DDS
        :type reset_pin: int
        :param io_update_pin: digital line to trigger DDS update
        :type io_update_pin: int
        :param ref_clock: frequency of reference clock being sent to DDS from clock distribution hardware
        :type ref_clock: float
        :param ramp_rate_clock:
        :type ramp_rate_clock: int
        :param f_initial:
        :type f_initial: float
        """
        super().__init__(connector=connector, io_pin=io_pin, serial_clock_pin=serial_clock_pin, reset_pin=reset_pin,
                         io_update_pin=io_update_pin)
        self._AD9854_ref_clock = ref_clock
        self._AD9854_ramp_rate_clk = ramp_rate_clock
        self._AD9854_sys_clock = ref_clock * ref_clock_multiplier
        self.f_ini = f_initial

    def initialize(self, dds_time):
        """Sets up the AD9854 for use in single tone mode

        :param dds_time: execution time
        :type dds_time: float
        :rtype: float
        :return: 0 (effective elapsed time)
        """
        # control register
        register = 0x07
        # 0X10 - default
        payload1 = 1 << 4
        # PLL range high, PLL multiplier = 6
        # TODO: update this to allow for variable PLL multipler, not just 6
        payload2 = (1 << 6) | (1 << 2) | (1 << 1)
        # external update clock, single tone mode
        payload3 = 0
        # amp mult enable
        payload4 = 1 << 5
        payload_combined = bytearray([payload1, payload2, payload3, payload4])
        self._spi(dds_time, payload_combined, register)
        self._update_output(dds_time)
        # set I channel amplitude multiplier to zero
        this_time = dds_time - 80 * self.spi_min_time
        payload5 = 0
        payload6 = 0
        payload_combined2 = bytearray([payload5, payload6])
        self._spi(this_time, payload_combined2, 0x08)
        return 0

    def chirp_initialize(self, dds_time):
        """Sets up the AD9854 for use in chirp mode. Uses f_initial parameter as initial frequency.

        :param dds_time: execution time
        :type dds_time: float
        :rtype: float
        :return: 0 (effective elapsed time)
        """
        this_time = dds_time
        self._update_output(this_time)

        # set chirp mode in control register
        payload1 = 1 << 4
        payload2 = (1 << 6) | (1 << 2) | (1 << 1)
        payload3 = (1 << 1) | (1 << 2)
        payload4 = 1 << 5
        payload_combined = bytearray([payload1, payload2, payload3, payload4])
        self._spi(this_time, payload_combined, 0x07)
        this_time -= 80 * self.spi_min_time

        # update signal
        this_time -= 2 * self.spi_min_time
        self._update_output(this_time)

        # write initial frequency turning word to register 0x02
        # no data type for six bytes, so separate it into 4 and 2
        freq_data = round((1 << 48) * self.f_ini / self._AD9854_sys_clock)
        payload5 = struct.pack('>LH', freq_data >> 16, freq_data & 65535)
        self._spi(this_time, payload5, 0x02)
        this_time -= 112 * self.spi_min_time

        # set ramp rate clock
        if self._AD9854_ramp_rate_clk >= (1 << 20):
            raise ValueError("AD9854 chirp_initialization: Ramp rate clock out of range")
        # ramp rate is 20 bits (3 bytes, but register doesn't care about last 4 bits)
        payload6 = struct.pack('>HB', self._AD9854_ramp_rate_clk >> 8, self._AD9854_ramp_rate_clk & 255)
        self._spi(this_time, payload6, 0x06)
        this_time -= 64 * self.spi_min_time

        # update signal
        this_time -= 2 * self.spi_min_time
        self._update_output(this_time)

        # set CLR ACC 2 bit in control register high
        payload7 = (1 << 6) | (1 << 3) | (1 << 2) | (1 << 1) | 1
        payload8 = (1 << 6) | (1 << 1) | (1 << 2)
        payload_combined2 = bytearray([payload1, payload7, payload8, payload4])
        self._spi(this_time, payload_combined2, 0x07)
        this_time -= 80 * self.spi_min_time

        # clear delta freq word
        payload9 = bytearray([0, 0, 0, 0, 0, 0])
        self._spi(this_time, payload9, 0x04)
        this_time -= 112 * self.spi_min_time

        return 0

    def reset(self, dds_time):
        """Resets and re-initializes the evaluation board

        :param dds_time: Execution time
        :type dds_time: float
        :rtype: float
        :return: 20 ms (effective elapsed time)
        """
        this_time = dds_time
        ew.set_digital_state(this_time, self.connector, 1 << self.reset_pin, 1 << self.reset_pin, 1 << self.reset_pin)
        this_time += 0.010
        ew.set_digital_state(this_time, self.connector, 1 << self.reset_pin, 1 << self.reset_pin, 0 << self.reset_pin)
        this_time += 0.010
        self.initialize(this_time)
        return 0.020

    def reset_fast(self, dds_time):
        """Quickly resets and re-initializes the evaluation board

        :param dds_time: Execution time
        :type dds_time: float
        :rtype: float
        :return: 2ms (effective elapsed time)
        """
        this_time = dds_time
        ew.set_digital_state(this_time, self.connector, 1 << self.reset_pin, 1 << self.reset_pin, 1 << self.reset_pin)
        this_time += 0.001
        ew.set_digital_state(this_time, self.connector, 1 << self.reset_pin, 1 << self.reset_pin, 0 << self.reset_pin)
        this_time += 0.001
        self.initialize(this_time)
        return 0.002

    def arbitrary_output(self, dds_time, chirp, total_time, freq_list, power_list):
        """Outputs the frequencies in freq_list (at the corresponding powers in power_list) over time total_time.

        :param dds_time: execution time
        :type dds_time: float
        :param chirp: Whether chirp mode is enabled or disabled (will need to call appropriate initialization)
        :type chirp: bool
        :param total_time: time duration of output (seconds)
        :type total_time: float
        :param freq_list: frequencies to output
        :type freq_list: list [float]
        :param power_list: powers to output
        :type power_list: list [float]
        :return: total_time (elapsed time)
        """
        # in chirp mode there should be one more frequency in freq_list than there are powers in power_list
        if chirp and len(power_list) + 1 != len(freq_list):
            raise ValueError("AD9854 arbitrary output: Unequal number of frequencies and powers")
        # not in chirp mode there should be an equal number of frequencies and powers
        if not chirp and len(power_list) != len(freq_list):
            raise ValueError("AD9854 arbitrary output: Unequal number of frequencies and powers")

        n_steps = len(power_list)
        min_time_step = 200 * self.spi_min_time
        delta_t = (self._AD9854_ramp_rate_clk + 1) / self._AD9854_sys_clock
        last_freq = float('inf')
        last_mult = float('inf')
        send_update = False

        # check step size
        if total_time < min_time_step:
            total_time = 2 * self.spi_min_time
            dt = total_time
            warnings.warn("AD9854arb: total time is negative or too small. Using single step")
        else:
            dt = total_time / n_steps
            if dt < min_time_step:
                dt = min_time_step
                warnings.warn("AD9854arb:time step too small. Using minimum time step.")

        # loop through num_steps, write each step backwards in time from i * dt
        for i in range(n_steps):
            this_time = i * dt + dds_time
            temp_time = this_time

            # calculate amplitude tuning word
            mult1 = 10 ** (power_list[i] / 10 - 3)
            mult = 4095 * (100 * mult1)**0.5 / 0.134
            mult = min(mult, 4095)
            # write amplitude tuning word if new amplitude
            if mult != last_mult:
                payload_mult = struct.pack('>H', int(mult) & 4095)
                self._spi(temp_time, payload_mult, 0x08)
                last_mult = mult
                send_update = True
                temp_time -= 48 * self.spi_min_time

            # write frequency tuning word if new frequency
            if not chirp:
                if freq_list[i] != last_freq:
                    freq_data = round((1 << 48) * freq_list[i] / self._AD9854_sys_clock)
                    payload5 = struct.pack('>LH', freq_data >> 16, freq_data & 65535)
                    self._spi(temp_time, payload5, 0x02)
                    last_freq = freq_list
                    send_update = True
                    temp_time -= 112 * self.spi_min_time
            else:
                dfdt = (freq_list[i + 1] - freq_list[i]) / dt
                if dfdt != last_freq:
                    freq_data = round((1 << 48) * delta_t * dfdt / self._AD9854_sys_clock)
                    payload5 = struct.pack('>LH', (freq_data >> 16) & ((1 << 32) - 1), freq_data & 65535)
                    self._spi(temp_time, payload5, 0x04)
                    last_freq = dfdt
                    send_update = True
                    temp_time -= 112 * self.spi_min_time
            # update clock if new word has been written
            if send_update:
                self._update_output(this_time)
                send_update = False
        return total_time


class AD9910(PeripheralBoard):
    def __init__(self, connector1, connector2, io_pin, serial_clock_pin, reset_pin, io_update_pin, DRCTL_pin, ref_clock,
                 ref_clk_multiplier, input_divider):
        super().__init__(connector=connector1, io_pin=io_pin, serial_clock_pin=serial_clock_pin, reset_pin=reset_pin,
                         io_update_pin=io_update_pin)
        self._AD9910_ref_clock = ref_clock
        # self._AD9910_sys_clock = ref_clk_multiplier * self._AD9910_ref_clock
        self._AD9910_sysclockinc = 1e-6
        self._AD9910_input_div = input_divider
        self.AD9910_DRCTLpin = DRCTL_pin
        self.AD9910_connector2 = connector2
        self._AD9910_refclkmultiplier = ref_clk_multiplier

        # if input divider is bypassed see CFR3[14]
        if (self._AD9910_refclkmultiplier == 0 and self._AD9910_input_div == 0):
            self._AD9910_sysclock = self._AD9910_ref_clock / 2
        if (self._AD9910_refclkmultiplier == 0 and self._AD9910_input_div == 1):
            self._AD9910_sysclock = self._AD9910_ref_clock
        if (self._AD9910_refclkmultiplier != 0):
            self._AD9910_sysclock = self._AD9910_refclkmultiplier * self._AD9910_ref_clock

    def reset(self, dds_time):
        """ Reset DDS by pulsing reset pin.

            :param dds_time: time at which reset command is sent
            :type dds_time: float
            :rtype: float
            :return: elapsed time for reset and initialization of board (2 x digital transition)
            """
        this_time = dds_time
        ew.set_digital_state(this_time, self.connector, 1 << self.reset_pin, 1 << self.reset_pin, 1 << self.reset_pin)
        this_time += self.spi_min_time
        ew.set_digital_state(this_time, self.connector, 1 << self.reset_pin, 1 << self.reset_pin, 0 << self.reset_pin)
        this_time += self.spi_min_time
        tt = 2 * self.spi_min_time
        print("reset tt:", tt)
        return tt

    def VCO_SEL(self, sys_freq):
        """ Chooses VCO Range for a given system frequency. Only used if PLL is in use.

            :param sys_freq: system clock frequency
            :type sys_freq: float
            :rtype: int
            :return: VCO_range
            """
        diff = []
        VCO = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05]  # corresponding hex values for each VCO Range
        med_vals = [440e6, 505e6, 600e6, 740e6, 825e6, 985e6]  # avg value of each VCO range from VCO0 - VCO5
        if (sys_freq < 420e6 or sys_freq > 1000e6):
            print("Warning: AD9910 system clock is outside VCO min and max range values.")
        else:
            for i in range(len(med_vals)):
                diff.append(abs(sys_freq - med_vals[i]))
            range1 = min(diff)
            ind = diff.index(range1)
            VCO_range = VCO[ind]
            return VCO_range

    def initialize(self, dds_time):
        """ Initialize DDS board. Set the reference clock multiplier and VCO gain control.

            :param dds_time: time to enact instructions
            :type dds_time: float
            :rtype: int
            :return: time to initialize board (tt)
            """

        # payload 1: controls REFCLK_OUT pin & freq band for PLL VCO in bits [29:28] & [26:24]
        # payload 2: sets charge pump current in bits [21:19]
        # payload 3: disables/enables both PLL & input divider in bits 8 and 15
        # payload 4 : sets PLL multiplier in bits [7:1]

        this_time = dds_time
        payload2 = 0x3F

        if (self._AD9910_refclkmultiplier == 0):
            if (self._AD9910_input_div == 0):
                payload3 = 0x40  # PLL is disabled & Input Divider is enabled
            else:
                payload3 = 0xC0
            payload1 = 0x07  # disables REFCLK_OUT pin & bypasses PLL
            payload4 = 0x00
        else:
            if (self._AD9910_input_div == 0):
                payload3 = 0x41  # PLL is enabled & Input Divider is enabled, SYNC_CLK enabled
            else:
                payload3 = 0xC1
            payload1 = self.VCO_SEL(self._AD9910_sysclock)
            payload4 = (self._AD9910_refclkmultiplier << 1)

        output1 = bytearray([0x00, 0x40, 0x08, 0x20])
        output2 = bytearray([payload1, payload2, payload3, payload4])

        # spi writes in negative time, so function is finished after ud pulse is complete
        self._spi(this_time, output2, 0x02)
        self._update_output(this_time)
        self._spi(this_time, output1, 0x01)
        self._update_output(this_time + .001)
        tt = this_time + .001
        print("done ini time:", tt)
        return tt

    def DRG_enable(self, dds_time):
        """ Enabling the DRG and setting frequency as the digital ramp destination.

            :param dds_time: time to enact instructions
            :type dds_time: float
            :rtype: int
            :return: 0
            """
        this_time = dds_time
        output1 = bytearray([0x00, 0x48, 0x08, 0x20])

        self._spi(this_time, output1, 0x01)
        self._update_output(this_time)
        return 0

    def DRG_high(self, dds_time):
        """ Pulsing DRCTL pin high will initiate positive slope sweep.

            :param dds_time: time at which DRCTL pin is set to high
            :type dds_time: float
            :rtype: float
            :return: time at which DRG is sent high
            """
        this_time = dds_time
        ew.set_digital_state(this_time, self.AD9910_connector2, 1 << self.AD9910_DRCTLpin, 1 << self.AD9910_DRCTLpin, 1 << self.AD9910_DRCTLpin)
        return this_time

    def DRG_low(self, dds_time):
        """ Pulsing DRCTL pin low will initiate negative slope sweep.

            :param dds_time: time at which DRCTL pin is set to low
            :type dds_time: float
            :rtype: float
            :return: time at which DRCTL pin is sent low
            """
        this_time = dds_time
        ew.set_digital_state(this_time, self.AD9910_connector2, 1 << self.AD9910_DRCTLpin, 1 << self.AD9910_DRCTLpin, 0 << self.AD9910_DRCTLpin)
        return this_time

    def set_ramp(self, dds_time, f_min, f_max, delta_t_p, delta_t_n, delta_f_p, delta_f_n):
        """ Enabling the DRG and setting frequency as the digital ramp destination.

            :param dds_time: time to enact instructions
            :type dds_time: float
            :param f_min: ramp lower limit
            :type f_min: float
            :param f_max: ramp upper limit
            :type f_max: float
            :param delta_t_p: positive time step size
            :type delta_t_p: float
            :param delta_t_n: negative time step size
            :type delta_t_n: float
            :param delta_f_p: positive frequency step size
            :type delta_f_p: float
            :param delta_f_n: negative frequency step size
            :type delta_f_n: float
            :rtype: int
            :return: 0
            """
        this_time = dds_time
        if f_min > f_max:
            print("Warning: Ramp lower limit is greater than ramp upper limit.")
        else:
            ftw_min = round((1 << 32) * (f_min / self._AD9910_sysclock))
            ftw_max = round((1 << 32) * (f_max / self._AD9910_sysclock))
            payload0 = struct.pack('>LL', ftw_max, ftw_min)  # sets ramp limits

            STEP_P = round((1 << 32) * (delta_f_p / self._AD9910_sysclock))
            STEP_N = round((1 << 32) * (delta_f_n / self._AD9910_sysclock))
            payload1 = struct.pack('>LL', STEP_N, STEP_P)  # sets step size of the frequency

            P = round(delta_t_p * self._AD9910_sysclock / 4)
            N = round(delta_t_n * self._AD9910_sysclock / 4)
            payload2 = struct.pack('>LL', N, P)  # sets the ramp rate

            # sequence proceeds backwards from the given time parameter
            self._update_output(this_time)
            self._spi(this_time, payload2, 0x0D)
            this_time -= 144 * self.spi_min_time
            self._spi(this_time, payload1, 0x0C)
            this_time -= 144 * self.spi_min_time
            self._spi(this_time, payload0, 0X0B)
        return 0

    def single_tone(self, dds_time, freq):
        """ Function that calls for the DDS to output a single frequency.

            :param dds_time: time to output frequency
            :type dds_time: float
            :param freq: desired frequency
            :type freq: float
            :rtype: int
            :return: 0
            """
        this_time = dds_time
        ftw = round((1 << 32) * (freq / self._AD9910_sysclock))

        payload0 = struct.pack('>BB', 0x08, 0xB5) + struct.pack(">h", 0) + struct.pack(">I",ftw)  # first 4 bytes are set to default values
        self._spi(this_time, payload0, 0x0E)
        self._update_output(this_time)
        print("single tone completed:", this_time)
        return 0


class AD5372(PeripheralBoard):
    def __init__(self, connector, io_pin, serial_clock_pin, sync_pin, ldac_pin):
        """Serial communication with an AD5372 DAC eval board.

        :param connector: FPGA connector the serial communication lines are located on
        :type connector: int
        :param io_pin: serial communication digital line
        :type io_pin: int
        :param serial_clock_pin: serial clock digital line
        :type serial_clock_pin: int
        :param sync_pin: synchronization pin (set low before writing, bring high when done)
        :type sync_pin: int
        :param ldac_pin: load dac pin (DAC output updated when LDAC pin goes low)
        :type ldac_pin: int
        """
        super().__init__(connector=connector, io_pin=io_pin, serial_clock_pin=serial_clock_pin)

        self.sync_pin = sync_pin
        self.ldac_pin = ldac_pin

        self.spi_min_time = 1e-7
        self.v_offset = 4
        self.v_ref = 3

    def _spi_sync(self, spi_time, bytes_to_write, register):
        """Write information in bytes_to_write to command register. Parent _spi method, but sets sync_pin low before
        writing.

        :param spi_time: Execution time (time to finish writing)
        :type spi_time: float
        :param bytes_to_write: information to be sent
        :type bytes_to_write: bytes or bytearray
        :param register: command register to write to
        :type register: int
        :rtype: float
        :return: 0 (effective elapsed time)
        """
        # Write data to the IO pin while cycling the clock pin
        this_time = spi_time

        this_time -= self.spi_min_time
        ew.set_digital_state(this_time, self.connector, (1 << self.sync_pin), (1 << self.sync_pin), (1 << self.sync_pin))

        # TODO:Test this looking at digital waveform, make sure timing of sync pin is still right
        self._spi(this_time, bytes_to_write, register)
        # 2 min_time pulses per bit, 8 bits per byte, n bytes in bytes_to_write
        this_time -= self.spi_min_time * (len(bytes_to_write)*8*2)
        # 2 min_time pulses per bit, 8 bits per byte, 1 byte in register
        this_time -= self.spi_min_time * (1*8*2)

        this_time -= self.spi_min_time
        ew.set_digital_state(this_time, self.connector, (1 << self.sync_pin), (1 << self.sync_pin), (0 << self.sync_pin))

        this_time -= self.spi_min_time
        ew.set_digital_state(this_time, self.connector, (1 << self.sync_pin), (1 << self.sync_pin), (1 << self.sync_pin))
        return 0.0

    def initialize(self, spi_time):
        this_time = spi_time
        channel_select = (1 << self.ldac_pin)
        out_enable = channel_select
        state = (0 << self.ldac_pin)
        ew.set_digital_state(this_time, self.connector, channel_select, out_enable, state)

        # 0xC0 selects X1 reg, all channels; 16 bits of data
        self._spi_sync(spi_time, self._volts_to_code(0.00), 0xC0)

        # set LDAC high before write to prevent output from changing
        this_time = spi_time + self.spi_min_time
        state = (1 << self.ldac_pin)
        ew.set_digital_state(this_time, self.connector, channel_select, out_enable, state)
        return 2 * self.spi_min_time

    def _volts_to_code(self, volts):
        """Converts desired voltage into DAC_CODE according to AD5372 datasheet

        :param volts:desired voltage
        :type volts: float
        :rtype: bytes
        :return: DAC_CODE
        """
        code = (int((0.5 + 65536.0 * (volts + self.v_offset) / (4 * self.v_ref))))
        if code > 0xFFFF:
            warnings.warn("AD5372 voltage out of range, using max voltage")
            code = int(0xFFFF)
        # print(code)
        return struct.pack('>H', code)

    def load(self, spi_time, channel, voltage):
        """Loads a value voltage to be output on channel in the future. Sets LDAC high to prevent DAC output from
        updating immediately.

        :param spi_time: Time to write
        :type spi_time: float
        :param channel: output channel of DAC
        :type channel: int
        :param voltage: output voltage
        :type voltage: float
        :rtype: float
        :return: effective elapsed time (2*min time)
        """
        # 0xC0 selects X1 register, 0x08 + chan addresses channel; 16 bits of data
        register = int(hex(0xC0 + 0x08 + channel), 16)
        self._spi_sync(spi_time, self._volts_to_code(voltage), register)
        this_time = spi_time + self.spi_min_time
        channel_select = (1 << self.ldac_pin)
        out_enable = channel_select
        state = (1 << self.ldac_pin)
        # set LDAC high before write to prevent output from changing
        ew.set_digital_state(this_time, self.connector, channel_select, out_enable, state)
        # self.initialize(this_time)
        return 2 * self.spi_min_time

    def set(self, spi_time, channel, voltage):
        """Updates output of channel to be voltage immediately.

        :param spi_time: Execution time
        :type spi_time: float
        :param channel: output channel
        :type channel: int
        :param voltage: output voltage
        :type voltage: float
        :rtype: float
        :return: effective elapsed time
        """
        reg = int(hex(0xC0 + 0x08 + channel), 16)
        self._spi_sync(spi_time, self._volts_to_code(voltage), reg)
        return 0.0


def reverse_bits(num, bit_size):
    """Reverses bit order of number with value num and bit_size number of bits

    :param num: number to be reversed
    :type num: int
    :param bit_size: number of bits in num
    :type bit_size: int
    :rtype: int
    :return: reversed num
    """
    binary = bin(num)
    reverse = binary[-1:1:-1]
    reverse = reverse + (bit_size - len(reverse)) * '0'

    return int(reverse, 2)


class XPSwitch:
    def __init__(self, channel_dictionary):
        """Control cross-point switch used as master feed-forward

        :param channel_dictionary: dictionary containing connector and digital lines
        :type channel_dictionary: dict
        """
        self.clock_inc = 4e-6
        self.connector = channel_dictionary["connector"]
        self.serial_strobe = channel_dictionary["serial_strobe"]
        self.serial_clock = channel_dictionary["clock"]
        self.serial_data = channel_dictionary["io"]
        self.crosspoint_strobe = channel_dictionary["crosspoint_strobe"]

    def _write_command(self, spi_time, command):
        this_time = spi_time - 21 * self.clock_inc
        for bit in range(10):
            state = (command >> bit) & 1
            ew.set_digital_state(this_time, self.connector, 1 << self.serial_data, 1 << self.serial_data,
                                 state << self.serial_data)
            ew.set_digital_state(this_time, self.connector, 1 << self.serial_clock, 1 << self.serial_clock,
                                 0 << self.serial_clock)
            this_time += self.clock_inc
            ew.set_digital_state(this_time, self.connector, 1 << self.serial_clock, 1 << self.serial_clock,
                                 1 << self.serial_clock)
            this_time += self.clock_inc

        ew.set_digital_state(this_time, self.connector, 1 << self.serial_strobe, 1 << self.serial_strobe,
                             1 << self.serial_strobe)
        this_time += self.clock_inc

        ew.set_digital_state(this_time, self.connector, 1 << self.crosspoint_strobe, 1 << self.crosspoint_strobe,
                             1 << self.crosspoint_strobe)
        this_time += self.clock_inc

        ew.set_digital_state(this_time, self.connector, 1 << self.serial_strobe, 1 << self.serial_strobe,
                             0 << self.serial_strobe)
        ew.set_digital_state(this_time, self.connector, 1 << self.crosspoint_strobe, 1 << self.crosspoint_strobe,
                             0 << self.crosspoint_strobe)
        ew.set_digital_state(this_time, self.connector, 1 << self.serial_clock, 1 << self.serial_clock,
                             0 << self.serial_clock)
        ew.set_digital_state(this_time, self.connector, 1 << self.serial_data, 1 << self.serial_data,
                             0 << self.serial_data)

        return 0

    def switch(self, spi_time, y_address, old_x_address, new_x_address):
        """Switches output at y_address from old x to new x.

        :param spi_time: Execution time (sec)
        :type spi_time: float
        :param y_address: output address
        :type y_address: int
        :param old_x_address: current input address
        :type old_x_address: int
        :param new_x_address: new input address
        :type new_x_address: int
        :rtype: float
        :return: effective elapsed time (s)
        :raise: ValueError if y_address not between 0 and 7
        :raise: ValueError if new_x_address not between 0 and 15
        """

        if (y_address < 0) or (y_address > 7):
            raise ValueError("XPSwitch y_address out of range")
        if new_x_address < 0 or new_x_address > 15:
            raise ValueError("XPSwitch new x_address out of range")

        this_time = spi_time - 23 * self.clock_inc

        if (old_x_address >= 0) and (old_x_address <= 15):
            command = (reverse_bits(y_address, 3) << 7) | (reverse_bits(old_x_address, 4) << 3) | (0 << 2) | (1 << 1) | 0
            self._write_command(this_time, command)

        this_time = spi_time
        command = (reverse_bits(y_address, 3) << 7) | (reverse_bits(new_x_address, 4) << 3) | (1 << 2) | (1 << 1) | 0
        self._write_command(this_time, command)

        return 46 * self.clock_inc

    def initialize(self, spi_time):
        """Initializes crosspoint switch for use. Sets all outputs to use X address 15

        :param spi_time:Execution time
        :type spi_time: float
        :rtype: float
        :return: elapsed time
        """
        time = spi_time
        self._write_command(time, 3)
        time += 0.00023
        time += self.switch(time, 0, -1, 15)
        time += self.switch(time, 1, -1, 15)
        time += self.switch(time, 2, -1, 15)
        time += self.switch(time, 3, -1, 15)
        time += self.switch(time, 4, -1, 15)
        time += self.switch(time, 5, -1, 15)
        time += self.switch(time, 6, -1, 15)
        time += self.switch(time, 7, -1, 15)
        return time
