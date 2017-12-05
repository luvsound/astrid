import random
from unittest import TestCase
from astrid.mixer import AstridMixer
from astrid import orc
import multiprocessing as mp
import threading


class TestOrc(TestCase):
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
