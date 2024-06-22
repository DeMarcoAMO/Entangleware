# EntanglewareRubidiumSequencer
An example of the sequencer and control platform for the DeMarco Lab Rubidium Apparatus at the University of 
Illinois at Urbana-Champaign. See our paper [[1]](#1) for a complete overview. 

Experimental quantum physics and computing platforms rely on sophisticated control and timing 
systems that must be deterministic. For example, a sequence to create a Bose-Einstein Condensate
in our lab invovles 46,812 analog and digital transitions over 100 seconds with 20ns timing 
precision and nanosecond timing drift. To achieve this, we utilize industry-standard National 
Instruments (NI) hardware. A master 10MHz clock conditioned to the Global Positioning Satellite 
constellation is used for timing stability. The hardware is managed by an intermediate program, 
the Entangleware Control Application (ECA) created by our partner 
[Entangleware](<https://entangleware.com/>).

The experiment is run in a "shot" mode, where a single run of the experiment produces data and 
parameters are changed between runs. The shot begins when the ECA triggers the hardware. 
Everything after the trigger is deterministically timed until the shot finishes. The actual
timing within the sequence is handled at the hardware level by the FPGA and clock distribution
system, not this software. The fundamental hardware outputs are analog and digital transitions 
that occur at precise times within the 
experimental run. We call a set of these transitions and times a "sequence". This project is used
to generate the necessary list of transitions and times and compile them into a bitstream that is
sent to the ECA via a standard TCP/UDP network interface. 

We divide the generation of these transitions into a hierarchy of sub-sequences. This 
sub-sequences describe logically separate steps, possibly interleaved in time, with adjustable 
relative timing between steps. Lower level sequences (found in Base) reflect the underlying 
hardware (e.g. sequences for magnetic coils), while mid-level sequences (MidLevelSeq) reflect 
the stage of the experiment (e.g. evaporative cooling).

## Table of contents
* [Project Organization](#project-organization)
* [Running the Sequencer](#running-the-sequencer)
* [Entangleware](#entangleware)
* [Base](#base)
  * [Timing](#timing)
  * [Boards](#boards)
  * [Output Wrappers](#output-wrappers)
  
* [MidLevel](#midlevel)
  * [MOT](#mot)
  * [Magnetic Traps](#magnetic-traps)
  * [Dipole Trap](#dipole-trap)
  * [Dipole Release](#dipole-release)
  
* [Test Sequences](#test-sequences)
  * [Test MidLevel](#test-midlevel)
  * [Test Dipole](#test-dipole)
  
## Project Organization
* README
* run.py
* Entangleware
    * ew_link.py
* Base
    * timing.py
    * outputwrappers.py
    * boards.py
    * channels.py
    * constants.py
    * TimingREADME
    * BoardsREADME
* MidLevel
    * MOT.py
    * MagneticTraps.py
    * DipoleTrap.py
    * DipoleRelease.py
    * EvaporationParameters.py
* TestSequences
    * SequencerExample.py
    * testMidLevel.py
    * testDipole.py
 
The Entangleware folder contains everything necessary for generating and filling the bitstream, including the fundamental outputs,
and network communication with the ECA. 

Base contains the Sequence class for timing (timing.py), functions for analog and digital outputs (outputwrappers.py), 
and all sequences that directly control hardware (e.g., lasers and magnetic coils). 

MidLevel contains sequences for different stages of an experimental run: transerring the MOT to a magnetic trap, RF evaporation, 
and optical evaporation. All optical evaporation parameters are stored as dictionaries in EvaporationParameters.py.

TestSequences contains both hardware tests (e.g. turn a magnetic coil on/off) and stage tests with the atoms 
(e.g. do some level of RF evaporation and image).

## Running the Sequencer

To run a sequence, the software needs to connect to the ECA via a network interface, generate the bitstream containing all 
the desired transitions, and transmit that to the ECA. The module run.py within the overall project directory contains our 
default script to execute a sequence. A simple version looks like:
```python
ew.connect(1.0)
ew.build_sequence()
makeBEC = CrossEvaporation()
makeBEC.seq(0.00)
print(ew.run_sequence())
ew.disconnect()
```

`ew.connect` establishes the network communication with the ECA, and `ew.build_sequence` initializes the bitstream to be sent to the ECA. 
Everything between `build_sequence` and `run_sequence` populates that bitstream with the desired transitions.
The sequence being run here is the seq method of a class called `CrossEvaporation`. 
`ew.run_sequence` transmits the bitstream, and `ew.disconnect` closes the network communication.

Our run module also contains analog and digital transitions between connect and build_sequence. 
Anything found here is treated as a default value for those channels
and is not deterministically timed. 

## Entangleware

All the functions the user will normally call are found in the ew_link module within the Entangleware directory.
### Outputs
The two fundamental outputs are found in Entangleware.ew_link.py:
```python
set_digital_state(seqtime, connector, channel_mask, output_enable_state, output_state)
set_analog_state(seq_time, board, channel, value)
```

`channel_mask`, `output_enable_state`, and `output_state` are all all bit registers, e.g. to address the 4th channel on the 
connector the `channel_mask` would be `1<<4`. ``output_enable_state`` is always set to `1` for all channels in our system, 
but allows for lines to become inputs rather than outputs for in-loop decision making. To aid legibility, two wrapper functions are 
found in [Base.outputwrappers.py](#output-wrappers).
 
## Base
### Timing
We use two types of timing, absolute and relative. Absolute timing occurs at some time after the hardware trigger. Relative timing occurs after the previous step in the sequence finishes.  The `Sequence` class in Base.timing.py is used to keep track of and increment time within the sequence (where time is a float in units of seconds). All sequences and sub-sequences are daughter classes of this `Sequence` class.
See TimingREADME in the Base directory for in-depth explanation of Sequence class.

The class has two attributes, `start_time` and `current_time`. `start_time` is when the sequence or sub-sequence begins in units of seconds, relative to the hardware trigger. `current_time` is incremented as the sequence progresses. The sequence class has two methods:
```python
abs(t_step, seq)
rel(delay_time, seq)
```
Both methods execute the step/sub-sequence `seq`. `abs` executes `seq` at time `t_step` after `start_time`,
while `rel` waits for `delay_time` after the end of the previous step/sub-sequence before executing `seq`. `seq` returns
the "elapsed time" it takes to run, and `current_time` is incremented appropriately.

### Boards
The boards.py module contains APIs for interfacing with peripheral hardware. Included are AD9959,
AD9854, and AD9910 direct digital synthesizers (DDSs) for generating RF signals, as well as an 
AD5372 digital-to-analog converter (DAC). All of these devices interface with the sequencer via
standard serial communication. These APIs wrap the serial communication and provide the user with simple commands
for output RF frequencies and analog voltages. See the BoardsREADME in the Base directory for more information.

### Output Wrappers

#### analog_out and digital_out
Two wrapper functions are provided that take the desired channel number, ect.., as a simple integer argument rather 
than a bit register like those found in [ew_link.py](#outputs).

```python
digital_out(seq_time, connector, channel, state)
analog_out(seq_time, connector, channel, value)
```
Here connector and channel are integers for the desired connector (there are 4 VHDCI output connectors on the FPGA
and 2 analog source cards) and channel number (0-31 on each FPGA connector and 0-7 on each analog source card). `State` 
is binary 0 or 1, value is a float between -10 and 10 (the output voltage range of the PCI-6733 analog source card).

#### AnalogRamp
A class used for generating "continuous" ramps of the analog source card outputs. Rather than update the output voltage
of the analog line at a set rate, we calculate when each bit flip in the analog register should occur for a given ramp
trajectory and call for the transition at the appropriate time. This reduces the number of transitions called for, 
minimizing compilation time, and more accurately reflects the nature of the underlying hardware. 

Our PCI-6733 analog source cards have a 16 bit register spanning -10V to 10V. This means each bit in the register 
represents roughly 0.3mV (20V/2^(16)). For a desired ramp the class generates a list of all the bit transitions needed,
then uses the inverse of the ramp function to find when each transition should occur. 

THe following ramps are currently supported: linear, sigmoidal, and exponential. Adding additional ramps is easily 
accomplished. 

#### AnalogOscillate
AnalogOscillate functions very similarly to AnalogRamp, but is used for oscillating functions. Calculating the inverse
functions needs to account for the domain of the inverse trig functions. 

### Hardware Control
Also contained within Base are the sequences used to talk to the fundamental hardware of the apparatus--lasers, shutters
magnetic coils, microwave and rf sources, and so forth. 

## MidLevel
The MidLevel Directory contains all the sequences that control different stages of the apparatus--i.e., loading the MOT
into the magnetic quadrupole trap, transporting atoms down to the science cell, RF evaporation, and evaporation in the 
optical dipole trap. 

### MOT
`QPCaptureF1` is the sequence that loads the atoms from the MOT into a magnetic quadrupole trap attached to a cart on a 
linear track that then transports the atoms down to the science cell. The sequence first does a stage of optical 
molasses cooling, followed by optically pumping the atoms into the F=1, mf=-1 hyperfine state (a low field-seeking and 
therefore magnetically trappable state). Finally, the current in the cart quadrupole trap is ramped high to trap the 
atoms. 

### Magnetic Traps
The sequences in this directory are responsible for moving the atoms now trapped in the cart magnetic trap down to the 
science cell and cooling using RF evaporation. For historical reasons, we first cool in the cart quadrupole trap, then 
transfer the atoms to a second magnetic quadrupole trap permanently mounted at the science cell referred to as the
"pinch" trap and performing a second stage of RF evaporation in this trap. Also contained in this directory are 
sequences to release the atoms from either magnetic trap, used to image the atoms after each stage for monitoring and 
benchmarking purposes. 

`SciCellLoad` briefly creates a condensed MOT (cMOT), calls `QPCaptureF1` from MidLevelSeq.MOT to load the atoms into
the cart QP trap, and triggers the cart to move down to the science cell. The cart has its own controller that waits 
for a digital trigger from the sequence to execute the next move step.

`CartEvap` calls `SciCellLoad`, then calls an AD9854 DDS RF source (see [Boards](#boards)) for forced RF evaporation. 

`PinchTransfer` calls `CartEvap`, then transfers between magnetic QP traps using two additional magnetic coils (called
AG and Bias) to shim the magnetic field between the two traps. `PinchLoad` adds one additional step, triggering the cart
to move part-way back towards the MOT chamber.

`PinchEvap` is the second stage of RF evaporation, calling `PinchLoad` then using the same AD9854 to evaporate. 

### Dipole Trap
`CrossEvap` is a sequence to load the atoms from the PinchQP trap into a purely optical crossed beam dipole trap, then 
lowers the power of the trap for a final stage of evaporative cooling. After calling `PinchEvap`, the atoms are 
transferred between traps by ramping the dipole laser up high and the pinch current down just below the current needed 
to support against gravity. The dipole beam is then ramped down and the pinch ramped off according to the desired 
evaporation trajectory. The dipole beam is ramped back up a little higher to recompress the atoms for stability. The 
evaporation trajectories are saved as dictionaries which are passed to the instance of `CrossEvap` as `evap_parameters`.
These dictionaries are all saved in MidLevelSeq.EvaporationParameters.py.

### Dipole Release
Dipole Release 

## References
<a id="1">[1]</a> 
N. Kowalski, N. Fredman, J. Zirbel, and B. DeMarco, “Entangleware
sequencer: A control platform for atomic physics experiments,” (2023),
arXiv:2311.09437 [quant-ph].
