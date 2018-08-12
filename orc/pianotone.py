import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

def make_note(freq, amp, length):
    mod = wts.randline(random.randint(10, 100))
    mod_freq = random.triangular(0.3, 3)
    mod_range = random.triangular(0, 0.3)

    return oscs.Osc(dsp.RND, 
                    window=dsp.SINE,
                    mod=mod, 
                    mod_freq=mod_freq, 
                    mod_range=mod_range).play(length=length, freq=freq, amp=amp)

def play(ctx):
    freq = ctx.p.freq or 330.0
    length = ctx.p.length or 0.1
    amp = random.triangular(0.1, 0.35)

    out = make_note(freq, amp, length)
    out = out.adsr(random.triangular(0.01, 0.1), 0.01, 0.5, 0.1)
    out = out.pan(random.random())

    yield out

