# Sequence Class
README for Sequence class within timing.py module in Base directory.

## Table of contents
* [Example Sequence](#example-sequence)
* [Instance Attributes](#instance-attributes)
* [Methods](#methods)
  * [abs](#abs) 
  * [rel](#rel)
  * [Other Methods](#other-methods)


## Example Sequence
An example top-level sequence might contain the following steps to make a BEC, release it from the trap, and image:
```python
class CrossEvaporation(Sequence):
    def seq(self, seq_time):
        abs(0.00, evaporate)
        rel(100*ms, release)
        rel(time_of_flight, image)
```

`CrossEvaporation` is a daughter class of the parent `Sequence` class. The steps the `seq` method calls can either be
methods of lower level sub-sequences (also daughter-classes of `Sequence`) or functions. Each step is assumed to take a start
time as its only parameter, and return the elapsed time it takes to execute. 

## Instance Attributes
Each instance of the Sequence class has three time attributes, `start_time`, `current_time`, and `start_permanent`. 
`start_time` is of course the starting time for the instance and `current_time` is updated as steps within the method are 
called. `start-permanent` is used if the `start-time` gets overwritten (see local absolute timing in [Other Methods](#other-methods))

In the [example](#example-sequence) top level sequence above, if `seq` is executed at t=0.00, the `evaporate` sub-sequence will be called at t=0.00 and receives that 
as its `start_time` and initial `current_time`. If `evaporate` takes 100 seconds, it will return that as its elapsed 
time, and `current_time` for `MakeBEC` will be 100 seconds. `release` will occur 100*ms later. The `start_time` and 
initial `current_time` for the `release` sub-sequence are t=100.10. `current_time` for `MakeBEC` is then incremented by 
the elapsed time for release and the variable `time_of_flight`, and that new `current_time` passed to image as its 
`start_time` and initial `current_time`. 

In this fashion the time is passed down through the hierarchy of sequences and sub-sequences. Since each sub-sequence 
gets the appropriate `start_time` but then handles its `current_time` independently, sub-sequences can overlap in time 
without requiring additional management. 

## Methods

The two primary methods of the Sequence class are `abs`, used for absolute timing steps, and `rel`, used for relative
timing steps. 
```python
abs(t_step, seq=null_func)
rel(delay_time, seq=null_func)
```
Both take as parameters a time and a step `seq` to be executed. The default step is a null function that just returns 
0 elapsed time.  


Each step (whether class method or function) is assumed to have the format:
```python
def step(time):
    ...
    return elapsed_time
```
where it takes as its only parameter the time at which it is to be executed and returns the time elapsed while it
executes.

### abs
`abs` executes `seq` at time `t_step + start_time` (i.e., `t_step` after the sequence begins). It ignores whatever may 
have occurred before `seq`. 

### rel
`seq` in the `rel` method can be either a single step or a list of steps. `rel` executes the step(s) `seq` at time
`delay_time + current_time` (i.e., `t_delay` after the previous step ends). It depends on whatever step is called 
immediately previous to it. 

If `seq` is a list, all steps in the list are executed at the same time (`delay_time + current_time`). However, only the
elapsed time of the final step in the list is used to update `current_time`. E.g., if `rel(10*ms, [step1, step2, step3])`
is called, `current_time` will be the end time of `step3`.

### other methods
#### rel_multiple
`rel_multiple` is used when you have multiple steps and delay times, but all referencing the end of the same previous 
step. For instance, if you want `step1` to occur 10ms after the previous step (`step0`) and `step2` to occur 15ms after
the same `step0` you could call `rel_multiple([[10ms, step1],[5ms, step2]])`. Delay times are additive, meaning each 
delay time is added to `current_time`, not the end time of `step0`.

#### local timing
Two methods, `start_local_timing` and `end_local_timing`, allow for local absolute timing within a sequence. 
`start_local_timing` overwrites `start_time` with `current_time` (after factoring in `delay_time`), meaning `abs` steps
will reference this new "`start_time`". The original `start_time` is still stored as the `start_permanent` class 
parameter. `end_local_timing` sets `start_time` back to its original value. 