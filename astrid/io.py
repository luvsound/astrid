import asyncio
import collections
from concurrent.futures import ThreadPoolExecutor
import logging
from logging.handlers import SysLogHandler
import queue
import threading
import time
import warnings

import numpy as np
from service import find_syslog
import sounddevice as sd
from aubio import pitch

from astrid import server
from pippi.soundbuffer import SoundBuffer

warnings.simplefilter('always')
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('astrid')
logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))

def pitch_tracker(bus, shutdown_signal, sr=44100, channels=1):
    window_size = 4096
    hop_size = 512
    tolerance = 0.8

    tracker = pitch('yin', window_size, hop_size, sr)
    tracker.set_unit('freq')
    tracker.set_tolerance(tolerance)

    with sd.Stream(channels=channels, samplerate=sr, dtype='float32') as stream:
        while True:
            if shutdown_signal.is_set():
                break

            snd, _ = stream.read(hop_size)
            p = tracker(snd.flatten())[0]
            if tracker.get_confidence() >= tolerance:
                setattr(bus, 'input_pitch', p)

def envelope_follower(bus, shutdown_signal, sr=44100, channels=1, window_size=None):
    if window_size is None:
        window_size = 0.015

    window_size = sr // window_size
    with sd.Stream(channels=channels, samplerate=sr, dtype='float32') as stream:
        while True:
            if shutdown_signal.is_set():
                break

            snd, _ = stream.read(window_size)
            a = np.amax(snd.flatten())
            logger.info('amplitude %s' % a)
            setattr(bus, 'input_amp', a)

def input_buffer(bus, shutdown_signal, sr=44100, channels=2):
    logger.info('starting input buffer rec')
    with sd.Stream(channels=channels, samplerate=sr, dtype='float32') as stream:
        while True:
            if shutdown_signal.is_set():
                break

            snd, _ = stream.read(sr)
            try:
                snd = SoundBuffer(frames=snd, channels=channels, samplerate=sr)
            except Exception as e:
                logger.error(e)

            setattr(bus, 'input_buffer', snd)

def play_stream(player, ctx):
    """ Blocking loop over renderer generator, 
        good for streams and non-overlapping sequences 
        of unknown segment lengths
    """
    generator = player(ctx)
    with sd.Stream(channels=2, samplerate=44100, dtype='float32') as stream:
        for snd in generator:
            stream.write(np.asarray(snd.frames, dtype='float32'))
            if ctx.stop_all.is_set() or ctx.stop_me.is_set():
                break

def oneshot(snd):
    """ Oneshot blocking playback
    """
    with sd.Stream(channels=snd.channels, samplerate=snd.samplerate, dtype='float32') as stream:
        stream.write(np.asarray(snd.frames, dtype='float32'))

def play_sequence(event_loop, executor, player, ctx, onsets):
    """ Schedule a sequence of overlapping oneshots
    """
    if not isinstance(onsets, collections.Iterable):
        try: 
            onsets = onsets(ctx)
        except Exception as e:
            logger.error('Onset callback failed with msg %s' % e)

    delay = threading.Event()
    generator = player(ctx)

    count = 0
    start_time = event_loop.time()
    for snd in generator:
        onset = onsets[count % len(onsets)]
        elapsed = event_loop.time() - start_time
        delay_time = onset - elapsed

        if delay_time > 0:
            delay.wait(timeout=delay_time)

        event_loop.run_in_executor(executor, oneshot, snd)

        if ctx.stop_all.is_set() or ctx.stop_me.is_set():
            ctx.running.clear()
            break

        count += 1

def start_voice(event_loop, executor, renderer, ctx):
    ctx.running.set()

    if hasattr(renderer, 'before'):
        # before callback blocks so it can make its 
        # results available to voices
        # TODO maybe an additional async before_noblock
        # or something would be nice, too, with results
        # sent to the bus instead.
        ctx.before = renderer.before(ctx)

    loop = False
    if hasattr(renderer, 'loop'):
        loop = renderer.loop

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

    for player, onsets in players:
        if onsets is not None:
            try:
                event_loop.run_in_executor(executor, play_sequence, event_loop, executor, player, ctx, onsets)
            except Exception as e:
                logger.error(e)
        else:
            event_loop.run_in_executor(executor, play_stream, player, ctx)

    if hasattr(renderer, 'done'):
        # FIXME run callbacks in thread pool
        # FIXME trigger this with a signal / done callback
        renderer.done(ctx)

    # FIXME looping should happen via done callback...?
    """
    if loop:
        msg = [server.PLAY_INSTRUMENT, ctx.instrument_name, ctx.params]
        logger.info('retrigger msg %s' % msg)
        messg_q.put(msg)
    """

