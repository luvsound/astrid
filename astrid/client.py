from contextlib import contextmanager
import logging
from logging.handlers import SysLogHandler
import os

import msgpack
from service import find_syslog
import zmq

from . import server

class AstridClient:
    def __init__(self):
        self.logger = logging.getLogger('astrid')
        if not self.logger.handlers:
            self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)

    @contextmanager
    def get_client(self):
        context = zmq.Context()
        client = context.socket(zmq.REQ)
        address = 'tcp://{}:{}'.format(server.MSG_HOST, server.MSG_PORT)
        self.logger.debug('Connecting client to %s' % address)
        client.connect(address)
        yield client
        context.destroy()

    def send_cmd(self, cmd):
        msg = msgpack.packb(cmd)

        with self.get_client() as client:
            client.send(msg)
            resp = client.recv()
            resp = msgpack.unpackb(resp, encoding='utf-8')
            self.logger.debug(server.cton(resp))

    def list_instruments(self):
        with self.get_client() as client:
            msg = msgpack.packb([server.cton(server.LIST_INSTRUMENTS)])
            client.send(msg)
            instruments = client.recv()
            self.logger.debug(('!!list instruments', instruments))
            instruments = msgpack.unpackb(instruments, encoding='utf-8')
            self.logger.debug(('!!list instruments', instruments))
            return instruments      

        return {}


