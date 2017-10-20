import random
from pippi import oscs, tune

def play(ctx):
    ctx.log('play voice')
    freqs = tune.chord('i9')

    for _ in range(10):
        osc = oscs.Osc('random')
        freq = random.choice(freqs) * 2**random.randint(0, 4)
        out = osc.play(freq=freq * 0.5, length=44100//random.choice([4, 8]))
        out = out.env('random')
        out = out.env('phasor')
        out = out.pan(random.random())

        yield out * random.triangular(0.25, 0.75)


