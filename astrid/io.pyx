from __future__ import absolute_import
import collections
import threading
import queue
import time
import numpy as np
import redis
import sys

from .logger import logger
from . import names
from .orc cimport EventContext, Instrument
from pippi.soundbuffer cimport SoundBuffer


cdef class BufferNode:
    def __init__(self, snd, start_time, onset):
        self.snd = snd
        self.start_time = start_time
        self.onset = onset
        self.pos = 0
        self.done_playing = -1

    cpdef double[:,:] next_block(self, int block_size):
        cdef int startpos = self.pos
        cdef int endpos = startpos + block_size
        self.pos += block_size
        if endpos >= len(self.snd.frames):
            endpos = len(self.snd.frames)
            self.done_playing = 1
        return self.snd.frames[startpos:endpos]

cdef void play_sequence(buf_q, object player, EventContext ctx, tuple onsets, bint loop, double overlap):
    """ Play a sequence of overlapping oneshots
    """
    cdef double delay_time = 0
    cdef object snd 
    cdef long elapsed = 0
    cdef object delay = threading.Event()
    cdef Py_ssize_t numonsets = len(onsets)
    cdef Py_ssize_t i = 0
    cdef Py_ssize_t j = 0
    cdef Py_ssize_t k = 0
    cdef Py_ssize_t length = 0
    cdef double onset = 0
    cdef int channels = 2
    cdef int samplerate = 44100
    cdef double start_time = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
    cdef double[:] _onsets = np.array(onsets, 'd')

    #logger.info('begin play_sequence %s' % ctx.instrument_name)

    for onset in onsets:
        generator = player(ctx)
        onset = _onsets[i]

        delay.wait(timeout=onset)
        try:
            for snd in generator:
                bufnode = BufferNode(snd, start_time, onset)
                buf_q.put(bufnode)

        except Exception as e:
            logger.error('Error during %s generator render: %s' % (ctx.instrument_name, e))

        ctx.tick += 1

    if loop:
        delay.wait(timeout=<double>(overlap * snd.dur))

    #logger.info('play_sequence complete %s' % ctx.instrument_name)
    #elapsed = time.clock_gettime(time.CLOCK_MONOTONIC_RAW) - start_time

def wait_for_messages(stop_me, instrument_name):
    r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(names.STOP_ALL_VOICES, names.STOP_INSTRUMENT)
    for msg in pubsub.listen():
        c = int(msg['channel'] or 0)
        if not msg['type'] == 'message':
            continue

        data = msg['data']
        logger.info('MSG DATA %s - %s' % (data, instrument_name))

        if c == names.STOP_ALL_VOICES or (c == names.STOP_INSTRUMENT and msg['data'] == instrument_name):
            stop_me.set()
            break

cdef tuple collect_players(object instrument):
    loop = False
    if hasattr(instrument.renderer, 'LOOP'):
        loop = instrument.renderer.LOOP

    overlap = 1
    if hasattr(instrument.renderer, 'OVERLAP'):
        overlap = instrument.renderer.OVERLAP

    # find all play methods
    players = set()

    cdef tuple onset_list = (0,)

    # The simplest case is a single play method 
    # with an optional onset list or callback
    if hasattr(instrument.renderer, 'play'):
        onsets = getattr(instrument.renderer, 'onsets', (0,))
        players.add((instrument.renderer.play, onsets))

    # Play methods can also be registered via 
    # an @player.init decorator, which also registers 
    # an optional onset list or callback
    if hasattr(instrument.renderer, 'player') \
        and hasattr(instrument.renderer.player, 'players') \
        and isinstance(instrument.renderer.player.players, set):
        players |= instrument.renderer.player.players

    if hasattr(instrument.renderer, 'PLAYERS') \
        and isinstance(instrument.renderer.PLAYERS, set):
        players |= instrument.renderer.PLAYERS
    
    logger.info('COLLECT_PLAYERS players: %s' % players)
    return players, loop, overlap

cdef void init_voice(object instrument, object params, object buf_q):
    cdef object stop_me = threading.Event()
    cdef set players
    cdef tuple onset_list
    cdef bint loop
    cdef double overlap
    cdef EventContext ctx = instrument.create_ctx(params)
    ctx.running.set()

    message_listener = threading.Thread(target=wait_for_messages, args=(stop_me, ctx.instrument_name))
    message_listener.start()

    if hasattr(instrument.renderer, 'before'):
        # blocking before callback makes
        # its results available to voices
        ctx.before = instrument.renderer.before(ctx)

    players, loop, overlap = collect_players(instrument)

    cdef int count = 0
    cdef object delay = threading.Event()

    while True:
        for player, onsets in players:
            try:
                ctx.count = count
                ctx.tick = 0
                onset_list = (0,)
                try:
                    onset_list = tuple(onsets)
                except TypeError:
                    if callable(onsets):
                        onset_list = tuple(onsets(ctx))
                
                play_sequence(buf_q, player, ctx, onset_list, loop, overlap)
            except Exception as e:
                logger.error('error calling play_sequence: %s' % e)
           
        count += 1

        if not loop or ctx.shutdown.is_set() or stop_me.is_set():
            break

        instrument.reload()
        players, loop, overlap = collect_players(instrument)
        if hasattr(instrument.renderer, 'before'):
            # blocking before callback makes
            # its results available to voices
            ctx.before = instrument.renderer.before(ctx)

    ctx.running.clear()

    if hasattr(instrument.renderer, 'done'):
        # When the loop has completed or playback has stopped, 
        # execute the done callback
        instrument.renderer.done(ctx)

