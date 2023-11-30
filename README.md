# Entangleware 
The sequencer and control platform for the DeMarco Lab at the University of Illinois at Urbana-Champaign. See our paper [[1]](#1) for a complete overview. 

Experimental quantum physics and computing platforms rely on sophisticated control and timing systems that must be deterministic. For example, a sequence to create a Bose-Einstein Condensate in our lab invovles 46,812 analog and digital transitions over 100 seconds with 20ns timing precision and nanosecond timing drift. To achieve this, we utilize industry-standard National Instruments (NI) hardware. A master 10MHz clock conditioned to the Global Positioning Satellite constellation is used for timing stability. The hardware is managed by an intermediate program, the Entangleware Control Application (ECA) created by our partner [Entangleware](<https://entangleware.com/>). 

The experiment is run in a "shot" mode, where a single run of the experiment produces data and parameters are changed between runs. The shot begins when the ECA triggers the hardware. Everything after the trigger is deterministically timed until the shot finishes. The fundamental hardware outputs are analog and digital transitions that occur at precise times within the experimental run. We call a set of these transitions and times a "sequence". This project is used to generate the necessary list of transitions and times and compile them into a bitstream that is sent to the ECA via a standard TCP/UDP network interface. 

We divide the generation of these transitions into a hierarchy of sub-sequences. This sub-sequences describe logically separate steps, possibly interleaved in time, with adjustable relative timing between steps. 
Lower level sequences (found in Base) reflect the underlying hardware (e.g. sequences for magnetic coils), while mid-level sequences (MidLevelSeq) reflect the stage of the experiment (e.g. evaporative cooling).

Included is a library of APIs for useful peripheral hardware, such as Direct Digital Synthesis (DDS) radiofrequency sources and digital-to-analog converters (DACs). 

## Table of contents
* [Project Organization](#project-organization)
* [Entangleware](#entangleware)
* [Timing](#timing)
  
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
* MidLevel
    * MOT.py
    * MagneticTraps.py
    * DipoleTrap.py
    * DipoleRelease.py
    * EvaporationParameters.py
* TopLevel
* TestSequences
    * SequencerExample.py
    * testMidLevel.py
    * testDipole.py
 
The Entangleware folder contains everything necessary for generating and filling the bitstream and network communication with the ECA. 

Base contains the Sequence class for timing (timing.py), functions for analog and digital outputs (outputwrappers.py), and all sequences that directly control hardware (e.g., lasers and magnetic coils). The peripheral board libary is found in boards.py.

MidLevel contains sequences for different stages of an experimental run: transerring the MOT to a magnetic trap, RF evaporation, and optical evaporation. All optical evaporation parameters are stored as dictionaries in EvaporationParameters.py.

TopLevel contains sequences for data taking.

TestSequences contains both hardware tests (e.g. turn a magnetic coil on/off) and stage tests with the atoms (e.g. do some level of RF evaporation and image).

## Entangleware
Network communication with the ECA is handled in this folder, as well as the two fundamental outputs found in Entangleware.ew_link.py:
```python
set_digital_state(seqtime, connector, channel_mask, output_enable_state, output_state)
set_analog_state(seq_time, board, channel, value)
```

`channel_mask`, `output_enable_state`, and `output_state` are all all bit registers, e.g. to address the 4th channel on the connector the `channel_mask` would be `1<<4`. ``output_enable_state`` is always set to `1` for all channels in our system, but allows for lines to become inputs rather than outputs for in-loop decision making. To aid legibility, two wrapper functions are found in Base.outputwrappers.py:
```python
digital_out(seq_time, connector, channel, state)
analog_out(seq_time, connector, channel, value)
```
Here connector and channel are simply integers for the desired connector (there are 4 VHDCI output connectors on the FPGA and 2 analog source cards) and channel number (0-31 on each FPGA connector and 0-7 on each analog source card). `State` is binary 0 or 1, value is a float between -10 and 10 (the output voltage range of the PCI-6733 analog source card). 

## Base
### Timing
We use two types of timing, absolute and relative. Absolute timing occurs at some time after the hardware trigger. Relative timing occurs after the previous step in the sequence finishes.  The `Sequence` class in Base.timing.py is used to keep track of and increment time within the sequence (where time is a float in units of seconds). All sequences and sub-sequences are daughter classes of this `Sequence` class.

The class has two attributes, `start_time` and `current_time`. `start_time` is when the sequence or sub-sequence begins in units of seconds, relative to the hardware trigger. `current_time` is incremented as the sequence progresses. 

### Output Wrappers
In addition to the `digital_out` and `analog_out` mentioned above (see [Entangleware](#entangleware)), output wrappers also contains two classes for "continuous" analog ramps, AnalogRamp and AnalogOscillate. The analog source cards have a 16 bit register and output range -10V to 10V, meaning each bit of the register corresponds to $20/2^{16}\approx$ 0.3mV. To minimize transitions the class calculates when each succesive bit flip should occur for the desired ramp trajectory and calls for the analog transition at the appropriate time. Currently supports linear, exponential, and sigmoidal ramps and sine wave oscillations. 

### Boards
APIs for peripheral hardware: AD9959, AD9854, and AD9910 DDSs and AD5372 DAC. Uses 4 digital lines per board for serial communication with eval board (I/O, Clock, Update, and Reset). Wraps serial communication, providing simple commands to output frequencies or voltages at deterministic times within the sequence.

## References
<a id="1">[1]</a> 
N. Kowalski, N. Fredman, J. Zirbel, and B. DeMarco, “Entangleware
sequencer: A control platform for atomic physics experiments,” (2023),
arXiv:2311.09437 [quant-ph].
