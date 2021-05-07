from pippi import dsp, noise

LOOP = True

def play(ctx):
    length = dsp.rand(6, 12)
    highfreq = dsp.rand(10000, 20000)
    lowfreq = highfreq - dsp.rand(1000, 5000)
    out = noise.bln('sine', length, lowfreq, highfreq)
    out = out.env('hann') * dsp.rand(0.01, 0.04)
    out = out.pan('rnd')

    yield out
