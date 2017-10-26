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
from . import io
from . import midi
from . import orc

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
ANALYSIS = 9
NUMRENDERERS = 8

_cmdToName = {
    LOAD_INSTRUMENT: 'add', 
    RELOAD_INSTRUMENT: 'reload', 
    STOP_ALL_VOICES: 'stopall', 
    LIST_INSTRUMENTS: 'list', 
    PLAY_INSTRUMENT: 'play', 
    ANALYSIS: 'analysis', 
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
    'analysis': ANALYSIS,
    'shutdown': SHUTDOWN,
    'ok': MSG_OK, 
}

def ntoc(name):
    return _nameToCmd.get(name, None)

def cton(cmd):
    return _cmdToName.get(cmd, None)

class AnalysisProcess(mp.Process):
    def __init__(self, bus, shutdown_signal):
        super(AnalysisProcess, self).__init__()
        self.bus = bus
        self.shutdown_signal = shutdown_signal

    def run(self):
        pitch_thread = threading.Thread(target=io.pitch_tracker, args=(self.bus, self.shutdown_signal))
        logger.info('starting pitch tracker')
        pitch_thread.start()
        logger.info('waiting for shutdown')
        self.shutdown_signal.wait()
        logger.info('analysis got shutdown')
        pitch_thread.join()

class RenderProcess(mp.Process):
    def __init__(self, 
            play_q, 
            reply_q, 
            shutdown_flag,
            stop_all, 
            stop_listening, 
            bus,
            event_loop, 
            cwd
        ):

        super(RenderProcess, self).__init__()

        self.instruments = {}
        self.voices = []
        self.play_q = play_q
        self.reply_q = reply_q
        self.stop_all = stop_all
        self.shutdown_flag = shutdown_flag
        self.stop_listening = stop_listening
        self.bus = bus
        self.render_pool = ThreadPoolExecutor(max_workers=100)
        self.event_loop = event_loop
        self.cwd = cwd

    def get_renderer(self, name):
        try:
            logger.debug('calling load inst %s' % name)
            renderer = self.instruments.get(name, None)
            if renderer is None:
                renderer = self.load_renderer(name)
            logger.debug('Renderer %s' % self.instruments[name])
            return renderer
        except Exception as e:
            logger.error('Render process could not load instrument: InstrumentNotFound %s' % e)

    def load_renderer(self, name):
        try:
            logger.debug('calling load inst %s' % name)
            renderer = orc.load_instrument(name, cwd=self.cwd)
            logger.debug('%s %s %s' % (name, self.cwd, renderer))
            self.instruments[name] = renderer
            logger.debug('Render process loaded instrument %s' % self.instruments[name])
            return renderer
        except Exception as e:
            logger.error('Render process could not load instrument: InstrumentNotFound %s' % e)

    def run(self):
        logger.debug('render process init')

        while True:
            if self.shutdown_flag.is_set():
                logger.debug('got shutdown')
                break

            logger.debug('waiting for play messages')
            cmd = self.play_q.get()
            logger.debug('renderer PLAY_INSTRUMENT %s' % cmd)
            instrument_name = cmd[0]
            params = None
            if len(cmd) > 1:
                params = cmd[1]

            renderer = self.get_renderer(instrument_name)
            logger.debug('get_renderer result %s' % renderer)
            if renderer is None:
                logger.error('No renderer loaded for %s' % instrument_name)
                continue

            logger.debug('starting voice with inst %s and params %s' % (renderer, params))

            device_aliases = []
            if isinstance(renderer.MIDI, list):
                device_aliases = renderer.MIDI
            else:
                device_aliases = [ renderer.MIDI ]

            midi_maps = {}
            for i, device in enumerate(device_aliases):
                mapping = None
                if hasattr(renderer, 'MAP'):
                    if isinstance(renderer.MAP, list):
                        try:
                            mapping = renderer.MAP[i]
                        except IndexError:
                            pass
                    else:
                        mapping = renderer.MAP

                    midi_maps[device] = mapping 

                logger.debug('MIDI device mapping %s %s' % (device, mapping))


            ctx = orc.EventContext(
                        params=params, 
                        instrument_name=instrument_name, 
                        running=threading.Event(),
                        stop_all=self.stop_all, 
                        stop_me=threading.Event(),
                        bus=self.bus, 
                        midi_devices=device_aliases, 
                        midi_maps=midi_maps, 
                    )

            logger.debug('ctx %s' % ctx)

            futures = io.start_voice(self.event_loop, self.render_pool, renderer, ctx)
 
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
        logger.debug('cleaning up')
        self.stop_all.set()
        self.shutdown_flag.set()
        for r in self.renderers:
            logger.info('waiting for renderer shutdown')
            r.join()

        logger.info('renderers shutdown')

        for instrument_name, listener in self.listeners.items():
            logger.info('waiting for listener shutdown %s %s' % (instrument_name, listener))
            listener.join()

        logger.info('listeners shutdown')

        self.tracker.join()
        logger.info('analysis shutdown')

        logger.info('all cleaned up!')

    def run(self):
        logger.info(BANNER)
        self.numrenderers = 8
        self.manager = mp.Manager()
        self.play_q = self.manager.Queue()
        self.reply_q = self.manager.Queue()
        self.bus = self.manager.Namespace()
        self.stop_all = self.manager.Event() # voices
        self.shutdown_flag = self.manager.Event() # render & analysis processes
        self.stop_listening = self.manager.Event() # midi listeners
        self.renderers = []
        self.observers = {}
        self.listeners = {}

        self.tracker = AnalysisProcess(self.bus, self.shutdown_flag)
        self.tracker.start()

        for _ in range(self.numrenderers):
            rp = RenderProcess(
                    self.play_q, 
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

        with self.msg_context():
            while True:
                reply = None
                cmd = self.msgsock.recv()
                cmd = msgpack.unpackb(cmd, encoding='utf-8')

                if len(cmd) == 0:
                    action = None
                else:
                    action = cmd.pop(0)

                logger.debug('action %s' % action) 

                if ntoc(action) == LOAD_INSTRUMENT or ntoc(action) == RELOAD_INSTRUMENT:
                    logger.debug('LOAD_INSTRUMENT %s %s' % (action, cmd))
                    if len(cmd) > 0:
                        # FIXME Loading locally and discarding to init MIDI listener...
                        if cmd[0] not in self.listeners:
                            renderer = orc.load_instrument(cmd[0], cwd=self.cwd)
                            listener = midi.start_listener(cmd[0], renderer, self.bus, self.stop_listening)
                            self.listeners[cmd[0]] = listener

                elif ntoc(action) == ANALYSIS:
                    # TODO probably be nice to toggle 
                    # these on demand, maybe change params...
                    logger.info('ANALYSIS %s' % cmd)

                elif ntoc(action) == SHUTDOWN:
                    logger.info('SHUTDOWN %s' % cmd)
                    break

                elif ntoc(action) == STOP_ALL_VOICES:
                    logger.debug('STOP_ALL_VOICES %s' % cmd)
                    self.stop_all.set()

                elif ntoc(action) == LIST_INSTRUMENTS:
                    logger.debug('LIST_INSTRUMENTS %s' % cmd)
                    reply = [ str(instrument) for name, instrument in self.instruments.items() ]

                elif ntoc(action) == PLAY_INSTRUMENT:
                    logger.debug('PLAY_INSTRUMENT %s' % cmd)
                    self.play_q.put(cmd)

                    # FIXME this loads the module twice when creating 
                    # a new listener -- once in the render process play 
                    # handler and again below to start the listener
                    if cmd[0] not in self.listeners:
                        renderer = orc.load_instrument(cmd[0], cwd=self.cwd)
                        listener = midi.start_listener(cmd[0], renderer, self.bus, self.stop_listening)
                        self.listeners[cmd[0]] = listener

                self.msgsock.send(msgpack.packb(reply or MSG_OK))

        self.cleanup()
        logger.debug('Astrid run finished')
        self.stop()


