import random

from pippi import oscs

def play(params):
    osc = oscs.Osc()

    for _ in range(4):
        osc.freq = random.triangular(220, 440)
        out = osc.play(random.randint(44100, 44100 * 4))
        out = out.env('random')

        out = out.pan(random.random())

        yield out * random.triangular(0.75, 1)





