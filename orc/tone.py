import random

from pippi import oscs, tune

def play(ctx):
    osc = oscs.Osc()
    freqs = tune.chord('i9')

    for _ in range(3):
        freq = random.choice(freqs) * 2**random.randint(0, 8)
        out = osc.play(freq=freq, length=random.randint(4410, 50000))
        out = out.env('random')
        out = out.env('phasor')
        out = out.pan(random.random())

        yield out * random.triangular(0.25, 0.35)

def before(ctx):
    ctx.log('before play')

def done(ctx):
    ctx.log('done playing')


