import asyncio
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import collections
import multiprocessing as mp
import os
import time
import threading
import random
import queue
import uuid

from libc.stdlib cimport malloc, calloc, free
import msgpack
import numpy as np
import zmq

from . import midi
from . import io
from . import orc
from . import names
from . cimport q 
from . cimport mixer as m
from . import mixer as m
from .logger import logger
from pippi import dsp
from pippi.soundbuffer cimport SoundBuffer
import jack

BANNER = """
 █████╗ ███████╗████████╗██████╗ ██╗██████╗ 
██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║██╔══██╗
███████║███████╗   ██║   ██████╔╝██║██║  ██║
██╔══██║╚════██║   ██║   ██╔══██╗██║██║  ██║
██║  ██║███████║   ██║   ██║  ██║██║██████╔╝
╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═════╝ 
"""                         

CHANNELS = 2

class AstridServer:
    def __init__(self):
        self.cwd = os.getcwd()
        self.listeners = {}

    @contextmanager
    def msg_context(self):
        self.context = zmq.Context()
        self.msgsock = self.context.socket(zmq.REP)
        address = 'tcp://*:{}'.format(names.MSG_PORT)
        self.msgsock.bind(address)
        logger.info('^_-               Listening on %s' % address)

        yield None

        self.context.destroy()

    def cleanup(self):
        logger.info('cleaning up')

        for instrument_name, listener in self.listeners.items():
            if listener is not None:
                listener.join()

        self.instrument_observer.stop()
        self.instrument_observer.join()

        logger.info('all cleaned up!')

    def start_instrument_listeners(self, instrument_name, instrument_path):
        if instrument_name not in self.listeners:
            instrument = orc.load_instrument(instrument_name, instrument_path, self.bus)
            self.listeners[instrument_name] = midi.start_listener(instrument)

    def load_instrument(self, instrument_name):
        instrument_path = os.path.join(self.cwd, names.ORC_DIR, '%s.py' % instrument_name)
        if not os.path.exists(instrument_path):
            logger.error('Could not find an instrument file at location %s' % instrument_path)
            return names.MSG_INVALID_INSTRUMENT

        self.start_instrument_listeners(instrument_name, instrument_path)

        for _ in range(self.numrenderers):
            self.load_q.put((instrument_name, instrument_path))

        return names.MSG_OK

    def run(self):
        logger.info(BANNER)
        self.jack_client = jack.Client('astrid')

        cdef q.Q* buf_q = q.q_init()

        # FIXME get number of hardware channels
        for channel in range(CHANNELS):
            self.jack_client.inports.register('input_{0}'.format(channel))
            self.jack_client.outports.register('output_{0}'.format(channel))

        self.block_size = self.jack_client.blocksize
        self.channels = len(self.jack_client.outports)
        self.samplerate = self.jack_client.samplerate
        RUNNING = True

        def jack_callback(frames):
            if RUNNING:
                for channel, port in enumerate(self.jack_client.outports):
                    port.get_array().fill(0)
                raise jack.CallbackExit

            out = m.mixed(buf_q, self.channels, self.samplerate, self.block_size)

            for channel, port in enumerate(self.jack_client.outports):
                port.get_array()[:] = out[:,channel % out.channels]

        self.jack_client.set_process_callback(jack_callback)

        # Instrument reload listeners watch orc dir for saves
        orc_fullpath = os.path.join(self.cwd, names.ORC_DIR)
        self.instrument_handler = orc.InstrumentHandler(self.load_q, orc_fullpath, self.numrenderers)
        self.instrument_observer = orc.Observer()
        self.instrument_observer.schedule(self.instrument_handler, path=orc_fullpath, recursive=True)
        self.instrument_observer.start()

        with self.msg_context(), self.jack_client:
            capture = self.jack_client.get_ports(is_physical=True, is_output=True)
            if not capture:
                raise RuntimeError('No physical capture ports')

            for src, dest in zip(capture, self.jack_client.inports):
                self.jack_client.connect(src, dest)

            playback = self.jack_client.get_ports(is_physical=True, is_input=True)
            if not playback:
                raise RuntimeError('No physical playback ports')

            # FIXME -- add interface to zmq cmds for adding and removing synth/voice ports, 
            # which default to connecting to the master outputs... how to handle runtime 
            # choice of output port from instrument scripts?
            for src, dest in zip(self.jack_client.outports, playback):
                self.jack_client.connect(src, dest)

            while True:
                reply = None
                cmd = self.msgsock.recv()
                cmd = msgpack.unpackb(cmd, encoding='utf-8')

                if len(cmd) == 0:
                    action = None
                else:
                    action = cmd.pop(0)

                if names.ntoc(action) == names.LOAD_INSTRUMENT:
                    if len(cmd) > 0:
                        reply = self.load_instrument(cmd[0])

                elif names.ntoc(action) == names.RELOAD_INSTRUMENT:
                    if len(cmd) > 0:
                        reply = self.load_instrument(cmd[0])

                elif names.ntoc(action) == names.REGISTER_PORT:
                    if len(cmd) > 0:
                        try:
                            port_name, port_channels = cmd
                            print(port_name, port_channels)
                        except TypeError:
                            self.msgsock.send(msgpack.packb(names.MSG_BAD_PARAMS))
                            continue

                        # Check for a port with this name that already exists
                        # If not, register the port with jack
                        # Connect the port to the master output, mapping ports 
                        # to channels incrementally from hardware out 0

                elif names.ntoc(action) == names.SHUTDOWN:
                    logger.info('SHUTDOWN %s' % cmd)
                    for _ in range(self.numrenderers):
                        self.load_q.put(names.SHUTDOWN)
                        self.play_q.put(names.SHUTDOWN)

                    self.msgsock.send(msgpack.packb(names.MSG_OK))
                    break

                elif names.ntoc(action) == names.STOP_ALL_VOICES:
                    logger.info('STOP_ALL_VOICES %s' % cmd)
                    #self.bus.stop_all.set()

                elif names.ntoc(action) == names.LIST_INSTRUMENTS:
                    logger.info('LIST_INSTRUMENTS %s' % cmd)
                    reply = [ str(instrument) for name, instrument in self.instruments.items() ]

                elif names.ntoc(action) == names.PLAY_INSTRUMENT:
                    self.play_q.put(cmd)

                self.msgsock.send(msgpack.packb(reply or names.MSG_OK))

        self.cleanup()
        logger.info('Astrid cleanup finished')

        q.q_destroy(buf_q)

        self.stop()
        logger.info('Astrid stopped')


