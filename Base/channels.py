# dictionaries for all the hardware pin mappings

# digital channels

ad9959_1 = {"connector": 0, "update": 7, "reset": 5, "clk": 3, "io": 1, "ref_clk": 125e6,
            "ref_multiplier": 4}
ad9959_1_profile = {"connector": 0, "lat1": 11, "lat2": 9, "lat3": 13}
ad9959_2 = {"connector": 1, "update": 7, "reset": 5, "clk": 3, "io": 1, "ref_clk": 500e6,
            "ref_multiplier": 0}
ad9959_2_profile = {"connector": 0, "pin1": 25, "pin2": 29, "u_pin": 31}
ad9959_3 = {"connector": 1, "update": 15, "reset": 13, "clk": 11, "io": 9, "ref_clk": 125e6,
            "ref_multiplier": 4}

ad9854_evap = {"connector": 1, "update": 31, "reset": 27, "clk": 25, "io": 29, "ref_clk": 50e6,
               "ramp_rate_clk": 24}

ad9910_test = {"connector": 3, "ioupdatepin": 31, "resetpin": 29, "sclkpin": 27, "mosipin": 25, "refclock": 60e6,
               "refclkmultiplier": 1}

slow_dac = {"connector": 3, "ldac": 23, "sync": 21, "clk": 19, "io": 17}

xp_switch = {"connector": 0, "serial_strobe": 23, "crosspoint_strobe": 21, "clock": 19, "io": 17}

shim1 = {"connector": 0, "line1": 2, "line2": 0}
shim2 = {"connector": 0, "line1": 4, "line2": 6}
shim3 = {"connector": 0, "line1": 10, "line2": 8}

pinch_digital = {"connector": 1, "line0": 10, "line1": 8, "line2": 12}
bias_digital = {"connector": 1, "line0": 18, "line1": 16, "line2": 20}
cart_digital = {"connector": 3, "line0": 10, "line1": 8, "line2": 12}

ag_trigger = {"connector": 1, "pin": 19}
ag_polarity = {"connector": 2, "pin": 30}

imaging_trigger = {"connector": 0, "pin": 16}

fets = {"connector": 3, "pin": 4}

aom = {"connector": 0, "probe": 24, "op": 26, "repump": 28}

mot_shutters = {"connector": 3, "one": 18, "two": 16, "three": 20}
op_shutter = {"connector": 3, "pin": 28}
probe_shutter = {"connector": 3, "pin": 26}
repump_shutter = {"connector": 3, "pin": 24}
lattice_shutter = {"connector": 0, "pin": 30}
raman_shutter = {"connector": 2, "pin": 26}

microwave_switch = {"connector": 3, "pin": 1}
uw_amp = {"connector": 1, "pin": 17}
rf_switch = {"connector": 1, "pin": 23}

cart = {"connector": 1, "pin": 2}

arduino_trigger = {"connector": 2, "pin": 14}
camera_sync = {"connector": 0, "pin": 18}
thorcam_trigger = {"connector": 2, "pin": 12}

# analog lines

cart_supply = {"connector": 0, "channel": 0}
pinch_servo = {"connector": 0, "channel": 1}
cart_servo = {"connector": 0, "channel": 2}
bias_servo = {"connector": 0, "channel": 3}
pinch_bias_supply = {"connector": 0, "channel": 4}
ag_supply = {"connector": 0, "channel": 5}
ag_servo = {"connector": 0, "channel": 6}
uw_atten = {"connector": 0, "channel": 7}

speckle_servo = {"connector": 1, "channel": 0}
imaging_servo = {"connector": 1, "channel": 1}
raman1_servo = {"connector": 1, "channel": 2}
raman2_servo = {"connector": 1, "channel": 3}
lattice1_servo = {"connector": 1, "channel": 4}
lattice2_servo = {"connector": 1, "channel": 5}
lattice3_servo = {"connector": 1, "channel": 6}
dipole_servo = {"connector": 1, "channel": 7}
