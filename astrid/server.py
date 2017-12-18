import asyncio
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import collections
import multiprocessing as mp
import os
import time
import threading
import random
import queue

import msgpack
from service import Service
import numpy as np
import zmq

from . import analysis
from . import midi
from . import io
from . import orc
from . import workers
from . import names
from .mixer import StreamContext, StreamContextView
from .logger import logger

BANNER = """
 █████╗ ███████╗████████╗██████╗ ██╗██████╗ 
██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║██╔══██╗
███████║███████╗   ██║   ██████╔╝██║██║  ██║
██╔══██║╚════██║   ██║   ██╔══██╗██║██║  ██║
██║  ██║███████║   ██║   ██║  ██║██║██████╔╝
╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═════╝ 
"""                         

NUMRENDERERS = 8
BLOCKSIZE = 64
CHANNELS = 2
SAMPLERATE = 44100
RINGBUFFERLENGTH = 30

class AstridServer(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = mp.Manager()

        self.bus = self.manager.Namespace()
        self.cwd = os.getcwd()
        self.event_loop = asyncio.get_event_loop()

        self.buf_q = self.manager.Queue()
        self.envelope_follower_response_q = self.manager.Queue()
        self.pitch_tracker_response_q = self.manager.Queue()
        self.load_q = self.manager.Queue()
        self.play_q = self.manager.Queue()
        self.read_q = self.manager.Queue()
        self.reply_q = self.manager.Queue()

        #stream_ctx = StreamContext()
        #self.stream_ctx_ptr = stream_ctx.get_pointer()

        # FIXME get this from env
        self.block_size = BLOCKSIZE
        self.channels = CHANNELS
        self.input_buffer_length = RINGBUFFERLENGTH
        self.numrenderers = NUMRENDERERS
        self.samplerate = SAMPLERATE

        self.bus.samplerate = SAMPLERATE
        self.bus.channels = CHANNELS
        self.bus.block_size = BLOCKSIZE
        self.bus.input_pitch = 220
        self.bus.input_amp = 0
        #self.bus.stream_ctx_ptr = self.stream_ctx_ptr

        self.stop_all = self.manager.Event() # voices
        self.shutdown_flag = self.manager.Event() # render & analysis processes
        self.stop_listening = self.manager.Event() # midi listeners
        self.finished_playing = self.manager.Event() # Mixer

        self.renderers = []
        self.observers = {}
        self.listeners = {}

        self.audiostream = io.AudioStream(
                                        self.buf_q, 
                                        self.read_q, 
                                        self.envelope_follower_response_q, 
                                        self.pitch_tracker_response_q,
                                        self.shutdown_flag,
                                        self.block_size, 
                                        self.channels, 
                                        self.samplerate
                                    )
    @contextmanager
    def msg_context(self):
        self.context = zmq.Context()
        self.msgsock = self.context.socket(zmq.REP)
        address = 'tcp://*:{}'.format(names.MSG_PORT)
        self.msgsock.bind(address)
        logger.info('^_-               Listening on %s' % address)

        yield None

        self.context.destroy()

    def cleanup(self):
        logger.info('cleaning up')

        self.stop_all.set()
        self.shutdown_flag.set()
        self.stop_listening.set()

        for r in self.renderers:
            r.join()

        logger.info('renderers cleaned up')

        for instrument_name, listener in self.listeners.items():
            logger.debug('stopping listeners')
            logger.debug(instrument_name)
            logger.debug(listener)
            if listener is not None:
                listener.join()

        logger.info('listeners cleaned up')

        #self.envelope_follower.join()
        #logger.info('envelope follower stopped')

        #self.pitch_tracker.join()
        #logger.info('pitch tracker stopped')

        self.audiostream.join()
        logger.info('audiostream cleaned up')

        self.event_loop.stop()
        self.event_loop.close()
        logger.info('stopped event loop')

        logger.info('stopping instrument observer')
        self.instrument_observer.stop()
        self.instrument_observer.join()

        logger.info('all cleaned up!')

    def start_instrument_listeners(self, instrument_name, instrument_path):
        if instrument_name not in self.listeners:
            renderer = orc.load_instrument(instrument_name, instrument_path)
            self.listeners[instrument_name] = midi.start_listener(instrument_name, renderer, self.bus, self.stop_listening)

    def load_instrument(self, instrument_name):
        instrument_path = os.path.join(self.cwd, names.ORC_DIR, '%s.py' % instrument_name)
        if not os.path.exists(instrument_path):
            logger.error('Could not find an instrument file at location %s' % instrument_path)
            return names.MSG_INVALID_INSTRUMENT

        self.start_instrument_listeners(instrument_name, instrument_path)

        for _ in range(self.numrenderers):
            self.load_q.put((instrument_name, instrument_path))

        return names.MSG_OK

    def run(self):
        logger.info(BANNER)

        self.audiostream.start()

        """
        logger.info('Starting envelope follower')
        try:
            self.envelope_follower = mp.Process(name='astrid-envelope-follower', target=analysis.envelope_follower, args=(self.bus, self.read_q, self.envelope_follower_response_q, self.shutdown_flag))
            self.envelope_follower.start()
        except Exception as e:
            logger.error(e)

        logger.info('Starting pitch tracker')
        try:
            self.pitch_tracker = mp.Process(name='astrid-pitch-tracker', target=analysis.pitch_tracker, args=(self.bus, self.read_q, self.pitch_tracker_response_q, self.shutdown_flag))
            self.pitch_tracker.start()
        except Exception as e:
            logger.error(e)
        """

        for _ in range(self.numrenderers):
            rp = workers.RenderProcess(
                    self.buf_q, 
                    self.play_q, 
                    self.load_q, 
                    self.reply_q, 
                    self.shutdown_flag,
                    self.stop_all, 
                    self.stop_listening, 
                    self.bus, 
                    self.event_loop,
                    self.cwd
                )
            rp.start()
            self.renderers += [ rp ]

        orc_fullpath = os.path.join(self.cwd, names.ORC_DIR)
        self.instrument_handler = orc.InstrumentHandler(self.load_q, orc_fullpath, self.numrenderers)
        self.instrument_observer = orc.Observer()
        self.instrument_observer.schedule(self.instrument_handler, path=orc_fullpath, recursive=True)
        self.instrument_observer.start()

        with self.msg_context():
            while True:
                reply = None
                cmd = self.msgsock.recv()
                cmd = msgpack.unpackb(cmd, encoding='utf-8')

                if len(cmd) == 0:
                    action = None
                else:
                    action = cmd.pop(0)

                if names.ntoc(action) == names.LOAD_INSTRUMENT:
                    if len(cmd) > 0:
                        reply = self.load_instrument(cmd[0])

                elif names.ntoc(action) == names.RELOAD_INSTRUMENT:
                    if len(cmd) > 0:
                        reply = self.load_instrument(cmd[0])

                elif names.ntoc(action) == names.ANALYSIS:
                    # TODO probably be nice to toggle 
                    # these on demand, maybe change params...
                    logger.info('ANALYSIS %s' % cmd)

                elif names.ntoc(action) == names.SHUTDOWN:
                    logger.info('SHUTDOWN %s' % cmd)
                    for _ in range(self.numrenderers):
                        self.load_q.put(names.SHUTDOWN)
                        self.play_q.put(names.SHUTDOWN)

                    self.msgsock.send(msgpack.packb(names.MSG_OK))
                    break

                elif names.ntoc(action) == names.STOP_ALL_VOICES:
                    logger.info('STOP_ALL_VOICES %s' % cmd)
                    self.stop_all.set()

                elif names.ntoc(action) == names.LIST_INSTRUMENTS:
                    logger.info('LIST_INSTRUMENTS %s' % cmd)
                    reply = [ str(instrument) for name, instrument in self.instruments.items() ]

                elif names.ntoc(action) == names.PLAY_INSTRUMENT:
                    if self.stop_all.is_set():
                        self.stop_all.clear() # FIXME this probably doesn't always work

                    self.play_q.put(cmd)

                self.msgsock.send(msgpack.packb(reply or names.MSG_OK))

        self.cleanup()
        logger.info('Astrid cleanup finished')

        self.stop()
        logger.info('Astrid stopped')


