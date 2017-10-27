import random
from pippi import oscs, tune

MIDI = 'MPK'
TRIG = -1

def play(ctx):
    ctx.log('play voice')
    ctl1 = ctx.m('MPK')
    ctx.log('MPK CC %s' % ctl1)

    wt = [ random.triangular(-1, 1) for _ in range(random.randint(10, 20)) ]
    osc = oscs.Osc(wt)
    length = random.randint(44100, 44100 * 3)
    out = osc.play(freq=ctx.p.freq * 0.5, length=length)
    #out = out.env('random')
    out = out.env('phasor')
    out = out.pan(random.random())
    out = out * ctx.p.amp

    yield out * random.triangular(0.5, 0.75)


