from contextlib import contextmanager
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

MSG_PORT = 9191
MSG_HOST = 'localhost'

LOAD_INSTRUMENT = 1
LIST_INSTRUMENTS = 2
PLAY_INSTRUMENT = 3
MSG_OK = 4

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

class AstridServer(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)
        self.cwd = os.getcwd()
        self.instruments = {}

    @contextmanager
    def msg_context(self):
        self.logger.info('Creating zmq context')
        self.context = zmq.Context()

        self.logger.info('Creating socket')
        self.msgsock = self.context.socket(zmq.REP)

        address = 'tcp://*:{}'.format(MSG_PORT)
        self.logger.info('Binding to %s' % address)
        self.msgsock.bind(address)
        yield None
        self.context.destroy()

    @contextmanager
    def get_client(self):
        self.logger.info('Creating client context')
        context = zmq.Context()

        self.logger.info('Creating client socket')
        client = context.socket(zmq.REQ)

        address = 'tcp://{}:{}'.format(MSG_HOST, MSG_PORT)
        self.logger.info('Connecting client to %s' % address)
        client.connect(address)
        yield client
        context.destroy()

    def ntoc(self, name):
        if isinstance(name, bytes):
            name = name.decode('ascii')

        return _nameToCmd.get(name, None)

    def cton(self, cmd):
        if isinstance(cmd, bytes):
            cmd = cmd.decode('ascii')

        return _cmdToName.get(cmd, None)

    def send_cmd(self, cmd):
        if self.ntoc(cmd[0]) == LOAD_INSTRUMENT:
            cmd[2] = os.path.abspath(cmd[2])

        self.logger.info('cmd %s' % cmd)

        msg = msgpack.packb(cmd)

        with self.get_client() as client:
            client.send(msg)
            resp = client.recv()
            self.logger.info(msgpack.unpackb(resp))

    def _load_instrument(self, name, path):
        self.logger.info((name, path))
        try:
            instrument = orc.Instrument(name, path)
            self.instruments[name] = instrument
            self.logger.info('Loaded instrument %s' % instrument)
        except orc.InstrumentNotFoundError as e:
            self.logger.error('load_instrument: InstrumentNotFound %s' % e)
            raise orc.InstrumentNotFoundError(name) from e

    def _play_instrument(self, instrument, *params):
        self.instruments[instrument].play()        

    def _render(self, instrument, params=None):
        self.instruments[name].render(params)
        self.logger.info('render %s' % name)

    def handle_cmd(self, cmd):
        self.logger.info('AstridServer.handle_cmd %s' % cmd)
        if len(cmd) == 0:
            return None

        verb = cmd.pop(0)
        self.logger.info('verb %s' % verb) 

        if self.ntoc(verb) == LOAD_INSTRUMENT:
            self._load_instrument(*cmd)

        elif self.ntoc(verb) == LIST_INSTRUMENTS:
            return [ str(instrument) for name, instrument in self.instruments.items() ]

        elif self.ntoc(verb) == PLAY_INSTRUMENT:
            self._play_instrument(*cmd)

    def list_instruments(self):
        with self.get_client() as client:
            msg = msgpack.packb([self.cton(LIST_INSTRUMENTS)])
            client.send(msg)
            instruments = client.recv()
            self.logger.info(('!!list instruments', instruments))
            instruments = msgpack.unpackb(instruments)
            self.logger.info(('!!list instruments', instruments))
            return instruments      

        return {}

    def run(self):
        with self.msg_context():
            while True:
                self.logger.info('Waiting for messages')
                response = self.msgsock.recv()
                response = msgpack.unpackb(response)
                reply = self.handle_cmd(response)
                self.logger.info('got response %s' % response)
                self.logger.info('sending reply %s' % reply)
                self.msgsock.send(msgpack.packb(reply or MSG_OK))


