import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

#MIDI = 'MPK'
#MIDI = 'VI49'
#TRIG = -1
#loop = True
SOUNDS = ['tests/sounds/vibes.wav']

"""
def onsets(ctx):
    #return [ i * 3 for i in wts.wavetable(dsp.SINE, random.randint(4, 32)) ]
    return [ 0, 1 ]
"""

def make_note(freq, amp, length):
    numtables = random.randint(1, random.randint(3, 12))
    lfo = dsp.randline(random.randint(10, 100))
    lfo_freq = random.triangular(0.3, 30)

    mod = dsp.randline(random.randint(10, 100))
    mod_freq = random.triangular(0.3, 3)
    mod_range = random.triangular(0, 0.03)
    pulsewidth = random.random()

    wavetables = []
    for _ in range(numtables):
        if random.random() > 0.5:
            wavetables += [ random.choice(['sine', 'square', 'tri', 'saw']) ]
        else:
            wavetables += [ dsp.randline(random.randint(3, 300)) ]

    return oscs.Pulsar2d(wavetables, windows=['sine'], pulsewidth=pulsewidth, freq=freq, amp=amp).play(length)

def play(ctx):
    mpk = ctx.m('MPK')
    freqs = tune.fromdegrees([1,2,3,5,6,8,9], octave=random.randint(1, 5), root='c')
    numvoices = random.randint(1, 3)
    length = random.triangular(0.15, 3.5)

    for _ in range(numvoices):
        #freq = ctx.p.freq or random.choice(freqs)
        freq = 330
        #amp = mpk.cc2 or ctx.p.amp or random.triangular(0.5, 0.85)
        amp = 0.2

        out = make_note(freq, amp, length)
        out = out.adsr(random.triangular(0.005, 0.5), 0.01, 0.35, random.triangular(0.1, 0.5))
        out = out.env('rsaw')
        out = out.pan(random.random())
        #v = random.choice(ctx.sounds)
        #v = v.rcut(random.triangular(length/10, length)).pan(random.random()) * random.random()
        #out.dub(out, 0)

        yield out


