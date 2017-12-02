import random
from pippi import oscs, tune

#MIDI = 'MPK'
#TRIG = -1

def play(ctx):
    ctx.log('play voice')
    #ctl1 = ctx.m('MPK')
    #ctx.log('MPK CC %s' % ctl1)

    length = random.randint(44100, 44100 * 3)
    freq = random.triangular(200, 330)
    amp = 0.25
    #freq = ctx.p.freq
    #amp = ctx.p.amp

    osc = oscs.Osc('tri')
    out = osc.play(length=length, freq=freq, amp=amp)
    out = out.env('phasor')

    #ctx.log('PLAYED %s' % ctl1)

    yield out


