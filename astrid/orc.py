import logging
import os
import importlib
import importlib.util

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(filename='pippi.log', level=logging.INFO)

class InstrumentNotFoundError(Exception):
    def __init__(self, instrument_name, *args, **kwargs):
        self.message = 'No instrument named %s found' % instrument_name

class InstrumentHandler(FileSystemEventHandler):
    def __init__(self, *args, **kwargs):
        super(InstrumentHandler, self).__init__(*args, **kwargs)

    def on_modified(self, event):
        path = event.src_path
        if path in self.instruments:
            # Signal reload
            pass

def load(name, orcdir=None):
    basepath = os.path.realpath(os.path.curdir)
    path = orcdir or os.path.join(basepath, 'orc/{}.py'.format(name))

    #instrument_handler = InstrumentHandler()
    #instrument_observer = Observer()
    #instrument_observer.schedule(instrument_handler, path='.', recursive=True)

    try:
        spec = importlib.util.spec_from_file_location(name, path)
        instrument = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(instrument)
        return instrument
    except ModuleNotFoundError as e:
        raise InstrumentNotFoundError(name) from e

