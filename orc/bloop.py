import random
from pippi import oscs, tune, dsp, interpolation, grains
from pippi import wavetables as wts

loop = True

def makecloud(snd):
    return grains.GrainCloud(snd, 
                win=dsp.HANN, 
                read_lfo=dsp.PHASOR, 
                speed_lfo_wt=interpolation.linear([ random.triangular(0, 0.05) for _ in range(random.randint(10, 1000)) ], 4096), 
                density_lfo_wt=interpolation.linear([ random.random() for _ in range(random.randint(10, 1000)) ], 4096), 
                grainlength_lfo_wt=interpolation.linear([ random.random() for _ in range(random.randint(10, 500)) ], 4096), 
                minspeed=0.99, 
                maxspeed=random.triangular(1, 1.1),
                density=random.triangular(0.75, 2),
                minlength=1, 
                maxlength=random.triangular(60, 100),
                spread=random.random(),
                jitter=random.triangular(0, 0.1),
            ).play(snd.dur * random.triangular(3, 4))

def play(ctx):
    length = random.triangular(0.1, 0.2)
    freq = ctx.bus.input_pitch
    amp = ctx.bus.input_amp * 2
    pulsewidth = 1

    osc = oscs.Osc(dsp.TRI, pulsewidth=pulsewidth)
    out = osc.play(length=length, freq=freq, amp=amp)
    out = out.adsr(0.005, 0.01, 0.35, 0.05)
    out = out.pan(random.random())
    if random.random() > 0.15:
        out = makecloud(out)

    yield out


