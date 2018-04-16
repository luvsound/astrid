import random
from unittest import TestCase
from astrid.mixer import AstridMixer, StreamContext, StreamContextView
from astrid import orc
import multiprocessing as mp
import threading
from pippi import dsp, interpolation, grains


class TestMixer(TestCase):
    def test_play_sample(self):
        block_size = 64
        channels = 2
        samplerate = 44100

        #ctx = StreamContext()
        #ctx_ptr = ctx.get_pointer()
        mixer = AstridMixer(block_size, channels, samplerate)

        snd = dsp.read('tests/sounds/vibes.wav')
        snd = snd.cut(1).env(dsp.SINE)

        mixer.add(snd)
        mixer.sleep(snd.dur*1000.0)

        mixer.shutdown()

    def test_play_clouds(self):
        def makecloud(snd):
            return grains.GrainCloud(snd * 0.125, 
                        win=dsp.HANN, 
                        read_lfo=dsp.PHASOR, 
                        speed_lfo_wt=interpolation.linear([ random.triangular(0, 0.05) for _ in range(random.randint(10, 1000)) ], 4096), 
                        density_lfo_wt=interpolation.linear([ random.random() for _ in range(random.randint(10, 1000)) ], 4096), 
                        grainlength_lfo_wt=interpolation.linear([ random.random() for _ in range(random.randint(10, 500)) ], 4096), 
                        minspeed=0.25, 
                        maxspeed=random.triangular(1, 1.5),
                        density=random.triangular(0.75, 2),
                        minlength=1, 
                        maxlength=random.triangular(60, 200),
                        spread=random.random(),
                        jitter=random.triangular(0, 0.1),
                    ).play(snd.dur * random.triangular(3, 4))

        block_size = 64
        channels = 2
        samplerate = 44100

        #ctx = StreamContext()
        #ctx_ptr = ctx.get_pointer()
        mixer = AstridMixer(block_size, channels, samplerate)

        mixer.sleep(2000.0)
        snd = mixer.read(44100)

        #ctx_view = StreamContextView(ctx_ptr)
        #snd = ctx_view.read(44100, 0)

        for i in range(10):
            density = random.triangular(0.1, 1)

            out = makecloud(snd) * 5
            #out.write('cldhm%s.wav' % i)

            mixer.add(out)

        mixer.sleep(5000.0)

        mixer.shutdown()



    def test_play_note_sequence(self):
        block_size = 64
        channels = 2
        samplerate = 44100

        #ctx = StreamContext()
        #ctx_ptr = ctx.get_pointer()
        mixer = AstridMixer(block_size, channels, samplerate)

        instrument_name = 'test'
        instrument = orc.load_instrument(instrument_name, 'orc/tone.py')

        ctx = orc.EventContext(
                    instrument_name=instrument_name, 
                    running=threading.Event(),
                    stop_all=threading.Event(), 
                    stop_me=threading.Event(),
                    bus=mp.Manager().Namespace(), 
                )

        numnotes = 6

        for _ in range(numnotes):
            generator = instrument.play(ctx)

            for snd in generator:
                self.assertTrue(len(snd) > 0)
                mixer.add(snd)
            mixer.sleep(random.randint(0, 100))

        mixer.sleep(1000)
        generator = instrument.play(ctx)

        for snd in generator:
            self.assertTrue(len(snd) > 0)
            mixer.add(snd)

        mixer.sleep(1000)

        mixer.shutdown()


    def test_play_input_recording(self):
        block_size = 64
        channels = 2
        samplerate = 44100
        lengthms = 2000

        #ctx = StreamContext()
        #ctx_ptr = ctx.get_pointer()
        mixer = AstridMixer(block_size, channels, samplerate)

        # fill up the ringbuffer for a while
        mixer.sleep(lengthms)

        # get the recording from the mixer
        #ctx_view = StreamContextView(ctx_ptr)
        #snd = ctx_view.read(int(lengthms * 0.001 * samplerate), 0)
        snd = mixer.read(int(lengthms * 0.001 * samplerate))
        snd.write('inp.wav')

        # play the sound
        mixer.add(snd)
        mixer.sleep(lengthms * 2)

        mixer.shutdown()

