import asyncio
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

def load_instrument(name, path=None, cwd=None):
    """ Loads a renderer module from the script 
        at self.path 

        Failure to load the module raises an 
        InstrumentNotFoundError
    """
    logger = logging.getLogger('astrid')
    if not logger.handlers:
        logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
    logger.setLevel(logging.INFO)

    if cwd is None:
        cwd = '.'

    if path is None:
        path = os.path.join(cwd, ORC_DIR, '%s.py' % name)

    logger.info('Loading instrument %s from %s' % (name, path))

    try:
        spec = importlib.util.spec_from_file_location(name, path)
        logger.info('spec %s' % spec)
        if spec is not None:
            renderer = importlib.util.module_from_spec(spec)
            logger.info('renderer %s' % renderer)
            try:
                spec.loader.exec_module(renderer)
            except Exception as e:
                logger.error(e)
            logger.info('post exec renderer %s' % renderer)
            return renderer
        else:
            logger.error(path)
    except (ModuleNotFoundError, TypeError) as e:
        logger.error(e)
        raise InstrumentNotFoundError(name) from e


class EventContext:
    before = None

    def __init__(self, 
            params=None, 
            instrument_name=None, 
            msgq=None, 
            running=None,
            stop_all=None, 
            stop_me=None
        ):

        self.params = params
        self.instrument_name = instrument_name
        self.msgq = msgq
        self.running = running
        self.stop_all = stop_all
        self.stop_me = stop_me

    def msg(self, msg):
        self.msgq.put(msg)

    def log(self, msg):
        logger.info(msg)


class InstrumentLoadOrchestrator(threading.Thread):
    def __init__(self, load_q, instruments, shutdown_flag, bus):
        super(InstrumentLoadOrchestrator, self).__init__()

        self.load_q = load_q
        self.instruments = instruments
        self.shutdown_flag = shutdown_flag
        self.bus = bus

    def run(self):
        """
        if False and self.observers.get(self.cmd[1], None) is None:
            instrument_handler = orc.InstrumentHandler(self.messg_q, cmd[0])
            instrument_observer = orc.Observer()
            instrument_observer.schedule(instrument_handler, path=cmd[1], recursive=True)
            logger.debug('add reload handler %s %s' % (instrument_handler, instrument_observer))
            self.observers[cmd[1]] = (instrument_observer, instrument_handler)
        """

        while True:
            logger.info('waiting for load messages')
            if self.shutdown_flag.is_set():
                logger.info('got shutdown')
                break


class InstrumentNotFoundError(Exception):
    def __init__(self, instrument_name, *args, **kwargs):
        self.message = 'No instrument named %s found' % instrument_name

class InstrumentHandler(FileSystemEventHandler):
    def __init__(self, messg_q, instrument_name):
        super(InstrumentHandler, self).__init__()
        self.messg_q = messg_q
        self.instrument_name = instrument_name

    def on_modified(self, event):
        logger.info('updated %s' % event)
        path = event.src_path


