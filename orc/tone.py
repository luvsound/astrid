import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

MIDI = 'MPK'
TRIG = -1

def play(ctx):
    ctx.log('play voice')
    mpk = ctx.m('MPK')
    ctx.log('MPK CC1 %s' % mpk.cc1)

    length = random.triangular(0.4, 1)
    freq = ctx.p.freq or random.triangular(200, 330)
    #freqs = tune.fromdegrees([1,3,5,9], octave=random.randint(2,5))
    #freq = random.triangular(300, 600)
    #freq = random.choice(freqs)
    #amp = random.triangular(0.1, 0.25) * 0.2
    amp = ctx.p.amp or 0.25
    pulsewidth = mpk.cc1 or 1

    #lfo_freq = random.triangular(0.001, 10)
    #numtables = random.randint(1, random.randint(3, 12))
    #lfo = random.choice([dsp.SINE, dsp.RSAW, dsp.TRI, dsp.PHASOR])
    #wavetables = [ random.choice([dsp.SINE, dsp.SQUARE, dsp.TRI, dsp.SAW]) for _ in range(numtables) ]
    osc = oscs.Osc(dsp.TRI, pulsewidth=pulsewidth)
    out = osc.play(length=length, freq=freq, amp=amp)
    out = out.adsr(0.005, 0.01, 0.35, 0.1)
    out = out.pan(random.random())
    #out.write('listeny.wav')

    ctx.log('PLAYED %s at %s' % (freq, amp))

    yield out


