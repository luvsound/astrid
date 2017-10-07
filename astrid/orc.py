import importlib
import importlib.util
import logging
from logging.handlers import SysLogHandler
import os
import threading

import numpy as np
from service import find_syslog
import sounddevice as sd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

ORC_DIR = 'orc'

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
    def __init__(self, instrument, params, *args, **kwargs):
        super(Voice, self).__init__(*args, **kwargs)
        self.instrument = instrument
        self.params = params

    def run(self):
        self.instrument._play(self.params)

class Instrument:
    def __init__(self, name, path=None):
        self.logger = logging.getLogger('astrid')
        self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)

        if isinstance(name, bytes):
            name = name.decode('ascii')

        if isinstance(path, bytes):
            path = path.decode('ascii')

        self.name = name

        if path is None:
            self.path = os.path.join(ORC_DIR, '%s.py' % self.name)
        else:
            self.path = path

        self.renderer = self.load_renderer()

    def __repr__(self):
        return '{}: {}'.format(self.name, self.path)

    def load_renderer(self):
        """ Loads a renderer module from the script 
            at self.path 

            Failure to load the module raises an 
            InstrumentNotFoundError
        """
        #instrument_handler = InstrumentHandler()
        #instrument_observer = Observer()
        #instrument_observer.schedule(instrument_handler, path='.', recursive=True)

        self.logger.info(('load_renderer', self.name, self.path))

        try:
            spec = importlib.util.spec_from_file_location(self.name, self.path)
            if spec is not None:
                renderer = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(renderer)
                return renderer
            else:
                self.logger.error(self.path)
        except (ModuleNotFoundError, TypeError) as e:
            self.logger.error(e.message)
            raise InstrumentNotFoundError(self.name) from e

    def render(params=None):
        if params is None:
            params = {}

        self.buffer = self.renderer.play(params)

    def play(self, params=None):
        voice = Voice(self, params)
        voice.start()

    def _play(self, params=None):
        renderer = self.renderer.play(params)

        with sd.Stream(channels=2, samplerate=44100, dtype='float32') as stream:
            for snd in renderer:
                self.logger.info('Writing sound to stream')
                stream.write(np.asarray(snd.frames, dtype='float32'))
            self.logger.info('Stopped')

