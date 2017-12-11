import random
from unittest import TestCase
from astrid.mixer import AstridMixer
from astrid import orc
import multiprocessing as mp
import threading
from pippi import dsp


class TestMixer(TestCase):
    def test_play_sample(self):
        block_size = 64
        channels = 2
        samplerate = 44100

        mixer = AstridMixer(block_size, channels, samplerate)

        snd = dsp.read('tests/sounds/vibes.wav')

        mixer.add(snd)
        mixer.sleep(snd.dur*1000.0)

        mixer.shutdown()


    def test_play_note_sequence(self):
        block_size = 64
        channels = 2
        samplerate = 44100

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

        mixer = AstridMixer(block_size, channels, samplerate)

        # fill up the ringbuffer for a while
        mixer.sleep(lengthms)

        # get the recording from the mixer
        snd = mixer.read(int(lengthms * 0.001 * samplerate))
        #snd.write('inp.wav')

        # play the sound
        mixer.add(snd)
        mixer.sleep(lengthms * 2)

        mixer.shutdown()

