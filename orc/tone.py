import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

MIDI = 'MPK'
#TRIG = -1
loop = True
SOUNDS = ['tests/sounds/vibes.wav']

"""
def onsets(ctx):
    #return [ i * 3 for i in wts.wavetable(dsp.SINE, random.randint(4, 32)) ]
    return [ 0, 1 ]
"""

def make_note(freq, amp, length):
    numtables = random.randint(1, random.randint(3, 12))
    lfo = wts.randline(random.randint(10, 100))
    lfo_freq = random.triangular(0.3, 30)

    mod = wts.randline(random.randint(10, 100))
    mod_freq = random.triangular(0.3, 3)
    mod_range = random.triangular(0, 3)
    pulsewidth = random.random()

    wavetables = []
    for _ in range(numtables):
        if random.random() > 0.5:
            wavetables += [ random.choice([dsp.SINE, dsp.SQUARE, dsp.TRI, dsp.SAW]) ]
        else:
            wavetables += [ wts.randline(random.randint(3, 300)) ]

    return oscs.Osc(stack=wavetables, window=dsp.SINE, mod=mod, lfo=lfo, pulsewidth=pulsewidth, mod_freq=mod_freq, mod_range=mod_range, lfo_freq=lfo_freq).play(length=length, freq=freq, amp=amp)

def play(ctx):
    mpk = ctx.m('MPK')
    freqs = tune.fromdegrees([1,2,3,5,6,8,9], octave=random.randint(1, 5), root='c')
    numvoices = random.randint(1, 3)
    length = random.triangular(0.5, 7)

    for _ in range(numvoices):
        freq = ctx.p.freq or random.choice(freqs)
        amp = mpk.cc2 or ctx.p.amp or random.triangular(0.1, 0.5)

        out = make_note(freq, amp, length)
        out = out.adsr(0.005, 0.01, 0.35, 0.1)
        out = out.env(dsp.RSAW)
        out = out.pan(random.random())
        v = random.choice(ctx.sounds)
        v = v.rcut(random.triangular(length/10, length)).pan(random.random()) * random.random()
        out.dub(v, 0)

        yield out


