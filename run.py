import subprocess
from typing import List

from Entangleware import ew_link as ew
import Base.outputwrappers as out
import Base.channels as ch
import Base.inireset as rst
import Base.magnetics as mag
import Base.masterrepump as laser
import Base.imaging as img
import Base.rf as rftest
import Base.boards as brd

from Base.constants import *

import MidLevelSeq.EvaporationParameters as Param

import TestSequences.testDipole as dip_test
import TestSequences.testMidLevel as mid_test

# Connect to the NI target
ew.connect(1.0)

# Set Default states (Anything before 'build_sequence' will be interpreted as a 'Default' or 'Idle' State)
########################################################################################################
# cart supply default level for MOT
out.analog_out(0.00, ch.cart_supply["connector"], ch.cart_supply["channel"], -0.370)
# cart digital servo default 6
out.digital_out(0.00, ch.cart_digital["connector"], ch.cart_digital["line2"], 1)
out.digital_out(0.00, ch.cart_digital["connector"], ch.cart_digital["line1"], 1)
# camera trigger default high
out.digital_out(0.00, ch.camera_sync["connector"], ch.camera_sync["pin"], 1)
# microwave amp default off
out.digital_out(0.00, ch.uw_amp["connector"], ch.uw_amp["pin"], 1)
# lattice shutters default closed
# out.digital_out(0.00, ch.lattice_shutter["connector"], ch.lattice_shutter["pin"], 1)
out.digital_out(0.00, ch.lattice_shutter["connector"], ch.lattice_shutter["pin"], 0)
# lattice servos default 0
out.analog_out(0.00, ch.lattice1_servo["connector"], ch.lattice1_servo["channel"], 0.00)
out.analog_out(0.00, ch.lattice2_servo["connector"], ch.lattice2_servo["channel"], 0.00)
out.analog_out(0.00, ch.lattice3_servo["connector"], ch.lattice3_servo["channel"], 0.00)
###################################################################################################

reset = rst.Reset()

shots = 1
for iteration in range(shots):
    print("iteration: ", iteration)

    # Build Sequence: Every thing after this line until 'run_sequence' is deterministically timed #
    ###################################################################################################
    ew.build_sequence()

    # reset.general(0.000)
    # reset.laser_locks(1.000)

    # pinch_evap = mid_test.TestPinchEvap(save_images=False)
    # pinch_evap.seq(0.00)

    # dip_evap = dip_test.CrossEvaporation(Param.x_large_thermal, i=iteration, save_images=False)
    # dip_evap.bias_quant(0.00)

    print(ew.run_sequence())

ew.disconnect()
