from pippi import oscs, tune, dsp

def make_note(freq, amp, length):
    shape = dsp.randline(dsp.randint(10, 100))
    return oscs.Tukey().play(length, freq, shape) * amp

def play(ctx):
    freq = ctx.p.freq or 330.0
    length = ctx.p.length or 0.1
    amp = dsp.rand(0.1, 0.35)

    out = make_note(freq, amp, length)
    cld = out.cloud(
            length, 
            window='sine', 
            position='rnd', 
            grid=dsp.win('rnd', 0.1, 2),
            grainlength=dsp.win('rnd', dsp.MS*10, dsp.MS*100),
            speed=dsp.win('rnd', 0.5, 2),
    )

    out = dsp.mix([out, cld])
    out = out.adsr(dsp.rand(0.01, 0.02), 0.01, 0.5, 0.1)

    yield out

