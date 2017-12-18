import random
import glob
from pippi import dsp, oscs, tune, rhythm
from astrid import player

BPM = 130
MIDI = 'MPK'
TRIG = -1

loop = True

def snarep(ctx):
    return rhythm.pattern('..x.', meter='4/4', beats=4, offset=0, bpm=BPM)

def kickp(ctx):
    return rhythm.pattern('x...', meter='4/4', beats=4, offset=0, bpm=BPM)

def hatp(ctx):
    return rhythm.pattern('xxxx', meter='4/4', beats=4, offset=0, swing=0, bpm=BPM)

def before(ctx):
    hatfs = glob.glob('/home/hecanjog/code/songs/sounds/drums/hats*.wav')
    kickfs = glob.glob('/home/hecanjog/code/songs/sounds/drums/kick*.wav')
    snarefs = glob.glob('/home/hecanjog/code/songs/sounds/drums/snarecrisp*.wav')

    return {
        'hats': hatfs, 
        'kicks': kickfs, 
        'snares': snarefs
    }

@player.init(onsets=hatp)
def hats(ctx):
    hat = random.choice(ctx.before.get('hats'))
    hat = dsp.read(hat)
    yield hat * random.triangular(0.25, 0.75)

@player.init(onsets=kickp)
def kicks(ctx):
    kick = random.choice(ctx.before.get('kicks'))
    kick = dsp.read(kick)
    yield kick * random.triangular(0.65, 0.75)

@player.init(onsets=snarep)
def snares(ctx):
    snare = random.choice(ctx.before.get('snares'))
    snare = dsp.read(snare)
    snare = snare * random.triangular(0.75, 0.85)
    snare = snare.speed(random.triangular(1.2, 1.4))

    yield snare
