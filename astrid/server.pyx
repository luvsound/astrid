#cython: language_level=3

from contextlib import contextmanager
import collections
import os
import time
import threading
import multiprocessing as mp
import random
import queue
import uuid

from libc.stdlib cimport malloc, calloc, free
import msgpack
import numpy as np
import zmq
import redis

from . import midi
from . cimport io
from . import io
from . import orc
from . import names
from . import voices
from .defaults import DEFAULT_CHANNELS
from .logger import logger
from .circle import Circle
from .sampler import Sampler
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


class AstridServer:
    def __init__(self):
        self.cwd = os.getcwd()
        self.listeners = {}
        self.channels = DEFAULT_CHANNELS

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

        self.jack_client.deactivate()
        self.jack_client.close()

        logger.info('all cleaned up!')

    def load_instrument(self, instrument_name):
        instrument_path = os.path.join(self.cwd, names.ORC_DIR, '%s.py' % instrument_name)
        if not os.path.exists(instrument_path):
            logger.error('Could not find an instrument file at location %s' % instrument_path)
            return names.MSG_INVALID_INSTRUMENT

        #for _ in range(self.numrenderers):
        #    self.load_q.put((instrument_name, instrument_path))
        self.redis.publish(names.LOAD_INSTRUMENT, instrument_name)

        return names.MSG_OK

    def wait_for_buffers(self, buffers, buf_q, buflock):
        while True:
            msg = buf_q.get()
            if msg == names.SHUTDOWN:
                break

            with buflock:
                logger.info('Adding to buf q: %s %s %s' % (msg.start_time, msg.onset, msg.pos))
                buffers += [ msg ]

    def wait_for_params(self, param_q):
        bus = redis.StrictRedis(host='localhost', port=6379, db=0)

        while True:
            msg = param_q.get()
            if msg == names.SHUTDOWN:
                break

            logger.info('GOT PARAM UPDATE %s' % msg)
            for m in msg:
                try:
                    k, v = tuple(m.split(':'))
                    bus.set(k, v)
                except ValueError as e:
                    logger.exception('Bad param: %s' % m)

    def run(self):
        logger.info(BANNER)

        self.jack_client = jack.Client('astrid')
        self.load_q = mp.Queue()
        self.play_q = mp.Queue()
        self.param_q = mp.Queue()
        self.buf_q = mp.Queue()
        self.buflock = mp.Lock()
        self.shutdown = mp.Event()
        self.numrenderers = 8
        self.renderers = []
        self.buffers = []
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.redis.pubsub()


        self.buffer_listener = threading.Thread(target=self.wait_for_buffers, args=(self.buffers, self.buf_q, self.buflock))
        self.buffer_listener.start()

        self.param_listener = threading.Thread(target=self.wait_for_params, args=(self.param_q,))
        self.param_listener.start()

        self.listeners = midi.start_listeners(self.shutdown)

        for i in range(self.numrenderers):
            r = voices.VoiceHandler(self.play_q, self.load_q, self.buf_q, self.shutdown, self.cwd)
            r.start()
            self.renderers += [ r ]

        self.block_size = self.jack_client.blocksize
        self.channels = len(self.jack_client.outports)
        self.samplerate = self.jack_client.samplerate
        self.RUNNING = True

        # FIXME get number of hardware channels
        for channel in range(self.channels):
            self.jack_client.inports.register('input_{0}'.format(channel))
            self.jack_client.outports.register('output_{0}'.format(channel))

        self.redis.set('SAMPLERATE', self.samplerate)
        self.redis.set('CHANNELS', self.channels)
        self.redis.set('BLOCKSIZE', self.block_size)

        self.circle = Circle()
        self.sampler = Sampler()

        def jack_callback(frames):
            if not self.RUNNING:
                for channel, port in enumerate(self.jack_client.outports):
                    port.get_array().fill(0)
                raise jack.CallbackExit

            cdef double[:,:] inbuf = np.zeros((self.jack_client.blocksize, self.channels), dtype='d')
            cdef double[:,:] outbuf = np.zeros((self.jack_client.blocksize, self.channels), dtype='d')
            cdef double[:,:] next_block
            cdef int blocklen

            with self.buflock:
                to_remove = []
                for b in self.buffers:
                    if b.done_playing > 0:
                        to_remove += [ b ]
                        continue
                    next_block = b.next_block(self.block_size)
                    blocklen = <int>len(next_block)
                    for i in range(blocklen):
                        for c in range(self.channels):
                            outbuf[i, c] += next_block[i, c]

                for b in to_remove:
                    i = self.buffers.index(b)
                    del self.buffers[i]

            for channel, port in enumerate(self.jack_client.outports):
                if channel < self.channels:
                    port.get_array()[:] = np.array(outbuf[:,channel]).astype('f')

            """
            for channel, port in enumerate(self.jack_client.inports):
                inblock = port.get_array().astype('d')
                for i in range(self.block_size):
                    inbuf[i,channel] = inblock[i]

            self.circle.add(inbuf)
            """

        self.jack_client.set_process_callback(jack_callback)

        # Instrument reload listeners watch orc dir for saves
        orc_fullpath = os.path.join(self.cwd, names.ORC_DIR)
        self.instrument_handler = orc.InstrumentHandler(self.load_q, orc_fullpath, self.numrenderers)
        self.instrument_observer = orc.Observer()
        self.instrument_observer.schedule(self.instrument_handler, path=orc_fullpath, recursive=True)
        self.instrument_observer.start()

        with self.msg_context():
            self.jack_client.activate()
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
                #cmd = msgpack.unpackb(cmd, encoding='utf-8')
                cmd = msgpack.unpackb(cmd)

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

                    self.RUNNING = False
                    self.shutdown.set()
                    self.msgsock.send(msgpack.packb(names.MSG_OK))
                    self.redis.publish(names.SHUTDOWN, names.SHUTDOWN)
                    break

                elif names.ntoc(action) == names.STOP_ALL_VOICES:
                    logger.info('STOP_ALL_VOICES %s' % cmd)
                    self.redis.publish(names.STOP_ALL_VOICES, names.STOP_ALL_VOICES)

                elif names.ntoc(action) == names.STOP_INSTRUMENT:
                    logger.info('STOP_INSTRUMENT %s' % cmd)
                    self.redis.publish(names.STOP_INSTRUMENT, cmd[0])

                elif names.ntoc(action) == names.LIST_INSTRUMENTS:
                    logger.info('LIST_INSTRUMENTS %s' % cmd)
                    reply = [ str(instrument) for name, instrument in self.instruments.items() ]

                elif names.ntoc(action) == names.PLAY_INSTRUMENT:
                    self.play_q.put(cmd)

                elif names.ntoc(action) == names.SET_VALUE:
                    logger.info('SET_VALUE %s' % cmd)
                    self.param_q.put(cmd)

                elif names.ntoc(action) == names.CLEAR_BANK:
                    logger.info('CLEAR_BANK %s' % cmd)
                    for b in cmd:
                        self.redis.unlink(b)

                elif names.ntoc(action) == names.REC_BANK:
                    logger.info('REC_BANK %s' % cmd)
                    b, *params = cmd
                    if len(params) == 0:
                        rtime = 1
                    else:
                        rtime = float(params[0])
                    self.sampler.write(b, self.circle.read(rtime))

                elif names.ntoc(action) == names.DUB_BANK:
                    logger.info('DUB_BANK %s' % cmd)
                    b, *params = cmd
                    self.sampler.dub(b, self.circle.read(*params))

                self.msgsock.send(msgpack.packb(reply or names.MSG_OK))

        for r in self.renderers:
            r.join()

        self.buffer_listener.join()

        self.cleanup()
        logger.info('Astrid cleanup finished')

        self.stop()
        logger.info('Astrid stopped')


