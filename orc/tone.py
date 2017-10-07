import random

from pippi import oscs

def play(ctx):
    ctx.log('init play')
    osc = oscs.Osc()

    for _ in range(4):
        freq = random.triangular(220, 440)
        out = osc.play(freq=freq, length=random.randint(4410, 44100 * 3))
        out = out.env('random')
        out = out.pan(random.random())

        ctx.log('push sound to stream')
        yield out * random.triangular(0.75, 1)

def pre(ctx):
    ctx.log('before play')

def done(ctx):
    ctx.log('done playing')


