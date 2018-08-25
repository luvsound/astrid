import random
from pippi import dsp, oscs

def play(ctx):
    osc = oscs.Osc(dsp.RND)
    yield osc.play(random.triangular(0.5, 2), freq=random.triangular(60, 800)).adsr(0.03, 0.1, 0.5, 0.1) * 0.5
