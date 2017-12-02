import asyncio
import readline
import collections
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import logging
import functools
from logging.handlers import SysLogHandler
import queue
import threading
import time
import warnings
import multiprocessing as mp

import numpy as np
from service import find_syslog
import sounddevice as sd
from aubio import pitch

from . import names
from .mixer import AstridMixer
from pippi.soundbuffer import SoundBuffer

warnings.simplefilter('always')
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('astrid')
if not logger.handlers:
    logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))

def get_input_blocks(record_head, input_buffer_stack, blocks=1):
    read_head = 0 if record_head.value < 0 else record_head.value
    return input_buffer_stack[read_head]
    
def pitch_tracker(bus, record_head, input_buffer_stack, shutdown_signal):
    logger.info('starting pitch tracker')
    window_size = 4096
    hop_size = bus.block_size
    tolerance = 0.8
    wait_time = (bus.samplerate / hop_size) / 1000
    delay = threading.Event()

    tracker = pitch('yin', window_size, hop_size, bus.samplerate)
    tracker.set_unit('freq')
    tracker.set_tolerance(bus.pitch_tracker_tolerance)

    while True:
        if shutdown_signal.is_set():
            break

        #p = tracker(input_buffer_stack[read_head][:,0].flatten())[0]
        p = 1
        if tracker.get_confidence() >= tolerance:
            setattr(bus, 'input_pitch', p)

        delay.wait(timeout=wait_time)

def envelope_follower(bus, record_head, input_buffer, shutdown_signal):
    logger.info('starting envelope follower')
    wait_time = 0.015
    delay = threading.Event()

    while True:
        if shutdown_signal.is_set():
            break

        read_head = record_head.value - 1
        read_head = 0 if read_head < 0 else read_head
        try:
            setattr(bus, 'input_amp', np.amax(input_buffer[read_head]))
        except Exception as e:
            pass
            #logger.error(e)
        delay.wait(timeout=wait_time)

class BufferEndReached(Exception):
    pass

class RingBuffer:
    def __init__(self, length, channels=2):
        self.write_index = 0
        self.frames = np.zeros((length, channels))

    def get_frames(self, length):
        last_frame_index = (self.write_index - 1) % self.length
        return self.frames[last_frame_index - length]

class PlayBuffer:
    """ This is just a wrapper around a
        bare numpy array.
        
        The mixer callback gets a block of sound 
        by calling get_block() which either returns 
        a buffer that equals the block size, or 
        raises a BufferEndReached if there are no 
        more samples to read.

        The callback will remove this playbuffer
        from the stack of playing buffers when finished.
    """
    def __init__(self, snd, block_size=64, pos=0):
        self.snd = snd
        self.pos = pos
        self.length = len(snd)
        self.block_size = block_size
        self.silence = np.zeros((block_size, snd.channels), dtype='float32')

    def get_block(self):
        start = self.pos * self.block_size
        end = start + self.block_size
        self.pos += 1
        if end < self.length:
            return np.asarray(self.snd.frames[start:end], dtype='float32')
        elif start >= self.length:
            raise BufferEndReached
        
        return np.concatenate(self.snd.frames[start:], self.silence[:end-self.length])

class BufferQueueHandler(threading.Thread):
    """ Just watches for new sounds coming into the 
        shared play_q, wraps them in a PlayBuffer and 
        appends them to the end of the stack of playing 
        buffers.
    """
    def __init__(self, buf_q, playing, num_playing, block_size=64, channels=2, samplerate=44100):
        super(BufferQueueHandler, self).__init__()
        self.buf_q = buf_q
        self.playing = playing
        self.num_playing = num_playing
        self.block_size = block_size
        self.mixer = AstridMixer(block_size, channels, samplerate)
        logger.info('started BUF QUEUE')

    def run(self):
        while True:
            snd = self.buf_q.get()
            logger.info('BUF QUEUE got snd')

            if snd == names.SHUTDOWN:
                break

            try:
                #playbuf = PlayBuffer(snd, self.block_size)
                logger.info('adding %s to ASTRID MIXER' % snd)
                #self.playing.append(playbuf)
                #self.num_playing.value = len(self.playing)
                self.mixer.add(snd)
            except Exception as e:
                logger.error(e)

        self.mixer.shutdown()

class OldAstridMixer(mp.Process):
    # FIXME do this with cython's openmp compat
    """
    cdef public double[:,:] silence
    cdef public int block_size
    cdef public int channels
    cdef public int samplerate
    cdef public int input_buffer_maxlen
    cdef public int i
    cdef public int _num_playing
    """

    def __init__(self, 
            buf_q, 
            play_q, 
            playing, 
            num_playing, 
            record_head, 
            finished_event, 
            block_size=64, 
            channels=2, 
            samplerate=44100, 
            input_buffer=None, 
            input_buffer_maxlen=0
        ):
        logger.info('Starting AstridMixer')
        super(OldAstridMixer, self).__init__()
        self.buf_q = buf_q
        self.play_q = play_q
        self.playing = playing
        self.num_playing = num_playing
        self.record_head = record_head
        self.finished_event = finished_event
        self.block_size = block_size
        self.channels = channels
        self.samplerate = samplerate
        self.input_buffer = input_buffer
        self.input_buffer_maxlen = input_buffer_maxlen
        self.silence = np.zeros((block_size, channels), dtype='float32')
        self.i = 0
        self._num_playing = len(self.num_playing.value)

    def run(self):
        try:
            logger.info('Starting buffer queue handler')
            buffer_queue_handler = BufferQueueHandler(self.buf_q, self.playing, self.num_playing, self.block_size)
            buffer_queue_handler.start()
            logger.info('BUF QUEUE handler started')
        except Exception as e:
            logger.error(e)

        self.finished_event.wait()

        logger.info('shutting mixer down')
        self.buf_q.put(names.SHUTDOWN)
        buffer_queue_handler.join()


def play_sequence(buf_q, event_loop, player, ctx, onsets, done_playing_event):
    """ Schedule a sequence of overlapping oneshots
    """
    logger.info('play_sequence %s' % onsets)
    if not isinstance(onsets, collections.Iterable):
        try: 
            onsets = onsets(ctx)
        except Exception as e:
            logger.error('Onset callback failed with msg %s' % e)

    delay = threading.Event()
    logger.info('delay %s' % delay)

    count = 0
    start_time = event_loop.time()
    logger.info('start time %s' % start_time)
    logger.info('playing %s onsets %s' % (len(onsets), onsets))
    for onset in onsets:
        delay_time = onset
        elapsed = event_loop.time() - start_time

        logger.info('play note c:%s o:%s e:%s d:%s' % (count, onset, elapsed, delay_time))

        if delay_time > 0:
            delay.wait(timeout=delay_time)
        
        try:
            generator = player(ctx)
            for snd in generator:
                logger.info('play_sequence putting snd in BUF QUEUE')
                buf_q.put(snd)

        except Exception as e:
            logger.error('Error during %s generator render: %s' % (ctx.instrument_name, e))

        if ctx.stop_all.is_set() or ctx.stop_me.is_set():
            break

        count += 1

    delay.wait(timeout=len(snd)/snd.samplerate)
    done_playing_event.set()

def start_voice(event_loop, executor, renderer, ctx, buf_q, play_q):
    ctx.running.set()
    logger.info('start voice %s' % renderer)

    loop = False
    if hasattr(renderer, 'loop'):
        loop = renderer.loop

    logger.info('loop %s' % loop)

    if hasattr(renderer, 'before'):
        # blocking before callback makes
        # its results available to voices
        ctx.before = renderer.before(ctx)

    if hasattr(renderer, 'before_async'):
        # async before callback may write to 
        # ctx bus or just do something async
        event_loop.run_in_executor(executor, renderer.before_async, ctx)

    # find all play methods
    players = set()

    # The simplest case is a single play method 
    # with an optional onset list or callback
    if hasattr(renderer, 'play'):
        onsets = getattr(renderer, 'onsets', None)
        players.add((renderer.play, onsets))

    # Play methods can also be registered via 
    # an @player.init decorator, which also registers 
    # an optional onset list or callback
    if hasattr(renderer, 'player') \
        and hasattr(renderer.player, 'players') \
        and isinstance(renderer.player.players, set):
        players |= renderer.player.players

    logger.info('players %s' % players)

    try:
        done_playing_event = threading.Event()
        logger.info(done_playing_event)
    except Exception as e:
        logger.error(e)

    count = 0
    for player, onsets in players:
        if onsets is None:
            onsets = [0]
            #event_loop.run_in_executor(executor, play_stream, player, ctx, done_playing_event)
            
        logger.info('scheduling player onsets %s %s %s' % (count, player, onsets))
        try:
            event_loop.run_in_executor(executor, play_sequence, buf_q, event_loop, player, ctx, onsets, done_playing_event)
        except Exception as e:
            logger.error('error calling play_sequence: %s' % e)

        count += 1

    # add done callback to the last scheduled future
    logger.info('waiting for final future to complete')
    done_playing_event.wait()
    logger.info('future completed')
    ctx.running.clear()

    if hasattr(renderer, 'done'):
        logger.info('running player done callback')
        event_loop.run_in_executor(executor, renderer.done, ctx)

    logger.info('done playing')
    try:
        if loop:
            msg = [ctx.instrument_name, ctx.get_params()]
            logger.error('retrigger msg %s' % msg)
            play_q.put(msg)
            logger.error('put msg %s' % msg)
    except Exception as e:
        logger.error(e)

