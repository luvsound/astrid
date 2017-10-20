import asyncio
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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

from pippi import oscs
from . import orc
from . import io

logger = logging.getLogger('astrid')
if not logger.handlers:
    logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
logger.setLevel(logging.DEBUG)

BANNER = """
 █████╗ ███████╗████████╗██████╗ ██╗██████╗ 
██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║██╔══██╗
███████║███████╗   ██║   ██████╔╝██║██║  ██║
██╔══██║╚════██║   ██║   ██╔══██╗██║██║  ██║
██║  ██║███████║   ██║   ██║  ██║██║██████╔╝
╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═════╝ 
"""                         

MSG_PORT = 9191
MSG_HOST = 'localhost'

LOAD_INSTRUMENT = 1
LIST_INSTRUMENTS = 2
PLAY_INSTRUMENT = 3
MSG_OK = 4
RENDER_PROCESS_SHUTDOWN_SIGNAL = 5
RELOAD_INSTRUMENT = 6
STOP_ALL_VOICES = 7
SHUTDOWN = 8
NUMRENDERERS = 8

_cmdToName = {
    LOAD_INSTRUMENT: 'add', 
    RELOAD_INSTRUMENT: 'reload', 
    STOP_ALL_VOICES: 'stopall', 
    LIST_INSTRUMENTS: 'list', 
    PLAY_INSTRUMENT: 'play', 
    SHUTDOWN: 'shutdown', 
    MSG_OK: 'ok', 
}

_nameToCmd = {
    'add': LOAD_INSTRUMENT, 
    'load': LOAD_INSTRUMENT, 
    'reload': RELOAD_INSTRUMENT, 
    'stopall': STOP_ALL_VOICES,
    'list': LIST_INSTRUMENTS, 
    'play': PLAY_INSTRUMENT, 
    'shutdown': SHUTDOWN,
    'ok': MSG_OK, 
}

def ntoc(name):
    return _nameToCmd.get(name, None)

def cton(cmd):
    return _cmdToName.get(cmd, None)

class RenderProcess(mp.Process):
    def __init__(self, 
            load_q, 
            play_q, 
            reply_q, 
            instruments,
            instrument_loading, 
            shutdown_flag,
            stop_all, 
            bus,
            event_loop, 
            cwd
        ):

        super(RenderProcess, self).__init__()

        self.instruments = {}
        self.load_q = load_q
        self.play_q = play_q
        self.reply_q = reply_q
        self.instrument_loading = instrument_loading
        self.stop_all = stop_all
        self.shutdown_flag = shutdown_flag
        self.bus = bus
        self.voices = []
        self.render_pool = ThreadPoolExecutor(max_workers=20)
        self.event_loop = event_loop
        self.cwd = cwd

    def get_renderer(self, name):
        try:
            logger.info('calling load inst %s' % name)
            renderer = self.instruments.get(name, None)
            if renderer is None:
                renderer = orc.load_instrument(name, cwd=self.cwd)
                logger.info('%s %s %s' % (name, self.cwd, renderer))
                self.instruments[name] = renderer
                logger.info('Render process loaded instrument %s' % self.instruments[name])
            logger.info('Renderer %s' % self.instruments[name])
            return renderer
        except Exception as e:
            logger.error('Render process could not load instrument: InstrumentNotFound %s' % e)

    def run(self):
        logger.info('render process init')

        while True:
            if self.shutdown_flag.is_set():
                logger.info('got shutdown')
                break

            logger.info('waiting for play messages')
            cmd = self.play_q.get()
            logger.info('renderer PLAY_INSTRUMENT %s' % cmd)
            instrument_name = cmd[0]

            renderer = self.get_renderer(instrument_name)
            logger.info('get_renderer result %s' % renderer)
            if renderer is None:
                logger.error('No renderer loaded for %s' % instrument_name)
                continue

            params = None
            logger.info('starting voice with inst %s and params %s' % (renderer, params))

            ctx = orc.EventContext(
                        params=params, 
                        instrument_name=instrument_name, 
                        msgq=self.play_q, 
                        running=threading.Event(),
                        stop_all=self.stop_all, 
                        stop_me=threading.Event()
                    )

            logger.info('ctx %s' % ctx)

            futures = io.start_voice(self.event_loop, self.render_pool, renderer, ctx)
 
        self.stop_all.set()
        self.render_pool.shutdown(wait=True)

class AstridServer(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwd = os.getcwd()
        self.event_loop = asyncio.get_event_loop()

    @contextmanager
    def msg_context(self):
        self.context = zmq.Context()
        self.msgsock = self.context.socket(zmq.REP)
        address = 'tcp://*:{}'.format(MSG_PORT)
        logger.info('^_-               Listening on %s' % address)
        self.msgsock.bind(address)
        yield None
        self.context.destroy()

    def cleanup(self):
        logger.info('cleaning up')
        self.stop_all.set()
        self.shutdown_flag.set()
        for r in self.renderers:
            r.join()

        logger.info('cleaned up')

    def run(self):
        logger.info(BANNER)
        self.numrenderers = 8
        self.manager = mp.Manager()
        self.play_q = self.manager.Queue()
        self.load_q = self.manager.Queue()
        self.reply_q = self.manager.Queue()
        self.bus = self.manager.Namespace()
        self.instruments = self.manager.dict()
        self.instrument_loading = self.manager.Event()
        self.stop_all = self.manager.Event()
        self.shutdown_flag = self.manager.Event()
        self.renderers = []
        self.observers = {}

        for _ in range(self.numrenderers):
            rp = RenderProcess(
                    self.load_q, 
                    self.play_q, 
                    self.reply_q, 
                    self.instruments,
                    self.instrument_loading, 
                    self.shutdown_flag,
                    self.stop_all, 
                    self.bus, 
                    self.event_loop,
                    self.cwd
                )
            rp.start()
            self.renderers += [ rp ]

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

                if ntoc(action) == LOAD_INSTRUMENT or ntoc(action) == RELOAD_INSTRUMENT:
                    logger.info('LOAD_INSTRUMENT %s %s' % (action, cmd))
                    self.load_q.put(cmd)

                elif ntoc(action) == SHUTDOWN:
                    logger.info('SHUTDOWN %s' % cmd)
                    break

                elif ntoc(action) == STOP_ALL_VOICES:
                    logger.info('STOP_ALL_VOICES %s' % cmd)
                    self.stop_all.set()

                elif ntoc(action) == LIST_INSTRUMENTS:
                    logger.info('LIST_INSTRUMENTS %s' % cmd)
                    reply = [ str(instrument) for name, instrument in self.instruments.items() ]

                elif ntoc(action) == PLAY_INSTRUMENT:
                    logger.info('PLAY_INSTRUMENT %s' % cmd)
                    self.play_q.put(cmd)

                self.msgsock.send(msgpack.packb(reply or MSG_OK))

        self.cleanup()
        logger.info('Astrid run finished')
        self.stop()


