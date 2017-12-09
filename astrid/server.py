import asyncio
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import collections
import logging
from logging.handlers import SysLogHandler
import multiprocessing as mp
import os
import time
import threading
import random
import queue

import msgpack
from service import find_syslog, Service
import numpy as np
import zmq

from pippi.soundbuffer import RingBuffer

from . import midi
from . import io
from . import orc
from . import workers
from . import names

logger = logging.getLogger('astrid')
if not logger.handlers:
    logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
logger.setLevel(logging.INFO)

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

        self.buf_q = self.manager.Queue()
        self.bus = self.manager.Namespace()
        self.cwd = os.getcwd()
        self.event_loop = asyncio.get_event_loop()
        self.load_q = self.manager.Queue()
        self.numrenderers = NUMRENDERERS
        self.play_q = self.manager.Queue()
        self.reply_q = self.manager.Queue()

        # FIXME get this from env
        self.block_size = BLOCKSIZE
        self.channels = CHANNELS
        self.samplerate = SAMPLERATE
        self.input_buffer_length = RINGBUFFERLENGTH

        setattr(self.bus, 'block_size', self.block_size)
        setattr(self.bus, 'channels', self.channels)
        setattr(self.bus, 'samplerate', self.samplerate)
        setattr(self.bus, 'input_buffer_length', self.input_buffer_length)

        self.input_buffer_maxlen = (self.input_buffer_length * self.samplerate) // self.block_size
        setattr(self.bus, 'input_buffer_maxlen', self.input_buffer_maxlen)

        self.input_buffer = None
        self.playing = self.manager.list()
        self.num_playing = self.manager.Value('i', 0)
        self.record_head = self.manager.Value('i', 0)

        self.stop_all = self.manager.Event() # voices
        self.shutdown_flag = self.manager.Event() # render & analysis processes
        self.stop_listening = self.manager.Event() # midi listeners
        self.finished_playing = self.manager.Event() # Mixer

        self.renderers = []
        self.observers = {}
        self.listeners = {}

        self.buffer_queue_handler = io.BufferQueueHandler(self.buf_q, self.playing, self.num_playing, self.block_size, self.channels, self.samplerate)
        self.buffer_queue_handler.start()

        #self.tracker = workers.AnalysisProcess(self.bus, self.shutdown_flag, self.input_buffer, self.record_head)
        #self.tracker.start()

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
            listener.join()

        logger.info('listeners cleaned up')

        #self.tracker.join()
        #logger.info('analysis cleaned up')

        self.buffer_queue_handler.join()
        logger.info('buffer queue handler cleaned up')

        self.event_loop.stop()
        self.event_loop.close()
        logger.info('stopped event loop')

        logger.info('all cleaned up!')

    def start_instrument_listener(self, instrument_name, refresh=False):
        # FIXME if refresh=True then send listener stop and start again
        # with reloaded instrument
        if instrument_name not in self.listeners:
            logger.info('starting listener %s' % instrument_name)
            renderer = orc.load_instrument(instrument_name, cwd=self.cwd)
            self.listeners[instrument_name] = midi.start_listener(instrument_name, renderer, self.bus, self.stop_listening)
            logger.info('started listener %s' % instrument_name)

    def run(self):
        logger.info(BANNER)

        with self.msg_context():
            while True:
                reply = None
                cmd = self.msgsock.recv()
                cmd = msgpack.unpackb(cmd, encoding='utf-8')

                if len(cmd) == 0:
                    action = None
                else:
                    action = cmd.pop(0)

                logger.info('action %s' % action) 

                if names.ntoc(action) == names.LOAD_INSTRUMENT or \
                   names.ntoc(action) == names.RELOAD_INSTRUMENT:
                    self.start_instrument_listener(cmd[0])
                    logger.info('LOAD_INSTRUMENT %s %s' % (action, cmd))
                    if len(cmd) > 0:
                        for _ in range(self.numrenderers):
                            self.load_q.put(cmd[0])

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
                    for _ in range(self.numrenderers):
                        self.play_q.put(names.STOP_ALL_VOICES)

                elif names.ntoc(action) == names.LIST_INSTRUMENTS:
                    logger.info('LIST_INSTRUMENTS %s' % cmd)
                    reply = [ str(instrument) for name, instrument in self.instruments.items() ]

                elif names.ntoc(action) == names.PLAY_INSTRUMENT:
                    logger.info('PLAY_INSTRUMENT %s' % cmd)
                    self.play_q.put(cmd)

                self.msgsock.send(msgpack.packb(reply or names.MSG_OK))

        self.cleanup()
        logger.info('Astrid cleanup finished')

        self.stop()
        logger.info('Astrid stopped')


