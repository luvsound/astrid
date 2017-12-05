import random
from unittest import TestCase
from astrid import orc
import multiprocessing as mp
import threading

class TestOrc(TestCase):
    def test_load_instrument_from_path(self):
        instrument_name = 'test'
        instrument = orc.load_instrument(instrument_name, 'orc/tone.py')

        ctx = orc.EventContext(
                    params=None, 
                    instrument_name=instrument_name, 
                    running=threading.Event(),
                    stop_all=threading.Event(), 
                    stop_me=threading.Event(),
                    bus=mp.Manager().Namespace(), 
                )

        generator = instrument.play(ctx)

        for snd in generator:
            self.assertTrue(len(snd) > 0)

