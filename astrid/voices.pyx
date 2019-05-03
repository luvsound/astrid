import multiprocessing as mp
import threading
import queue
import os
import time

import redis

from .io cimport init_voice
from .logger import logger
from . import names
from . import orc

class VoiceHandler(mp.Process):
    def __init__(self, play_q, load_q, buf_q, shutdown, cwd):
        super().__init__()
        self.instruments = {}
        self.buf_q = buf_q
        self.play_q = play_q
        self.load_q = load_q
        self.shutdown = shutdown
        self.cwd = cwd
        self.q = queue.Queue()

    def load_instrument(self, instrument_name, instrument_path, shutdown):
        instrument = orc.load_instrument(instrument_name, instrument_path, shutdown)
        self.instruments[instrument_name] = instrument
        return instrument

    def get_instrument(self, instrument_name, shutdown):
        instrument = self.instruments.get(instrument_name, None)         
        if instrument is None:
            instrument_path = os.path.join(self.cwd, names.ORC_DIR, '%s.py' % instrument_name)
            instrument = self.load_instrument(instrument_name, instrument_path, shutdown)
        return instrument

    def wait_for_shutdown(self, q, shutdown):
        shutdown.wait()
        q.put((names.SHUTDOWN, None))
        logger.debug('render process put shutdown')

    def wait_for_loads(self, q, load_q):
        r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
        pubsub = r.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(names.LOAD_INSTRUMENT, names.SHUTDOWN)
        for msg in pubsub.listen():
            c = int(msg['channel'] or 0)
            if not msg['type'] == 'message':
                continue

            instrument_name = msg['data']
            logger.info('LOAD MSG %s' % instrument_name)

            if c == names.LOAD_INSTRUMENT:
                q.put((names.LOAD_INSTRUMENT, (instrument_name, None)))

            elif c == names.SHUTDOWN:
                logger.debug('render process shutdown load queue')
                break

    def wait_for_plays(self, q, play_q):
        while True:
            msg = play_q.get()
            if msg == names.SHUTDOWN:
                logger.debug('render process shutdown play queue')
                break

            q.put((names.PLAY_INSTRUMENT, msg))

    def run(self):
        load_listener = threading.Thread(target=self.wait_for_loads, args=(self.q, self.load_q))
        load_listener.start()

        play_listener = threading.Thread(target=self.wait_for_plays, args=(self.q, self.play_q))
        play_listener.start()

        shutdown_listener = threading.Thread(target=self.wait_for_shutdown, args=(self.q, self.shutdown))
        shutdown_listener.start()

        voices = []

        try:
            while True:
                action, cmd = self.q.get()

                if action == names.LOAD_INSTRUMENT:
                    instrument_name, instrument_path = cmd
                    self.load_instrument(instrument_name, instrument_path, self.shutdown)

                elif action == names.PLAY_INSTRUMENT:
                    instrument_name = cmd[0]
                    params = None
                    if len(cmd) > 1:
                        logger.info('CMD params: %s' % cmd)
                        params = {}
                        for c in cmd[1:]:
                            if isinstance(c, dict):
                                params.update(c)
                            else:
                                k, v = tuple(c.split(':'))
                                params[k] = v

                    instrument = self.get_instrument(instrument_name, self.shutdown)
                    if instrument is None:
                        logger.error('No instrument loaded for %s' % instrument_name)
                        continue

                    voice = threading.Thread(target=init_voice, args=(instrument, params, self.buf_q))
                    voice.start()
                    voices += [ voice ]

                elif action == names.SHUTDOWN:
                    logger.debug('voice %s got shutdown' % self.pid)
                    for voice in voices:
                        voice.join()
                    break

        except Exception as e:
            logger.error(e)

        load_listener.join()
        play_listener.join()
        shutdown_listener.join()
        logger.debug('voice %s cleaned up' % self.pid)


