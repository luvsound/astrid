from contextlib import contextmanager
import importlib
import importlib.util
import logging
from logging.handlers import SysLogHandler
import os
import threading

import msgpack
import numpy as np
from service import find_syslog
import sounddevice as sd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import zmq

from . import server

logger = logging.getLogger('astrid')
logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
logger.setLevel(logging.INFO)

ORC_DIR = 'orc'

class EventContext:
    def __init__(self, params=None):
        self._params = params

    @property
    def params(self):
        return self._params 

    def log(self, msg):
        logger.info(msg)

class InstrumentNotFoundError(Exception):
    def __init__(self, instrument_name, *args, **kwargs):
        self.message = 'No instrument named %s found' % instrument_name

class InstrumentHandler(FileSystemEventHandler):
    def __init__(self, *args, **kwargs):
        super(InstrumentHandler, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger('astrid')
        self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)

    def on_modified(self, event):
        path = event.src_path
        if path in self.instruments:
            # Signal reload
            pass

class Voice(threading.Thread):
    def __init__(self, instrument, params, instrument_name=None, messg_q=None):
        super(Voice, self).__init__()
        self.params = params
        self.instrument = instrument
        self.instrument_name = instrument_name
        self.messg_q = messg_q
        self.loop = True

    def retrigger(self):
        msg = [server.PLAY_INSTRUMENT, self.instrument_name, self.params]
        logger.info('retrigger msg %s' % msg)
        self.messg_q.put(msg)

    def run(self):
        logger.info('Voice running %s %s' % (self.instrument, self.params))
        ctx = EventContext(self.params)
        logger.info('Event Context %s' % ctx)
        renderer = self.instrument.play(ctx)
        logger.info('Renderer %s' % renderer)

        if hasattr(self.instrument, 'before'):
            self.instrument.before(ctx)

        with sd.Stream(channels=2, samplerate=44100, dtype='float32') as stream:
            logger.info('Stream %s' % stream)
            for snd in renderer:
                logger.info('Writing sound to stream %s' % snd)
                stream.write(np.asarray(snd.frames, dtype='float32'))
            logger.info('Stopped')

        if hasattr(self.instrument, 'done'):
            self.instrument.done(ctx)

        if self.loop:
            logger.info('Retriggering')
            self.retrigger()


def load_instrument(name, path=None):
    """ Loads a renderer module from the script 
        at self.path 

        Failure to load the module raises an 
        InstrumentNotFoundError
    """
    logger = logging.getLogger('astrid')
    if not logger.handlers:
        logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
    logger.setLevel(logging.INFO)

    #instrument_handler = InstrumentHandler()
    #instrument_observer = Observer()
    #instrument_observer.schedule(instrument_handler, path='.', recursive=True)

    if path is None:
        path = os.path.join(ORC_DIR, '%s.py' % name)

    logger.info('Loading instrument %s from %s' % (name, path))

    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is not None:
            renderer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(renderer)
            return renderer
        else:
            logger.error(path)
    except (ModuleNotFoundError, TypeError) as e:
        logger.error(e.message)
        raise InstrumentNotFoundError(name) from e


