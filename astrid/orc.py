import asyncio
from contextlib import contextmanager
import importlib
import importlib.util
import os
import threading

import msgpack
import numpy as np
import sounddevice as sd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import zmq

from . import client
from . import midi
from . import names
from .logger import logger
from .mixer import StreamContextView

INSTRUMENT_RENDERER_KEY_TEMPLATE = '{}-renderer'

def load_instrument(name, path):
    """ Loads a renderer module from the script 
        at self.path 

        Failure to load the module raises an 
        InstrumentNotFoundError
    """
    try:
        logger.info('Loading instrument %s from %s' % (name, path))
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is not None:
            renderer = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(renderer)
            except Exception as e:
                logger.error(e)

            return renderer
        else:
            logger.error(path)
    except TypeError as e:
        logger.error(e)
        raise InstrumentNotFoundError(name) from e


class ParamBucket:
    """ params[key] to params.key
    """
    def __init__(self, params):
        self._params = params

    def __getattr__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        if self._params is None:
            return default
        return self._params.get(key, default)


class EventContext:
    before = None

    def __init__(self, 
            params=None, 
            instrument_name=None, 
            running=None,
            stop_all=None, 
            stop_me=None, 
            bus=None,
            midi_devices=None, 
            midi_maps=None
        ):

        #self.stream_ctx = StreamContextView(self.bus.stream_ctx_ptr)

        self.m = midi.MidiBucket(midi_devices, midi_maps, bus)
        self.p = ParamBucket(params)
        #self.client = client.AstridClient()
        self.client = None
        self.instrument_name = instrument_name
        self.running = running
        self.stop_all = stop_all
        self.stop_me = stop_me
        self.bus = bus

    def msg(self, msg):
        if self.client is not None:
            self.client.send_cmd(msg)

    def adc(self, length):
        framelength = int(self.bus.samplerate * length)
        return self.stream_ctx.read(framelength, 0)

    def play(self, instrument_name, *params, **kwargs):
        if params is not None:
            params = params[0]

        if params is None:
            params = {}

        if kwargs is not None:
            params.update(kwargs)

        if self.client is not None:
            self.client.send_cmd([names.PLAY_INSTRUMENT, instrument_name, params])

    def log(self, msg):
        logger.info(msg)

    def get_params(self):
        return self.p._params


class InstrumentNotFoundError(Exception):
    def __init__(self, instrument_name, *args, **kwargs):
        self.message = 'No instrument named %s found' % instrument_name

class InstrumentHandler(FileSystemEventHandler):
    def __init__(self, load_q, orc_path, numrenderers):
        super(InstrumentHandler, self).__init__()
        self.load_q = load_q
        self.orc_path = orc_path
        self.numrenderers = numrenderers

    def on_modified(self, event):
        logger.debug('updated %s' % event)
        if event.src_path[-3:] == '.py':
            instrument_name = os.path.basename(event.src_path).replace('.py', '')
            for _ in range(self.numrenderers):
                self.load_q.put((instrument_name, event.src_path))

