import random
from unittest import TestCase
from astrid import orc
import multiprocessing as mp
import threading

class TestOrc(TestCase):
    def test_load_instrument_from_path(self):
        manager = mp.Manager()
        bus = manager.Namespace()
        bus.stop_all = manager.Event() # voices
        bus.shutdown_flag = manager.Event() # render & analysis processes
        bus.stop_listening = manager.Event() # midi listeners

        instrument_name = 'test'
        instrument = orc.load_instrument(instrument_name, 'orc/tone.py', bus)

        params = None
        ctx = instrument.create_ctx(params)
        generator = instrument.renderer.play(ctx)

        for snd in generator:
            self.assertTrue(len(snd) > 0)

