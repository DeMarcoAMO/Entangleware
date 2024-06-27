def null_func(time):
    """default null sequence, that takes 0 time to execute
    :param time: time to execute
    :type time: float
    :rtype float
    :return 0"""
    return 0


# Class to handle absolute and relative timing
class Sequence:
    def __init__(self):
        """Handles the timing of the steps within a sequence/subsequence. Hardware trigger is time 0.
        :param self.start_time: start time of the instance
        :type self.start_time: float
        :param self.current_time: time within the instance, incremented by abs and rel methods
        :type self.current_time: float
        :param self.start_permanent: stores start_time, which gets overwritten in start_local_timing method
        :type self.start_permanent: float """
        self.start_time = 0.0
        self.current_time = 0.0
        self.start_permanent = 0.0

    # decorator to automatically update the values of absolute time and current time in a daughter class
    def _update_time(func):
        """"decorator to automatically update class attributes self.start_time and self.current_time and
        return the elapsed time for methods of daughter classes. Used to pass time from higher to lower level sequences.
        Assumes func takes one time parameter, func(time)"""
        def time_wrapper(self, t):
            self.start_time = t
            self.current_time = t
            self.start_permanent = t
            func(self, t)
            time_elapsed = self.current_time - self.start_time
            return time_elapsed
        time_wrapper.__name__ = func.__name__
        time_wrapper.__doc__ = func.__doc__
        return time_wrapper

    # executes sequence seq at time t_step
    def abs(self, t_step, seq=null_func):
        """Execute seq at time t_step after self.start_time.
        Assumes seq has one parameter, the time at which it should be executed.
        :param t_step: time to execute seq
        :type t_step: float
        :param seq: method or function to be executed
        :type seq: callable
        :rtype: float
        :return: elapsed time of seq"""
        self.current_time = t_step + self.start_time
        step_time = seq(self.current_time)
        self.current_time += step_time
        return step_time

    def rel(self, delay_time, seq=null_func):
        """Execute seq at time delay_time after self.current_time (the time at which the previous step finished)
        Assumes seq has one parameter, the time at which it should be executed.
        :param delay_time: time to wait before executing seq
        :type delay_time: float
        :param seq: method/function or list of methods/functions to be executed
        :type seq: callable or list [callable]
        :rtype: float
        :return: elapsed time of seq (elapsed time of last element if list)"""
        self.current_time += delay_time
        step_time = 0
        if type(seq) is list:
            for step in seq:
                step_time = step(self.current_time)
            self.current_time += step_time
            return step_time
        else:
            step_time = seq(self.current_time)
            self.current_time += step_time
            return step_time

    # TODO: make step_list a list of tuples, rather than a list of lists
    def rel_multiple(self, step_list):
        """ Executes list of tuples containing methods/functions and delay times. step_list is in format
        [(delay_time, seq)]. Increments current time by delay_time and executes seq, then moves to next pair in list.
        [(50*ms, step1), (1ms, step2)] will execute step 1 50ms after previous step and step 2 51ms after previous step.
        :param step_list: nested list of pairs of delay times and methods/functions to be executed
        :type step_list: list [tuple]
        :rtype: float
        :return: elapsed time of final element in step_list
        """
        step_time = 0
        for seq in step_list:
            self.current_time += seq[0]
            step_time = seq[1](self.current_time)
        self.current_time += step_time
        return step_time

    # need to call end_local_timing at end of block of steps
    def start_local_timing(self, delay_time=0):
        """ Creates block of local timing within a sequence. Overwrites start_time wih current_time.
        Allows for absolute timing relative to the start of the block, rather than the start of the sequence.
        Need to call end_local_timing at end of block to restore start_time.
        :param delay_time: delay time before beginning local timing
        :type delay_time: float
        :return: None
        """
        self.current_time += delay_time
        self.start_time = self.current_time

    # ends local timing, reverts start value back to its original value
    def end_local_timing(self):
        """ Ends local timing block. Sets start_time back to its original value, stored in start_permanent.
        :return: None
        """
        self.start_time = self.start_permanent
