import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

loop = True

def play(ctx):
    length = random.triangular(0.1, 0.2)
    freq = ctx.bus.input_pitch * 4
    amp = ctx.bus.input_amp * 4
    pulsewidth = 1

    osc = oscs.Osc(dsp.TRI, pulsewidth=pulsewidth)
    out = osc.play(length=length, freq=freq, amp=amp)
    out = out.adsr(0.005, 0.01, 0.35, 0.05)
    out = out.pan(random.random())

    yield out


