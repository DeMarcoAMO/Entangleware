from functools import partial
from Base.timing import Sequence
from Base.constants import *
import Entangleware.ew_link as ew
import Base.outputwrappers as out
import Base.channels as ch
import MidLevelSeq.DipoleTrap as Trap

# global variables

# see notes Rb#15 pg 115 03/04/2013
r_bias = 0.0100
r_pinch = 0.0061

# variables to keep track of which coils are on, passed to the release sequences for appropriate handling
img_on = False
bias_on = False
pinch_on = False
ag_on = False
 

def pinch_setpoint(i):
    """ Converts pinch current to servo loop setpoint voltage (calibrated to hall probe monitor)

    :param i: pinch current (Amps)
    :type i: float
    :rtype: float
    :return: servo voltage
    """
    set_pt = -0.004 * i
    return set_pt


def bias_setpoint(i):
    """ Converts bias current to servo loop setpoint voltage (calibrated to hall probe monitor)

    :param i: bias current (Amps)
    :type i: float
    :rtype: float
    :return: servo voltage
    """
    set_pt = -0.004 * i
    return set_pt


def imaging_voltage(i):
    """ Converts imaging current to servo loop setpoint voltage (calibrated to monitor)

    :param i: imaging current (Amps)
    :type i: float
    :rtype: float
    :return: servo voltage
    """
    v = i/2.0
    return v


def cart_setpoint(i):
    """ Converts cart QP current into servo loop setpoint voltage (calibrated to hall probe monitor)

    :param i: cart current (Amps)
    :type i: float
    :rtype: float
    :return: servo voltage
    """
    set_pt = -0.004 * i
    return set_pt


def cart_voltage(i):
    """ Converts cart QP current into power supply voltage

    :param i: cart current (amps)
    :type i: float
    :rtype: float
    :return: power supply voltage
    """
    v = (-5.0/21.0)*(0.06 *i + 0.784 + 0.080 +7.5e-6*i*i)
    return v


# N.E.K. added if ip == 0 check on 04/30/22 to handle situation in which bias_voltage is less than pinch_voltage
# even with ip=0
# N.E.K. 04/30/22 updated bias_voltage = 0.011 * ib + 0.3 Rb#24 pg. 16
# N.E.K. 11/14/22 updated bias_voltage = 0.011 * ib + 0.165 Rb#25 pg. 32
def pinch_bias_voltage(ip, ib):
    """ Converts pinch current and bias current into power supply voltage. Coils run in parallel off same supply, so use
    whichever voltage is higher.

    :param ip: pinch current (amps)
    :type ip: float
    :param ib: bias current (amps)
    :type ib: float
    :rtype: float
    :return: power supply voltage
    :raises: ValueError: if ib > 150 amp"""

    pinch_voltage = 0.0054 * ip + 0.46222
    # pinch_voltage = 0.0061 * ip
    # bias_voltage = r_bias * ib + 0.7
    # bias_voltage = 0.011 * ib + 0.17
    bias_voltage = 0.011 * ib + 0.165
    if ib > 150:
        raise ValueError('Careful going above 150A. Bias voltage was optimized for 125A. If source-drain',
                         'voltage is too high FET will heat up and break.')
    if ip == 0:
        v = -5.0 / 8.0 * bias_voltage
    elif pinch_voltage > bias_voltage:
        v = -5.0/8.0 * pinch_voltage
    else:
        v = -5.0/8.0 * bias_voltage
    return v


# servo set point
def ag_setpoint(i):
    """ Converts antigravity (AG) coil current into a servo loop setpoint voltage calibrated to monitor

    :param i: AG current (amps)
    :type i: float
    :rtype: float
    :return: AG servo voltage
    """
    set_pt = 0.1*i
    return set_pt


# supply voltage
def ag_voltage(i):
    """ Converts AG current into a power supply voltage

    :param i: AG current (amps)
    :type i: float
    :rtype: float
    :return: power supply voltage
    """
    set_pt = 10.0/33.0 * (i*1.255 + 1.092)
    return set_pt


# The cart set-points are 0: off 1: analog control 6: 10A (MOT) 7: 192A (QP trap)
def cart_digital_setpoint(seq_time, i):
    """Sets digital lines for CartQP servo. 3 preset values (i=0: off, i=6: 10A for MOT,
    i=7: 192A for QP trap), and a 4th (i=1) to servo to the setpoint from the sequencer. Presets have lower noise than
    the servo.

    :param seq_time: time to update set point
    :type seq_time: float
    :param i: set point selection
    :type i: int
    :rtype: float
    :return: elapsed time 1us
    """
    channel_mask = 1 << ch.cart_digital["line2"] | 1 << ch.cart_digital["line1"] | 1 << ch.cart_digital["line0"]
    state = ((i >> 2) & 1) << ch.cart_digital["line2"] | ((i >> 1) & 1) << ch.cart_digital["line1"] | \
            (i & 1) << ch.cart_digital["line0"]
    ew.set_digital_state(seqtime=seq_time, connector=ch.cart_digital["connector"], channel_mask=channel_mask,
                         output_enable_state=channel_mask, output_state=state)

    return out.digital_time_step


# the pinch set points are 0: off 1: analog control 2: 585A 3: 10A
def pinch_digital_setpoint(seq_time, i):
    """Sets digital lines for PinchQP servo. 3 preset values (i=0: off, i=2: 585A for QP trap,
    i=3: 10A), and a 4th (i=1) to servo to the setpoint line the sequencer. Presets have lower noise than the servo.

    :param seq_time: time to update set point
    :type seq_time: float
    :param i: set point selection
    :type i: int
    :rtype: float
    :return: elapsed time 1us
    """

    channel_mask = 1 << ch.pinch_digital["line2"] | 1 << ch.pinch_digital["line1"] | 1 << ch.pinch_digital["line0"]
    state = ((i >> 2) & 1) << ch.pinch_digital["line2"] | ((i >> 1) & 1) << ch.pinch_digital["line1"] | \
            (i & 1) << ch.pinch_digital["line0"]
    ew.set_digital_state(seqtime=seq_time, connector=ch.pinch_digital["connector"], channel_mask=channel_mask,
                         output_enable_state=channel_mask, output_state=state)
    return out.digital_time_step


# the bias set points are 0: off 1: analog control 2: 300A 3: 5A
def bias_digital_setpoint(seq_time, i):
    """Sets digital lines for Bias coil servo. 3 preset values (i=0: off, i=2: 300A, i=3: 5A),
    and a 4th (i=1) to servo to the setpoint from the sequencer. Presets have lower noise than the servo.

    :param seq_time: time to update set point
    :type seq_time: float
    :param i: set point selection
    :type i: int
    :rtype: float
    :return: elapsed time 1us
    """

    channel_mask = 1 << ch.bias_digital["line2"] | 1 << ch.bias_digital["line1"] | 1 << ch.bias_digital["line0"]
    state = ((i >> 2) & 1) << ch.bias_digital["line2"] | ((i >> 1) & 1) << ch.bias_digital["line1"] | \
            (i & 1) << ch.bias_digital["line0"]
    ew.set_digital_state(seqtime=seq_time, connector=ch.bias_digital["connector"], channel_mask=channel_mask,
                         output_enable_state=channel_mask, output_state=state)
    return out.digital_time_step


def fets_fast_on(seq_time):
    """ Forces FETs for CartQP fully on in ~20us. Run at the same time that the cart digital set point 7 is selected

    :param seq_time: execution time
    :type seq_time: float
    :rtype: float
    :return: elapsed time
    """

    out.digital_out(seq_time, ch.fets["connector"], ch.fets["pin"], 1)
    t = out.digital_out(seq_time + 1*ms, ch.fets["connector"], ch.fets["pin"], 0)
    return 1*ms + t


class Shims:
    @staticmethod
    def mot(seq_time):
        """ Selects MOT set-point for MOT-chamber shim coils

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line1"], 0)
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line2"], 0)

        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line1"], 0)
        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line2"], 0)

        out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line1"], 0)
        t = out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line2"], 0)
        return t

    @staticmethod
    def molasses(seq_time):
        """ Selects Molasses set-point for MOT-chamber shim coils

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line1"], 1)
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line2"], 0)

        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line1"], 1)
        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line2"], 0)

        out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line1"], 1)
        t = out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line2"], 0)
        return t

    @staticmethod
    def off(seq_time):
        """ Selects off set-point for MOT-chamber shim coils

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """

        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line1"], 0)
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line2"], 1)

        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line1"], 0)
        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line2"], 1)

        out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line1"], 0)
        t = out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line2"], 1)
        return t

    @staticmethod
    def op(seq_time):
        """ Selects optical pumping (OP) set-point for MOT-chamber shim coils

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line1"], 1)
        out.digital_out(seq_time, ch.shim1["connector"], ch.shim1["line2"], 1)

        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line1"], 1)
        out.digital_out(seq_time, ch.shim2["connector"], ch.shim2["line2"], 1)

        out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line1"], 1)
        t = out.digital_out(seq_time, ch.shim3["connector"], ch.shim3["line2"], 1)
        return t


class CartSupply:
    @staticmethod
    def off(seq_time):
        """Preset off current for Cart QP

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time 2us
        """
        t = out.analog_out(seq_time, ch.cart_supply["connector"], ch.cart_supply["channel"], 0.000)
        return t

    @staticmethod
    def mot(seq_time):
        """Preset MOT current for Cart QP

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time 2us
        """
        t = out.analog_out(seq_time, ch.cart_supply["connector"], ch.cart_supply["channel"], -0.370)
        return t

    @staticmethod
    def qp(seq_time):
        """Preset QP current for Cart QP

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time 2us
        """
        t = out.analog_out(seq_time, ch.cart_supply["connector"], ch.cart_supply["channel"], -3.015)
        return t

    @staticmethod
    def qp_low(seq_time):
        """Preset low QP current for Cart QP

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time 2us
        """
        t = out.analog_out(seq_time, ch.cart_supply["connector"], ch.cart_supply["channel"], -3.530)
        return t


class CartQP(Sequence):
    def __init__(self, i0=0, i1=0, ramp_time=1*ms):
        """Handles quadrupole coil pair on cart. Turns on to one of three preset set points, or ramps from current i0
        to i1 over time ramp_time

        :param i0: initial current
        :type i0: float
        :param i1: final current
        :type i1: float
        :rtype: float
        :param ramp_time: time of ramp from i0 to i1
        """

        super().__init__()

        # ramp parameters
        if i0 < 0 or i1 < 0:
            raise ValueError('CartQP current must be positive')
        v0 = cart_voltage(i0)
        v1 = cart_voltage(i1)
        servo0 = cart_setpoint(i0)
        servo1 = cart_setpoint(i1)
        # check to make sure current actually changes
        self.change = True if i0 != i1 else False
        # check whether current is increasing or decreasing
        self.increasing = True if i1 > i0 else False
        self.servo_init = partial(out.analog_out, connector=ch.cart_servo["connector"],
                                  channel=ch.cart_servo["channel"], value=servo0)
        self.supply_ramp = out.AnalogRamp(board=ch.cart_supply["connector"], channel=ch.cart_supply["channel"],
                                          val_start=v0, val_end=v1, total_time=ramp_time)
        self.servo_ramp = out.AnalogRamp(board=ch.cart_servo["connector"], channel=ch.cart_servo["channel"],
                                         val_start=servo0, val_end=servo1, total_time=ramp_time)

    @Sequence._update_time
    def on(self, seq_time):
        """ Turns Cart QP on high to trap atoms (set point 7)

        :param seq_time: time to execute
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        set_pt = partial(cart_digital_setpoint, i=7)
        self.abs(-82*ms, CartSupply.qp)
        self.abs(-0.05*ms, fets_fast_on)
        self.abs(-0.05 * ms, set_pt)

    @Sequence._update_time
    def slow_on6(self, seq_time):
        """ Turns Cart QP on to MOT level (set point 6)

        :param seq_time: time to execute
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        set_pt = partial(cart_digital_setpoint, i=6)
        self.abs(-80*ms, CartSupply.qp)
        self.abs(-0.05*ms, fets_fast_on)
        self.abs(-0.05*ms, set_pt)

    @Sequence._update_time
    def off(self, seq_time):
        """ Turns Cart QP Off

        :param seq_time: time to execute
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        set_pt = partial(cart_digital_setpoint, i=0)
        self.abs(0.00, set_pt)
        self.abs(5*ms, CartSupply.mot)
        self.abs(0.00)

    @Sequence._update_time
    def ramp(self, seq_time):
        """ Ramps cartQP from to i1 in ramp_time

        :param seq_time: time to execute
        :type seq_time: float
        :rtype: float
        :return: elapsed time (ramp_time)
        """
        set_pt = partial(cart_digital_setpoint, i=1)
        if self.change:
            if self.increasing:
                self.abs(-50*ms, self.supply_ramp.linear)
            else:
                self.abs(10*ms, self.supply_ramp.linear)
            self.abs(-10*ms, self.servo_init)
            self.abs(-1*ms, set_pt)
            self.abs(0.00, self.servo_ramp.linear)


# AG coil does not turn off when current servo is 0, needs to be set negative (-0.1A)
# volt_ramp = True is the equivalent of AGCoil_Ramp in the old sequence. Changing that parameter to false is
# equivalent to AGCoil_Ramp2
class AGCoil(Sequence):
    def __init__(self, i0=0, i1=0.0, total_time=0, volt_ramp=True):
        """Handles AntiGravity Coil. Snaps coils on/off or ramps/pulses between i0 and i1 in time tt.

        :param i0: snap on voltage and/or initial ramp/pulse voltage
        :type i0: float
        :param i1: final ramp/pulse voltage
        :type i1: float
        :param total_time: ramp/pulse time
        :type total_time: float
        :param volt_ramp: flag whether to ramp supply voltage as well or just change servo
        :type volt_ramp: bool
        :raise ValueError: if current is too low (i0 or i1 < -0.1A)
        :raise ValueError: if current is too high (i0 or i1 > 25A)
        """

        super().__init__()
        # check to make sure currents are within -0.1 < I < 25
        if i0 < -0.1 or i1 < -0.1:
            raise ValueError('Antigrav current must be greater than -0.1 A')
        if i0 > 25 or i1 > 25:
            raise ValueError('Antigrav current must be less than 25 A')

        # ramp_flags
        self.tt = total_time
        self.change = False if i1 == i0 else True
        self.volt_ramp = volt_ramp
        self.increasing = True if i1 > i0 else False

        # calculate servo and supply voltages
        self.v0 = ag_voltage(i0)
        self.v1 = ag_voltage(i1)
        set0 = ag_setpoint(i0)
        set1 = ag_setpoint(i1)

        # Digital Switch
        self.switch_on = partial(out.digital_out, connector=ch.ag_trigger["connector"],
                                 channel=ch.ag_trigger["pin"], state=1)
        self.switch_off = partial(out.digital_out, connector=ch.ag_trigger["connector"],
                                  channel=ch.ag_trigger["pin"], state=0)
        # Analog Values
        self.supply0 = partial(out.analog_out, connector=ch.ag_supply["connector"], channel=ch.ag_supply["channel"],
                               value=self.v0)
        self.supply_off = partial(out.analog_out, connector=ch.ag_supply["connector"],
                                  channel=ch.ag_supply["channel"], value=ag_voltage(-1.0))

        self.servo_off = partial(out.analog_out, connector=ch.ag_servo["connector"], channel=ch.ag_servo["channel"],
                                 value=0)
        self.servo0 = partial(out.analog_out, connector=ch.ag_servo["connector"], channel=ch.ag_servo["channel"],
                              value=set0)
        self.servo1 = partial(out.analog_out, connector=ch.ag_servo["connector"], channel=ch.ag_servo["channel"],
                              value=set1)

        # Analog Ramps
        self.servo_ramp = out.AnalogRamp(ch.ag_servo["connector"], ch.ag_servo["channel"], set0, set1, self.tt)
        self.v_ramp = out.AnalogRamp(ch.ag_supply["connector"], ch.ag_supply["channel"], self.v0,
                                     self.v1, self.tt)

        # AG Coil on flag
        if i1 > 0:
            self.final_off = False
        else:
            self.final_off = True

    @Sequence._update_time
    def ramp(self, seq_time):
        """Ramps AG Coil from I0 to I1 in time tt. If ramping supply voltage, does supply before servo for increasing
        ramp and after for decreasing to ensure adequate voltage. Updates ag_on flag based on final current I1.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """
        global ag_on
        if self.change:
            if self.volt_ramp:
                if self.increasing:
                    self.abs(-50 * ms, self.v_ramp.linear)
                else:
                    self.abs(50 * ms, self.v_ramp.linear)
            self.abs(-0.1 * ms, self.switch_on)
            self.abs(0.00, self.servo_ramp.linear)
        else:
            self.abs(self.tt)

        if self.final_off:
            ag_on = False
        else:
            ag_on = True

    @Sequence._update_time
    def snap_on(self, seq_time):
        """Snaps AG Coil to current I0.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time
        """

        self.abs(-50 * ms, self.servo_off)
        self.abs(-50 * ms, self.supply0)
        self.abs(-1*ms, self.switch_on)
        self.abs(0.00, self.servo0)

        global ag_on
        ag_on = True

    @Sequence._update_time
    def pulse1(self, seq_time):
        """ Pulses coil from i0 to i1 for time tt

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed_time
        """
        ramp_on = out.AnalogRamp(ch.ag_supply["connector"], ch.ag_supply["channel"], self.v0,
                                 self.v1, 70*ms)
        ramp_off = out.AnalogRamp(ch.ag_supply["connector"], ch.ag_supply["channel"], self.v1,
                                  self.v0, 300 * ms)
        self.abs(-150*ms, ramp_on.linear)
        self.abs(self.tt+10*ms, ramp_off.linear)
        self.abs(-1*ms, self.switch_on)
        self.abs(0.00, self.servo1)
        self.abs(self.tt, self.servo0)

    # quick voltage ramps
    @Sequence._update_time
    def pulse3(self, seq_time):
        """ Pulses coil from i0 to i1 for time tt

                :param seq_time: Execution time
                :type seq_time: float
                :rtype: float
                :return: elapsed_time
                """
        ramp_on = out.AnalogRamp(ch.ag_supply["connector"], ch.ag_supply["channel"], self.v0,
                                 self.v1, 10 * ms)
        ramp_off = out.AnalogRamp(ch.ag_supply["connector"], ch.ag_supply["channel"], self.v1,
                                  self.v0, 10 * ms)
        self.abs(-55 * ms, ramp_on.linear)
        self.abs(self.tt + 10 * ms, ramp_off.linear)
        self.abs(-1 * ms, self.switch_on)
        self.abs(0.00, self.servo1)
        self.abs(self.tt, self.servo0)

    @Sequence._update_time
    def off(self, seq_time):
        """Turns AG coil off (switch, servo, and supply)

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (5.001 ms)
        """
        polarity_normal = partial(out.digital_out, connector=ch.ag_polarity["connector"],
                                  channel=ch.ag_polarity["pin"], state=0)
        self.abs(0.00, self.switch_off)
        self.abs(1*ms, self.servo_off)
        self.abs(1*ms, self.supply_off)
        self.abs(5*ms, polarity_normal)
        global ag_on
        ag_on = False


# sequences to ramp the pinch, bias, or both. The pinch servo oscillates under 4A, and the bias servo oscillates
# between 8 and 12 amps. When ramping the coils off ramp to the edge of the oscillating regime then snap coil off.
class PinchBiasSet(Sequence):
    def __init__(self, ip0=0, ib0=0, ip1=0, ib1=0, total_time=1):
        """Controls Pinch and Bias magnetic coils (handled together since they run off the same power supply).
        Used to snap coils on to i0, snap between i0 and i1, ramp between i0 and i1 over time total_time, and turn the
        coils off.

        :param ip0: initial pinch current
        :type ip0: float
        :param ib0: inital bias current
        :type ib0: float
        :param ip1: final pinch current
        :type ip1: float
        :param ib1: final bias current
        :type ib1: float
        :param total_time: ramp time (seconds)
        :type total_time: float
        """

        super().__init__()

        # check to make sure currents are valid
        if ip0 < 0 or ib0 < 0 or ip1 < 0 or ib1 < 0:
            raise ValueError('Pinch and Bias currents must be positive')
        if 0 < ip0 < 4 or 0 < ip1 < 4:
            raise ValueError('Pinch servo oscillates under 4A')
        if 8 < ib0 < 12 or 8 < ib0 < 12:
            raise ValueError('Bias servo oscillates between 8 and 12A')

        # convert the pinch and bias currents into servo set points and the power supply voltage
        voltage0 = pinch_bias_voltage(ip=ip0, ib=ib0)
        voltage1 = pinch_bias_voltage(ip=ip1, ib=ib1)
        pinch_set_pt0 = pinch_setpoint(ip0)
        bias_set_pt0 = bias_setpoint(ib0)
        pinch_set_pt1 = pinch_setpoint(ip1)
        bias_set_pt1 = bias_setpoint(ib1)

        self.total_time = total_time
        # check to see whether the pinch and bias start on
        self.pinch_start_on = True if ip0 > 0 else False
        self.bias_start_on = True if ib0 > 0 else False

        # check to see if pinch or bias end up at 0
        self.pinch1_off = True if ip1 <= 0 else False
        self.bias1_off = True if ib1 <= 0 else False

        # check if voltage is increasing/changing and if the pinch and bias are changing
        self.increasing = False
        self.change_voltage = False
        self.change_pinch = False
        self.change_bias = False
        if abs(voltage1) > abs(voltage0):
            self.increasing = True
        if voltage0 != voltage1:
            self.change_voltage = True
        if ip0 != ip1:
            self.change_pinch = True
        if ib0 != ib1:
            self.change_bias = True

        # digital lines to set pinch and bias servos to analog control (set point) or off
        self.bias_dig_on = partial(bias_digital_setpoint, i=1)
        self.bias_dig_off = partial(bias_digital_setpoint, i=0)
        self.pinch_dig_on = partial(pinch_digital_setpoint, i=1)
        self.pinch_dig_off = partial(pinch_digital_setpoint, i=0)

        # analog_outs for servo and supply voltages (initial, final, and off)
        self.v_out0 = partial(out.analog_out, connector=ch.pinch_bias_supply["connector"],
                              channel=ch.pinch_bias_supply["channel"], value=voltage0)
        self.v_out1 = partial(out.analog_out, connector=ch.pinch_bias_supply["connector"],
                              channel=ch.pinch_bias_supply["channel"], value=voltage1)
        self.supply_off = partial(out.analog_out, connector=ch.pinch_bias_supply["connector"],
                                  channel=ch.pinch_bias_supply["channel"], value=0)
        self.pinch_out0 = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                                  channel=ch.pinch_servo["channel"], value=pinch_set_pt0)
        self.bias_out0 = partial(out.analog_out, connector=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                 value=bias_set_pt0)
        self.pinch_out1 = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                                  channel=ch.pinch_servo["channel"], value=pinch_set_pt1)
        self.bias_out1 = partial(out.analog_out, connector=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                 value=bias_set_pt1)
        self.pinch_servo_zero = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                                        channel=ch.pinch_servo["channel"], value=0)
        self.bias_servo_zero = partial(out.analog_out, connector=ch.bias_servo["connector"],
                                       channel=ch.bias_servo["channel"], value=0)

        # ramp for supply voltage
        self.voltage_ramp = out.AnalogRamp(board=ch.pinch_bias_supply["connector"],
                                           channel=ch.pinch_bias_supply["channel"], val_start=voltage0, val_end=voltage1,
                                           total_time=total_time)

        # ramps for servo voltages
        # if ramping off, ramp to current range where oscillations start and snap off from there
        if self.pinch1_off:
            self.pinch_ramp = out.AnalogRamp(board=ch.pinch_servo["connector"], channel=ch.pinch_servo["channel"],
                                             val_start=pinch_set_pt0, val_end=pinch_setpoint(4), total_time=total_time)
        else:
            self.pinch_ramp = out.AnalogRamp(board=ch.pinch_servo["connector"], channel=ch.pinch_servo["channel"],
                                             val_start=pinch_set_pt0, val_end=pinch_set_pt1, total_time=total_time)
        if self.bias1_off:
            self.bias_ramp = out.AnalogRamp(board=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                            val_start=bias_set_pt0, val_end=bias_setpoint(5), total_time=total_time)
        else:
            self.bias_ramp = out.AnalogRamp(board=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                            val_start=bias_set_pt0, val_end=bias_set_pt1, total_time=total_time)

        # class attributes to store current supply voltage and servo set points
        # methods that change the current will update these, so the ramp_off methods will always start from the correct
        # current. Defaults to initial values i0.
        self.values0 = {"supply_voltage": voltage0, "pinch_set_pt": pinch_set_pt0, "bias_set_pt": bias_set_pt0}
        self.values1 = {"supply_voltage": voltage1, "pinch_set_pt": pinch_set_pt1, "bias_set_pt": bias_set_pt1}
        self.values_off = {"supply_voltage": 0, "pinch_set_pt": 0, "bias_set_pt": 0}
        self.current_values = self.values0

    @Sequence._update_time
    def snap_on(self, seq_time):
        """Snaps Pinch and/or Bias on to currents ip0 and ib0. Checks which coils are turning on, and updates global
        flags appropriately.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (2us analog out)
        """

        global bias_on
        global pinch_on
        # set the supply voltage
        self.abs(-100 * ms, self.v_out0)
        if self.pinch_start_on:
            # set the servo to analog control and set servo voltage
            self.abs(-1 * ms, self.pinch_dig_on)
            self.abs(0.00, self.pinch_out0)
            pinch_on = True
        else:
            # make sure servo is off
            self.abs(0.00, self.pinch_dig_off)
            pinch_on = False
        if self.bias_start_on:
            # set servo to analog control and set servo voltage
            self.abs(-1*ms, self.bias_dig_on)
            self.abs(0.00, self.bias_out0)
            bias_on = True
        else:
            self.abs(0.00, self.bias_dig_off)
            bias_on = False

        # update current supply voltage and setpoints
        self.current_values = self.values0

    @Sequence._update_time
    def ramp(self, seq_time):
        """Ramps pinch and/or bias from i0 to i1 in time total_time

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: Elapsed time (total_time)
        """

        # update on/off flags based on final currents
        global pinch_on
        global bias_on
        pinch_on = False if self.pinch1_off else True
        bias_on = False if self.bias1_off else True

        # update current supply voltage and setpoints
        self.current_values = self.values1

        pinch_servo_negative = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                                       channel=ch.pinch_servo["channel"], value=-0.1)
        bias_servo_negative = partial(out.analog_out, connector=ch.bias_servo["connector"],
                                      channel=ch.bias_servo["channel"], value=-0.1)
        if self.change_voltage:
            if self.increasing:
                self.abs(-50*ms, self.voltage_ramp.linear)
            else:
                self.abs(10*ms, self.voltage_ramp.linear)
        if self.change_pinch:
            self.abs(-10 * ms, self.pinch_out0)
            self.abs(-1 * ms, self.pinch_dig_on)
            self.abs(0.00, self.pinch_ramp.linear)
            if self.pinch1_off:
                self.rel(0.00, pinch_servo_negative)
                self.rel(0.00, self.pinch_dig_off)
        if self.change_bias:
            self.abs(-10 * ms, self.bias_out0)
            self.abs(-1*ms, self.bias_dig_on)
            self.abs(0.00, self.bias_ramp.linear)
            if self.bias1_off:
                self.rel(0.00, bias_servo_negative)
                self.rel(0.00, self.bias_dig_off)
        self.abs(self.total_time)

    # for use when pinch/bias are already on. Snap from i0 to i1.
    @Sequence._update_time
    def snap_diff(self, seq_time):
        """Snaps pinch and/or bias from i0 to i1.

        :param seq_time: Execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (1us)
        """
        global bias_on
        global pinch_on
        pinch_on = False if self.pinch1_off else True
        bias_on = False if self.bias1_off else True

        # update current supply voltage and setpoints
        self.current_values = self.values1

        # set the voltage
        if self.increasing:
            self.abs(-10 * ms, self.v_out0)
        else:
            self.abs(10 * ms, self.v_out0)
        if self.pinch_start_on or not self.pinch1_off:
            # set the servo to analog control
            self.abs(-1 * ms, self.pinch_dig_on)
            # set the pinch current
            self.abs(-1 * ms, self.pinch_out0)
            self.abs(0.00, self.pinch_out1)
        # if the bias is turning on, set the servo to analog control then set the current. If not, make sure the servo
        # is off
        if self.bias_start_on or not self.bias1_off:
            self.abs(-1 * ms, self.bias_dig_on)
            self.abs(-1*ms, self.pinch_out1)
            self.abs(0.00, self.bias_out1)
        else:
            self.abs(0.00, self.bias_dig_off)

    @Sequence._update_time
    def off(self, seq_time):
        """Turns pinch and bias coils off from current values of parameters ip and ib

        :param seq_time: Execution time
        :return: elapsed time (19.702 ms)
        """

        # set up servo setpoints
        pinch_servo_start = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                                    channel=ch.pinch_servo["channel"], value=self.current_values["pinch_set_pt"])
        bias_servo_start = partial(out.analog_out, connector=ch.bias_servo["connector"],
                                   channel=ch.bias_servo["channel"], value=self.current_values["bias_set_pt"])
        pinch_servo_negative = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                                       channel=ch.pinch_servo["channel"], value=-0.1)
        bias_servo_negative = partial(out.analog_out, connector=ch.bias_servo["connector"],
                                      channel=ch.bias_servo["channel"], value=-0.1)

        # set up servo and supply ramps
        off_time = 0.75*ms
        pinch_servo_ramp = out.AnalogRamp(board=ch.pinch_servo["connector"], channel=ch.pinch_servo["channel"],
                                          val_start=self.current_values["pinch_set_pt"], val_end=pinch_setpoint(4),
                                          total_time=off_time)
        bias_servo_ramp = out.AnalogRamp(board=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                         val_start=self.current_values["bias_set_pt"], val_end=bias_setpoint(5),
                                         total_time=off_time)
        supply_ramp = self.voltage_ramp = out.AnalogRamp(board=ch.pinch_bias_supply["connector"],
                                                         channel=ch.pinch_bias_supply["channel"],
                                                         val_start=self.current_values["supply_voltage"],
                                                         val_end=pinch_bias_voltage(0, 0), total_time=off_time)

        # ramp pinch and bias currents down then snap off
        if self.current_values["pinch_set_pt"] != 0:
            self.abs(-10*ms, pinch_servo_start)
            self.abs(-1*ms, self.pinch_dig_on)
            self.abs(0.1*ms, pinch_servo_ramp.linear)
            self.rel(0.00, pinch_servo_negative)
        if self.current_values["bias_set_pt"] != 0:
            self.abs(-10*ms, bias_servo_start)
            self.abs(-1*ms, self.bias_dig_on)
            self.abs(0.1*ms, bias_servo_ramp.linear)
            self.rel(0.00, bias_servo_negative)
        self.rel(0.00, [self.pinch_dig_off, self.bias_dig_off])
        self.abs(10.1 * ms, supply_ramp.linear)

        # clean up
        self.abs(19.7 * ms, self.pinch_servo_zero)
        self.abs(19.7 * ms, self.bias_servo_zero)
        self.abs(19.7 * ms, self.supply_off)

        global pinch_on
        pinch_on = False
        global bias_on
        bias_on = False

    @Sequence._update_time
    def off_qp(self, seq_time):
        """Turns pinch coils off from full 585A qp current.

        :param seq_time: execution time
        :return: elapsed time (19.702 ms)
        """
        qp_low = partial(out.analog_out, connector=ch.pinch_servo["connector"],
                         channel=ch.pinch_servo["channel"], value=-2.3154)
        qp_ramp = out.AnalogRamp(board=ch.pinch_servo["connector"], channel=ch.pinch_servo["channel"],
                                 val_start=-2.3154, val_end=1.000, total_time=1*ms)

        self.abs(0.05 * ms, qp_low)
        # set pinch servo to reference voltage
        self.abs(0.1 * ms, self.pinch_dig_on)
        # ramp servo off
        self.abs(0.1 * ms, qp_ramp.linear)

        # clean up
        self.abs(1*ms, self.bias_dig_off)
        self.abs(10 * ms, self.pinch_dig_off)
        self.abs(19.7*ms, self.pinch_servo_zero)
        self.abs(19.7*ms, self.bias_servo_zero)
        self.abs(19.7*ms, self.supply_off)

        global pinch_on
        pinch_on = False
        global bias_on
        bias_on = False

    @Sequence._update_time
    def clean_up(self, seq_time):
        """Turns off supply and servos if both coils are already at 0 current.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (10.002 ms)
        """
        self.abs(0.00, self.bias_dig_off)
        self.abs(0.00, self.pinch_dig_off)
        self.abs(10*ms, self.pinch_servo_zero)
        self.abs(10*ms, self.bias_servo_zero)
        self.abs(10*ms, self.supply_off)

        global pinch_on
        pinch_on = False
        global bias_on
        bias_on = False

    @Sequence._update_time
    def clean_up_fast(self, seq_time):
        """Turns off supply and servos if both coils are already at 0 current.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (10.002 ms)
        """
        self.abs(0.00, self.bias_dig_off)
        self.abs(0.00, self.pinch_dig_off)
        self.abs(1*ms, self.pinch_servo_zero)
        self.abs(1*ms, self.bias_servo_zero)
        self.abs(1*ms, self.supply_off)

        global pinch_on
        pinch_on = False
        global bias_on
        bias_on = False

# Sequences to change just bias coil (assumes pinch is off). Same as PinchBiasSet, just without Pinch
class BiasSet(Sequence):
    def __init__(self, total_time, ib0, ib1=0, sig_a=1, exp_tau=1.5*ms):
        super().__init__()
        global pinch_on
        if pinch_on:
            raise ValueError('Pinch is on. Use PinchBiasSet')
        # check current values
        if ib0 < 0 or ib1 < 0:
            raise ValueError('Bias currents must be positive')
        # determine supply voltages
        voltage0 = pinch_bias_voltage(0, ib0)
        voltage1 = pinch_bias_voltage(0, ib1)
        voltage_off = pinch_bias_voltage(0, 0)

        self.tt = total_time
        # make sure the coil is on when you start
        self.on_flag = True if ib1 != 0 else False
        # check if current is increasing or decreasing (affects timing of supply ramp).
        self.increase_flag = True if abs(voltage1) > abs(voltage0) else False
        # check to make sure current is changing
        self.change_flag = True if ib0 != ib1 else False

        self.dig_ctl = partial(bias_digital_setpoint, i=1)
        self.dig_off = partial(bias_digital_setpoint, i=0)

        self.ang0 = partial(out.analog_out, connector=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                            value=bias_setpoint(ib0))
        self.ang1 = partial(out.analog_out, connector=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                            value=bias_setpoint(ib1))
        self.ang_off = partial(out.analog_out, connector=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                               value=0.1)
        self.v_snap = partial(out.analog_out, connector=ch.pinch_bias_supply["connector"],
                              channel=ch.pinch_bias_supply["channel"], value=voltage1)

        v_low = -5.0/8.0*0.17
        self.v_snap_low = partial(out.analog_out, connector=ch.pinch_bias_supply["connector"],
                                   channel=ch.pinch_bias_supply["channel"], value=v_low)
        self.v_off = partial(out.analog_out, connector=ch.pinch_bias_supply["connector"],
                             channel=ch.pinch_bias_supply["channel"], value=voltage_off)

        # ramp for servo and supply
        self.servo_ramp = out.AnalogRamp(board=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                         val_start=bias_setpoint(ib0), val_end=bias_setpoint(ib1),
                                         total_time=total_time, a=sig_a, tau=exp_tau)
        self.supply_ramp = out.AnalogRamp(board=ch.pinch_bias_supply["connector"],
                                          channel=ch.pinch_bias_supply["channel"], val_start=voltage0, val_end=voltage1,
                                          total_time=total_time, a=sig_a, tau=exp_tau)
        self.supply_ramp_low = out.AnalogRamp(board=ch.pinch_bias_supply["connector"],
                                              channel=ch.pinch_bias_supply["channel"], val_start=voltage0, val_end=v_low,
                                              total_time=total_time, a=sig_a, tau=exp_tau)

        self.servo_off_ramp = out.AnalogRamp(board=ch.bias_servo["connector"], channel=ch.bias_servo["channel"],
                                             val_start=bias_setpoint(ib1), val_end=bias_setpoint(0),
                                             total_time=total_time, a=sig_a)
        self.supply_off_ramp = out.AnalogRamp(board=ch.pinch_bias_supply["connector"],
                                              channel=ch.pinch_bias_supply["channel"], val_start=voltage1,
                                              val_end=voltage_off, total_time=total_time, a=sig_a)

    # ramps from current ib1 down to zero
    @Sequence._update_time
    def ramp_off(self, seq_time):
        if self.on_flag:
            self.abs(-10*ms, self.ang1)
            self.abs(-1*ms, self.dig_ctl)
            self.abs(0.00, self.servo_off_ramp.linear)
            self.abs(0.00, self.ang_off)
        self.abs(10*ms, self.supply_off_ramp.linear)
        self.abs(self.tt)

        global bias_on
        bias_on = False

    # ramps from current ib0 to ib1
    @Sequence._update_time
    def ramp(self, seq_time):
        # ramp up supply before the servo if the current is increasing
        if self.increase_flag:
            self.abs(-50*ms, self.supply_ramp.linear)
        # otherwise ramp down supply after the servo if the current is decreasing
        else:
            self.abs(10*ms, self.supply_ramp.linear)
        # ensure the servo is set up for analog control, then ramp
        if self.change_flag:
            self.abs(-10 * ms, self.ang0)
            self.abs(-1 * ms, self.dig_ctl)
            self.abs(0.00, self.servo_ramp.linear)

    @Sequence._update_time
    def ramp_sig(self, seq_time):
        # ramp up supply before the servo if the current is increasing
        if self.increase_flag:
            self.abs(-50 * ms, self.supply_ramp.linear)
        # otherwise ramp down supply after the servo if the current is decreasing
        else:
            self.abs(10 * ms, self.supply_ramp.linear)
        # ensure the servo is set up for analog control, then ramp
        if self.change_flag:
            self.abs(-10 * ms, self.ang0)
            self.abs(-1 * ms, self.dig_ctl)
            self.abs(0.00, self.servo_ramp.sigmoidal)

    # used to play with timing of voltage ramp relative to servo ramp
    @Sequence._update_time
    def ramp_sig2(self, seq_time):
        # ramp up supply before the servo if the current is increasing
        if self.increase_flag:
            self.abs(-50 * ms, self.supply_ramp.linear)
        # otherwise ramp down supply after the servo if the current is decreasing
        else:
            # self.abs(0.5 * ms, self.supply_ramp.linear)
            self.abs(0.5 * ms, self.supply_ramp_low.linear)
            # self.abs(1.1 * ms, self.v_snap)
        # ensure the servo is set up for analog control, then ramp
        if self.change_flag:
            # self.abs(-10 * ms, self.ang0)
            # self.abs(-1 * ms, self.dig_ctl)
            self.abs(0.00, self.servo_ramp.sigmoidal)

    @Sequence._update_time
    def ramp_exp(self, seq_time):
        # ramp up supply before the servo if the current is increasing
        if self.increase_flag:
            self.abs(-50 * ms, self.supply_ramp.linear)
        # otherwise ramp down supply after the servo if the current is decreasing
        else:
            self.abs(10 * ms, self.supply_ramp.linear)
        # ensure the servo is set up for analog control, then ramp
        if self.change_flag:
            self.abs(-10 * ms, self.ang0)
            self.abs(-1 * ms, self.dig_ctl)
            self.abs(0.00, self.servo_ramp.exponential)

    @Sequence._update_time
    def ramp_off_sig(self, seq_time):
        if self.on_flag:
            self.abs(-10 * ms, self.ang1)
            self.abs(-1 * ms, self.dig_ctl)
            self.abs(0.00, self.servo_off_ramp.sigmoidal)
        self.abs(10 * ms, self.supply_off_ramp.linear)
        self.abs(self.tt)

        global bias_on
        bias_on = False

    # snaps on to current ib1
    @Sequence._update_time
    def snap_on(self, seq_time):
        self.abs(-50 * ms, self.v_snap)
        self.abs(-1 * ms, self.dig_ctl)
        self.abs(0.00, self.ang1)
        global bias_on
        bias_on = True

    # snaps off
    @Sequence._update_time
    def snap_off(self, seq_time):
        self.abs(-1 * ms, self.dig_ctl)
        self.abs(0.00, self.ang_off)
        self.abs(10 * ms, self.v_off)
        global bias_on
        bias_on = False


class ImagingCoil(Sequence):
    def __init__(self, i0=0, i1=6, tt=1*ms):
        """Controls imaging coils. Has three preset values--off, on low for quantization, or high for imaging, or
        ramps from i0 to i1 in time tt.

        :param i0: ramp initial current
        :type i0: float
        :param i1: ramp final current
        :type i1: float
        :param tt: ramp time
        :type tt: float
        """
        super().__init__()
        self.trigger_on = partial(out.digital_out, connector=ch.imaging_trigger["connector"],
                                  channel=ch.imaging_trigger["pin"], state=1)
        self.trigger_off = partial(out.digital_out, connector=ch.imaging_trigger["connector"],
                                   channel=ch.imaging_trigger["pin"], state=0)
        self.servo_off = partial(out.analog_out, connector=ch.imaging_servo["connector"],
                                 channel=ch.imaging_servo["channel"], value=0)
        self.servo_on = partial(out.analog_out, connector=ch.imaging_servo["connector"],
                                channel=ch.imaging_servo["channel"], value=3)
        self.servo_on_low = partial(out.analog_out, connector=ch.imaging_servo["connector"],
                                    channel=ch.imaging_servo["channel"], value=imaging_voltage(0.5))
        v0 = imaging_voltage(i0)
        v1 = imaging_voltage(i1)
        self.analog_ramp = out.AnalogRamp(ch.imaging_servo["connector"], ch.imaging_servo["channel"], v0, v1,
                                   tt)

    @Sequence._update_time
    def on(self, seq_time):
        """Turns imaging coil on full

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (1us)
        """
        self.abs(-5 * ms, self.servo_on)
        self.abs(0.00, self.trigger_on)
        global img_on
        img_on = True

    @Sequence._update_time
    def off(self, seq_time):
        """Turns imaging coil off

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (5.002 ms)
        """
        self.abs(0.00, self.trigger_off)
        self.abs(5*ms, self.servo_off)
        global img_on
        img_on = False

    @Sequence._update_time
    def on_low(self, seq_time):
        """Turns imaging coil on low.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (1us)
        """
        self.abs(-5 * ms, self.servo_on_low)
        self.abs(0.00, self.trigger_on)
        global img_on
        img_on = True

    @Sequence._update_time
    def low(self, seq_time):
        """Turns down imaging coil to low if already on.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (2us)
        """
        self.abs(0.00, self.servo_on_low)
        global img_on
        img_on = True

    # imaging coil already on, just needs to be turned up high (Imaging_Coil_On2 in old sequencer)
    @Sequence._update_time
    def high(self, seq_time):
        """Turns imaging coil up to full on if already on.

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time (2us)
        """
        self.abs(0.00, self.servo_on)
        global img_on
        img_on = True

    @Sequence._update_time
    def ramp(self, seq_time):
        """Ramps from i0 to i1 in time tt

        :param seq_time: execution time
        :type seq_time: float
        :rtype: float
        :return: elapsed time tt
        """
        self.abs(0, self.trigger_on)
        self.abs(0, self.analog_ramp.linear)
        global img_on
        img_on = True


class MagneticKick(Sequence):
    def __init__(self, pulse_time=1.5*ms, ag_0=-0.1, ag_1=3, ipb=4, ib0=Trap.bias_quant_current, ip0=0):
        """Pulses one or magnetic coils on/off quickly to induce center of mass motion of atomic cloud

        :param pulse_time: duration of kick (seconds)
        :type pulse_time: float
        :param ag_1: antigravity coil kick current
        :type ag_1: float
        :param ipb: pinch and bias coils kick current
        :type ipd: float
        :param ib0: initial bias current (before/after kick)
        :type ib0: float
        :param ip0: initial pinch current (before/after kick)
        :type ip0: float
        """
        super().__init__()
        self.tt = pulse_time
        self.ag_kick1 = AGCoil(i0=0.5, i1=ag_1 + 0.5, total_time=pulse_time)
        self.ag_kick3 = AGCoil(i0=-0.1, i1=ag_1 + 0.5, total_time=pulse_time)

        self.pinch_bias_coil = PinchBiasSet(ip0=ipb, ib0=ipb)

        self.pb_snap_up = PinchBiasSet(ip0=ip0, ib0=ib0, ip1=ip0+ipb, ib1=ib0+ipb)
        self.pb_snap_down = PinchBiasSet(ip0=ip0+ipb, ib0=ib0+ipb, ip1=ip0, ib1=ib0)

    @Sequence._update_time
    def ag(self, seq_time):
        global ag_on
        if ag_on:
            self.abs(0.00, self.ag_kick1.pulse1)
        else:
            self.abs(-5*ms, self.ag_kick3.switch_on)
            self.abs(0.00, self.ag_kick3.pulse3)
        self.abs(self.tt)

    @Sequence._update_time
    def pinch_bias(self, seq_time):
        global pinch_on
        global bias_on
        print("bias_on: ", bias_on)
        if pinch_on or bias_on:
            self.abs(0.00, self.pb_snap_up.snap_diff)
            self.abs(self.tt, self.pb_snap_down.snap_diff)
            self.abs(self.tt)
        else:
            self.abs(0.00, self.pinch_bias_coil.snap_on)
            self.abs(self.tt, self.pinch_bias_coil.clean_up)
            self.abs(self.tt)
