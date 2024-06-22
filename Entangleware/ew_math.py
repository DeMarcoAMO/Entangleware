import math


def exponential(val_start, val_end, t_start, t_end, decay_rate):
    # Set start and end values to an integer; The intent is to format as a 16-bit integer for the DAC
    # you may wish to warn the user if their initial or final value is outside the range of the DAC
    q_val_start = int((val_start / 20) * (2 ** 16))
    q_val_end = int((val_end / 20) * (2 ** 16))
    delta = math.exp(decay_rate * (t_end-t_start))
    if delta == 1:
        raise ValueError('decay_rate or the time interval is too small')
    alpha = (q_val_start-q_val_end)/(1-delta)
    offset = q_val_start - alpha
    if (q_val_start > q_val_end+1):
        outputsteps = list(range( q_val_end + 1, q_val_start))
    else:
        outputsteps = list(range(q_val_start, q_val_end + 1))
    timesteps = [None] * len(outputsteps)
    analogsteps = [None] * len(outputsteps)
    for indx in range(len(outputsteps)):
        timesteps[indx] = t_start + math.log((outputsteps[indx]-offset)/alpha)/decay_rate
        analogsteps[indx] = 20 * outputsteps[indx] / (2**16)
    if (q_val_start > q_val_end + 1):
        timesteps.reverse()
        analogsteps.reverse()
    return (timesteps, analogsteps)


if __name__ == "__main__":
    data = exponential(10, -10, 0, 11, -0.3)
    print(data[0])
    print(data[1])
    print(len(data[0]))
