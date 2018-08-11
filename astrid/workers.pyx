import multiprocessing as mp
import threading
from concurrent.futures import ProcessPoolExecutor
import queue
import time
import os
import jack
import numpy as np

from .io cimport init_voice
from . import midi
from . import orc
from . import names
from . cimport q
from .logger import logger

class RenderProcess(mp.Process):
    cdef public q.Q* buf_q
    def __cinit__(self, 
            q.Q* buf_q, 
            play_q, 
            event_q, 
            load_q, 
            reply_q, 
            bus,
            cwd
        ):

        super(RenderProcess, self).__init__()

        self.instruments = {}
        self.voices = []
        self.buf_q = buf_q
        self.play_q = play_q
        self.event_q = event_q
        self.load_q = load_q
        self.shutdown_flag = bus.shutdown_flag
        self.bus = bus
        self.cwd = cwd
        self.q = queue.Queue()
        self.name = 'astrid-render-process'

    def load_instrument(self, instrument_name, instrument_path):
        instrument = orc.load_instrument(instrument_name, instrument_path, self.bus)
        self.instruments[instrument_name] = instrument
        return instrument

    def get_instrument(self, instrument_name):
        instrument = self.instruments.get(instrument_name, None)         
        if instrument is None:
            instrument_path = os.path.join(self.cwd, names.ORC_DIR, '%s.py' % instrument_name)
            instrument = self.load_instrument(instrument_name, instrument_path, self.bus)
        return instrument

    def run(self):
        def wait_for_shutdown(q, shutdown_flag):
            shutdown_flag.wait()
            q.put((names.SHUTDOWN, None))
            logger.debug('render process put shutdown')

        def wait_for_loads(load_q, q, shutdown_flag):
            while True:
                msg = load_q.get()

                if msg == names.SHUTDOWN:
                    logger.debug('render process shutdown load queue')
                    break

                q.put((names.LOAD_INSTRUMENT, msg))

                # dumb way to try to keep it to one load per process
                # FIXME this probably doesn't always work
                time.sleep(1)

        def wait_for_plays(play_q, q, shutdown_flag):
            while True:
                msg = play_q.get()

                if msg == names.SHUTDOWN:
                    logger.debug('render process shutdown play queue')
                    break

                q.put((names.PLAY_INSTRUMENT, msg))

        load_listener = threading.Thread(name='astrid-load-queue-listener', target=wait_for_loads, args=(self.load_q, self.q, self.shutdown_flag))
        load_listener.start()

        play_listener = threading.Thread(name='astrid-play-queue-listener', target=wait_for_plays, args=(self.play_q, self.q, self.shutdown_flag))
        play_listener.start()

        shutdown_listener = threading.Thread(name='astrid-render-shutdown-listener', target=wait_for_shutdown, args=(self.q, self.shutdown_flag))
        shutdown_listener.start()

        voices = []

        try:
            while True:
                action, cmd = self.q.get()

                if action == names.LOAD_INSTRUMENT:
                    self.load_instrument(*cmd)

                elif action == names.PLAY_INSTRUMENT:
                    instrument_name = cmd[0]
                    params = None
                    if len(cmd) > 1:
                        params = cmd[1]

                    instrument = self.get_instrument(instrument_name)
                    if instrument is None:
                        logger.error('No instrument loaded for %s' % instrument_name)
                        continue

                    # FIXME start voice
                    #logger.error('start voice')
                    voice = threading.Thread(target=init_voice, args=(instrument, params, self.buf_q, self.event_q))
                    voice.start()
                    voices += [ voice ]

                elif action == names.SHUTDOWN:
                    logger.debug('got shutdown')
                    for voice in voices:
                        voice.join()
                    break

        except Exception as e:
            logger.error(e)
     
        load_listener.join()
        play_listener.join()
        shutdown_listener.join()
        logger.debug('render process finished')


