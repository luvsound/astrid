from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor
import logging
from logging.handlers import SysLogHandler
import multiprocessing as mp
import os
import time
import threading

import msgpack
from service import find_syslog, Service
import numpy as np
import zmq

from pippi import oscs
from . import orc

logger = logging.getLogger('astrid')
#logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
logger.setLevel(logging.INFO)

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

_cmdToName = {
    LOAD_INSTRUMENT: 'add', 
    LIST_INSTRUMENTS: 'list', 
    PLAY_INSTRUMENT: 'play', 
    MSG_OK: 'ok', 
}

_nameToCmd = {
    'add': LOAD_INSTRUMENT, 
    'load': LOAD_INSTRUMENT, 
    'list': LIST_INSTRUMENTS, 
    'play': PLAY_INSTRUMENT, 
    'ok': MSG_OK, 
}

def ntoc(name):
    return _nameToCmd.get(name, None)

def cton(cmd):
    return _cmdToName.get(cmd, None)

class RenderProcess(mp.Process):
    def __init__(self, messg_q, reply_q, reload_signal, bus=None, instruments=None):
        super(RenderProcess, self).__init__()
        self.instruments = {}
        self.messg_q = messg_q
        self.reply_q = reply_q
        self.reload_signal = reload_signal
        self.bus = bus

        if instruments is not None:
            for name, path in instruments:
                self._load_instrument(name, path)

    def load_instrument(self, name, path=None):
        try:
            instrument = orc.load_instrument(name, path)
            self.instruments[name] = instrument
            logger.info('Renderer loaded instrument %s' % instrument)
        except orc.InstrumentNotFoundError as e:
            logger.error('Renderer could not load instrument: InstrumentNotFound %s' % e)
            raise orc.InstrumentNotFoundError(name) from e

        return instrument

    def get_instrument(self, name, path=None):
        return instrument

    def cleanup(self):
        # cleanup voice threads
        logger.info('cleaning up')

    def run(self):
        running = True
        while running:
            cmd = self.messg_q.get()
            action = cmd.pop(0)
            logger.info('renderer got cmd from queue %s %s' % (action, cmd))

            if action == RENDER_PROCESS_SHUTDOWN_SIGNAL:
                logger.info('got shutdown signal')
                running = False

            elif action == PLAY_INSTRUMENT:
                logger.info('renderer PLAY_INSTRUMENT %s' % cmd)
                instrument_name, params = None, None
                if len(cmd) == 2:
                    instrument_name, params = cmd
                elif len(cmd) == 1:
                    instrument_name = cmd[0]

                instrument = self.instruments.get(instrument_name, None)
                if instrument is None:
                    # Try to load instrument from orc directory
                    logger.warning('%s not found, trying orc dir' % instrument_name)
                    instrument = self.load_instrument(instrument_name, None)

                logger.info('starting voice with inst %s and params %s' % (instrument, params))
                voice = orc.Voice(instrument, params, instrument_name, self.messg_q)
                voice.start()

            elif action == LOAD_INSTRUMENT:
                logger.info('renderer LOAD_INSTRUMENT %s' % cmd)
                self.load_instrument(cmd[0], cmd[1])

            elif action == LIST_INSTRUMENTS:
                logger.info('renderer LIST_INSTRUMENTS')

        self.cleanup()

class AstridServer(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwd = os.getcwd()

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
        for _ in range(self.numrenderers):
            self.messg_q.put([RENDER_PROCESS_SHUTDOWN_SIGNAL])

    def run(self):
        logger.info(BANNER)
        self.numrenderers = 8
        self.manager = mp.Manager()
        self.messg_q = self.manager.Queue()
        self.reply_q = self.manager.Queue()
        self.bus = self.manager.Namespace()
        self.reload_signal = mp.Event()
        self.running = True
        self.renderers = []
        for _ in range(self.numrenderers):
            rp = RenderProcess(self.messg_q, self.reply_q, self.reload_signal, self.bus)
            rp.start()
            self.renderers += [ rp ]

        with self.msg_context():
            while self.running:
                if self.got_sigterm():
                    self.running = False

                reply = None
                cmd = self.msgsock.recv()
                cmd = msgpack.unpackb(cmd, encoding='utf-8')

                if len(cmd) == 0:
                    action = None
                else:
                    action = cmd.pop(0)

                logger.debug('action %s' % action) 

                if ntoc(action) == LOAD_INSTRUMENT:
                    logger.info('LOAD_INSTRUMENT %s' % cmd)
                    for _ in range(self.numrenderers):
                        self.messg_q.put([LOAD_INSTRUMENT, *cmd])

                elif ntoc(action) == LIST_INSTRUMENTS:
                    logger.info('LIST_INSTRUMENTS %s' % cmd)
                    self.messg_q.put([LIST_INSTRUMENTS, *cmd])
                    logger.info('waiting for reply')
                    instruments = self.reply_q.get()
                    logger.info('got reply %s' % instruments)
                    reply = [ str(instrument) for name, instrument in instruments.items() ]

                elif ntoc(action) == PLAY_INSTRUMENT:
                    logger.info('PLAY_INSTRUMENT %s' % cmd)
                    self.messg_q.put([PLAY_INSTRUMENT, *cmd])

                self.msgsock.send(msgpack.packb(reply or MSG_OK))

        self.cleanup()
        logger.info('Astrid run finished [%s]' % self.get_pid())


