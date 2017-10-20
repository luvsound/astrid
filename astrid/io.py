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

from . import server

warnings.simplefilter('always')
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('astrid')
logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))

def sequenced(renderer, ctx):
    generator = renderer.play(ctx)
    with sd.Stream(channels=2, samplerate=44100, dtype='float32') as stream:
        logger.info('Stream %s' % stream)
        for snd in generator:
            logger.info('Writing sound to stream %s' % snd)
            stream.write(np.asarray(snd.frames, dtype='float32'))
            if ctx.stop_all.is_set() or ctx.stop_me.is_set():
                break

def oneshot(snd, onset, delay):
    if onset > 0:
        delay.wait(timeout=onset)

    with sd.Stream(channels=2, samplerate=44100, dtype='float32') as stream:
        logger.info('Stream %s' % stream)
        stream.write(np.asarray(snd.frames, dtype='float32'))

def start_voice(event_loop, executor, renderer, ctx):
    logger.info('start voice %s' % ctx)
    ctx.running.set()

    if hasattr(renderer, 'before'):
        ctx.before = renderer.before(ctx)

    loop = False
    if hasattr(renderer, 'loop'):
        loop = renderer.loop

    onsets = None
    if hasattr(renderer, 'onsets'):
        if isinstance(renderer.onsets, collections.Iterable):
            onsets = renderer.onsets
        else:
            try: 
                onsets = renderer.onsets(ctx)
            except TypeError:
                pass

    futures = []
    if onsets is not None:
        delay = threading.Event()
        generator = renderer.play(ctx)
        count = 0
        for snd in generator:
            onset = onsets[count % len(onsets)]
            future = event_loop.run_in_executor(executor, oneshot, snd, onset, delay)
            futures += [ future ]
            count += 1
            if ctx.stop_all.is_set() or ctx.stop_me.is_set():
                ctx.running.clear()
                break

    else:
        future = event_loop.run_in_executor(executor, sequenced, renderer, ctx)
        futures += [ future ]

    if hasattr(renderer, 'done'):
        renderer.done(ctx)

    """
    if loop:
        msg = [server.PLAY_INSTRUMENT, ctx.instrument_name, ctx.params]
        logger.debug('retrigger msg %s' % msg)
        messg_q.put(msg)
    """

    return futures

