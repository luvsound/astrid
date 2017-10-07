import random

from pippi import oscs

def play(params):
    osc = oscs.Osc()

    for _ in range(4):
        freq = random.triangular(220, 440)
        out = osc.play(freq=freq, length=random.randint(4410, 44100 * 3))
        out = out.env('random')
        out = out.pan(random.random())

        yield out * random.triangular(0.75, 1)





