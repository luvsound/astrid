import random
from pippi import oscs, tune

MIDI = 'MPK'
TRIG = -1

def play(ctx):
    ctx.log('play voice')
    freqs = tune.chord('i9')

    osc = oscs.Osc('random')
    #freq = random.choice(freqs) * 2**random.randint(0, 4)
    out = osc.play(freq=ctx.p.freq * 0.5, length=44100//random.choice([4, 8]))
    out = out.env('random')
    out = out.env('phasor')
    out = out.pan(random.random())
    out = out * ctx.p.amp

    yield out * random.triangular(0.25, 0.75)


