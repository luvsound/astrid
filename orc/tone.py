import random
from pippi import oscs, tune, dsp

MIDI = 'MPK'
TRIG = -1

def play(ctx):
    ctx.log('play voice')
    mpk = ctx.m('MPK')
    ctx.log('MPK CC1 %s' % mpk.cc1)

    length = random.triangular(0.4, 1)
    freq = ctx.p.freq or random.triangular(200, 330)
    freqs = tune.fromdegrees([1,3,5,9], octave=6)
    #freq = random.triangular(300, 600)
    freq = random.choice(freqs)
    amp = random.triangular(0.125, 0.15)
    #amp = ctx.p.amp or 0.25

    osc = oscs.Osc(wavetable=dsp.SINE)
    out = osc.play(length=length, freq=freq, amp=amp)
    out = out.env(dsp.RSAW)
    out = out.pan(random.random())
    #out.write('listeny.wav')

    ctx.log('PLAYED %s at %s' % (freq, amp))

    yield out


