#cython: language_level=3

import asyncio
from contextlib import contextmanager
import importlib
import importlib.util
import os
import threading

import redis
import msgpack
import numpy as np
import sounddevice as sd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import zmq

from pippi import dsp
from . import client
from . import midi
from . import names
from .logger import logger
from .circle cimport Circle

INSTRUMENT_RENDERER_KEY_TEMPLATE = '{}-renderer'

def load_instrument(name, path, shutdown=None):
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
                logger.exception('Error loading instrument module: %s' % str(e))

            instrument = Instrument(name, path, renderer, shutdown)

        else:
            logger.error('Could not load instrument - spec is None: %s %s' % (path, name))
            raise InstrumentNotFoundError(name)
    except TypeError as e:
        logger.exception('TypeError loading instrument module: %s' % str(e))
        raise InstrumentNotFoundError(name) from e

    midi.start_listener(instrument)
    return instrument

cdef class SessionParamBucket:
    """ params[key] to params.key
    """
    def __init__(self):
        self._bus = redis.StrictRedis(host='localhost', port=6379, db=0)

    def __getattr__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        v = self._bus.get(key) 
        if v is None:
            return default
        return v.decode('utf-8')

cdef class ParamBucket:
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


cdef class EventContext:
    def __init__(self, 
            params=None, 
            instrument_name=None, 
            running=None,
            shutdown=None, 
            stop_me=None, 
            sounds=None,
            midi_devices=None, 
            midi_maps=None, 
            before=None,
        ):

        self.before = before
        self.m = midi.MidiBucket(midi_devices, midi_maps)
        self.p = ParamBucket(params)
        self.s = SessionParamBucket() 
        self.client = None
        self.instrument_name = instrument_name
        self.running = running
        self.shutdown = shutdown
        self.stop_me = stop_me
        self.sounds = sounds
        self.adc = Circle()

    def msg(self, msg):
        if self.client is not None:
            self.client.send_cmd(msg)

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

cdef class Instrument:
    def __init__(self, str name, str path, object renderer, object shutdown):
        self.name = name
        self.path = path
        self.renderer = renderer
        self.sounds = self.load_sounds()
        self.shutdown = shutdown

    def reload(self):
        #logger.info('Reloading instrument %s from %s' % (self.name, self.path))
        spec = importlib.util.spec_from_file_location(self.name, self.path)
        if spec is not None:
            renderer = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(renderer)
            except Exception as e:
                logger.exception('Error loading instrument module: %s' % str(e))

            self.renderer = renderer
        else:
            logger.error(self.path)

    def load_sounds(self):
        if hasattr(self.renderer, 'SOUNDS') and isinstance(self.renderer.SOUNDS, list):
            return [ dsp.read(snd) for snd in self.renderer.SOUNDS ]
        elif hasattr(self.renderer, 'SOUNDS') and isinstance(self.renderer.SOUNDS, dict):
            return { k: dsp.read(snd) for k, snd in self.renderer.SOUNDS.items() }

        return None

    def map_midi_devices(self):
        device_aliases = []
        midi_maps = {}

        if hasattr(self.renderer, 'MIDI'): 
            if isinstance(self.renderer.MIDI, list):
                device_aliases = self.renderer.MIDI
            else:
                device_aliases = [ self.renderer.MIDI ]

        for i, device in enumerate(device_aliases):
            mapping = None
            if hasattr(self.renderer, 'MAP'):
                if isinstance(self.renderer.MAP, list):
                    try:
                        mapping = self.renderer.MAP[i]
                    except IndexError:
                        pass
                else:
                    mapping = self.renderer.MAP

                midi_maps[device] = mapping 

        return device_aliases, midi_maps

    def create_ctx(self, params):
        device_aliases, midi_maps = self.map_midi_devices()
        return EventContext(
                    params=params, 
                    instrument_name=self.name, 
                    running=threading.Event(),
                    shutdown=self.shutdown, 
                    stop_me=threading.Event(),
                    sounds=self.sounds,
                    midi_devices=device_aliases, 
                    midi_maps=midi_maps, 
                )



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

