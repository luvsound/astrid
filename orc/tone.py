import random
from pippi import oscs, tune, dsp
from pippi import wavetables as wts

MIDI = 'MPK'
#TRIG = -1
loop = True

def onsets(ctx):
    return [ i * 0.2 for i in wts.wavetable(dsp.SINE, random.randint(4, 32)) ]

def make_note(freq, lfo_freq, amp, length):
    length = random.triangular(length, length * 2)
    numtables = random.randint(1, random.randint(3, 12))
    lfo = random.choice([dsp.SINE, dsp.RSAW, dsp.TRI, dsp.PHASOR])
    wavetables = [ random.choice([dsp.SINE, dsp.SQUARE, dsp.TRI, dsp.SAW]) for _ in range(numtables) ]

    osc = oscs.Osc(wavetables, lfo=lfo)

    #freq = freq * random.choice([0.5, 1])
    note = osc.play(length=length, freq=freq, amp=amp, mod_freq=lfo_freq)
    #note = note.env(dsp.RND).env(dsp.PHASOR).pan(random.random())

    return note


def play(ctx):
    ctx.log('play voice')
    mpk = ctx.m('MPK')
    ctx.log('MPK CC1 %s' % mpk.cc1)

    length = random.triangular(0.01, 0.5)
    #freq = ctx.p.freq or random.triangular(200, 330)
    freqs = tune.fromdegrees([1,3,5,6], octave=random.randint(2,5), root='c')
    #freq = random.triangular(300, 600)
    freq = random.choice(freqs)
    ctx.log(freq)
    #amp = random.triangular(0.1, 0.25) * 0.2
    #amp = ctx.p.amp * 0.125
    amp = mpk.cc2 or 0.15
    pulsewidth = mpk.cc1 or random.random()
    lfo_freq = random.triangular(0.001, 330)
    lfo_freq = (mpk.cc3 or 1) * 100

    out = make_note(freq, lfo_freq, amp, length)
    out = out.adsr(0.005, 0.01, 0.35, 0.1)
    out = out.pan(random.random())
    #out.write('listeny.wav')

    ctx.log('PLAYED %s at %s' % (freq, amp))

    yield out


