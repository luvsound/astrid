import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

def make_note(freq, amp, length, mod_range):
    mod = wts.randline(random.randint(10, 100))
    mod_freq = random.triangular(0.3, 3)

    return oscs.Osc(dsp.TRI, 
                    window=dsp.SINE,
                    mod=mod, 
                    mod_freq=mod_freq, 
                    mod_range=mod_range).play(length=length, freq=freq, amp=amp)

def play(ctx):
    freq = ctx.p.freq or 330.0
    length = ctx.p.length or 0.1
    amp = random.triangular(0.1, 0.35)

    mod = random.triangular(0, 0.05)

    out = make_note(freq, amp, length, mod)
    cld = out.cloud(win=dsp.SINE, read_lfo=dsp.RND, 
                    density_lfo=dsp.RND,
                    mindensity=0.1, 
                    maxdensity=2,
                    grainlength_lfo=dsp.RND, 
                    grainlength_lfo_speed=random.triangular(0.5, 10),
                    speed_lfo=dsp.RND,
                    jitter=0,
                    spread=0,
                    minspeed=0.5,
                    maxspeed=2,
                    minlength=10, 
                    maxlength=100
                )
    out = dsp.mix([out, cld])
    out = out.adsr(random.triangular(0.01, 0.02), 0.01, 0.5, 0.1)

    yield out

