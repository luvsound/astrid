import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

def make_note(freq, amp, length):
    mod = wts.randline(random.randint(10, 100))
    mod_freq = random.triangular(0.3, 3)
    mod_range = random.triangular(0, 0.03)

    return oscs.Osc(dsp.SINE, 
                    mod=mod, 
                    mod_freq=mod_freq, 
                    mod_range=mod_range).play(length=length, freq=freq, amp=amp)

def play(ctx):
    freq = ctx.p.freq or 330.0
    length = ctx.p.length or 0.1
    amp = 0.3

    out = make_note(freq, amp, length)
    out = out.adsr(0.01, 0.01, 0.5, 0.1)
    out = out.pan(random.random())

    yield out

