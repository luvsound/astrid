from contextlib import contextmanager
import os

import msgpack
import zmq

from . import names
from .logger import logger

class AstridClient:
    @contextmanager
    def get_client(self):
        context = zmq.Context()
        client = context.socket(zmq.REQ)
        address = 'tcp://{}:{}'.format(names.MSG_HOST, names.MSG_PORT)
        logger.debug('Connecting client to %s' % address)
        client.connect(address)
        yield client
        context.destroy()

    def send_cmd(self, cmd):
        msg = msgpack.packb(cmd)

        with self.get_client() as client:
            client.send(msg)
            resp = client.recv()
            #resp = msgpack.unpackb(resp, encoding='utf-8')
            resp = msgpack.unpackb(resp)
            logger.debug(names.cton(resp))

    def list_instruments(self):
        with self.get_client() as client:
            msg = msgpack.packb([names.cton(names.LIST_INSTRUMENTS)])
            client.send(msg)
            instruments = client.recv()
            logger.debug(('!!list instruments', instruments))
            #instruments = msgpack.unpackb(instruments, encoding='utf-8')
            instruments = msgpack.unpackb(instruments)
            logger.debug(('!!list instruments', instruments))
            return instruments      

        return {}


