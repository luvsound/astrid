import random
from pippi import oscs, tune

def play(ctx):
    osc = oscs.Osc('tri')

    while True:
        ctx.log('play bus %s' % ctx.bus)
        if hasattr(ctx.bus, 'input_pitch'):
            hz = ctx.bus.input_pitch
        else:
            hz = random.random() * 3 + 200
        ctx.log('play TRI %s' % hz)
        out = osc.play(freq=hz, length=64)
        out = out * 0.25
        yield out


