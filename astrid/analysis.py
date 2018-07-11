#from aubio import pitch
import numpy as np
import threading
import queue

from .logger import logger
from . import names
from .mixer import StreamContextView

def pitch_tracker(bus, read_q, response_q, shutdown_signal):
    pass
    """
    logger.info('starting pitch tracker %s %s' % (bus.block_size, bus.samplerate))
    window_size = 4096
    hop_size = 4096
    tolerance = 0.8
    wait_time = (bus.samplerate / hop_size) / 1000
    delay = threading.Event()

    tracker = pitch('yin', window_size, hop_size, bus.samplerate)
    tracker.set_unit('freq')
    tracker.set_tolerance(tolerance)

    while True:
        if shutdown_signal.is_set():
            break

        try:
            read_q.put((names.PITCH_TRACKER, hop_size))
            buf = response_q.get()
            #buf = stream_ctx.read(hop_size, 0)
            p = tracker(buf.frames.base[:,0].astype('float32').flatten())[0]
            #logger.info('')
            #logger.info(wait_time)
            #logger.info(p)
            #logger.info(tracker.get_confidence())
            if tracker.get_confidence() >= tolerance:
                #logger.info(p)
                setattr(bus, 'input_pitch', p)
        except Exception as e:
            logger.error(e)

        delay.wait(timeout=wait_time)
    """

def envelope_follower(bus, read_q, response_q, shutdown_flag):
    logger.info('started envelope follower')
    wait_time = 0.015
    delay = threading.Event()
    #delay.wait(timeout=2)
    framelength = int(wait_time * bus.samplerate)
    #stream_ctx = StreamContextView(stream_ctx_ptr)
    #logger.error('ctx ptr: %s' % stream_ctx_ptr)
    #logger.error('ctx channels: %s ctx samplerate: %s' % (stream_ctx.channels, stream_ctx.samplerate))
    #logger.error('ctx read 2: %s' % stream_ctx.read(2, 0))

    while True:
        if shutdown_flag.is_set():
            break

        try:
            read_q.put((names.ENVELOPE_FOLLOWER, framelength))
            buf = response_q.get()

            #buf = stream_ctx.read(framelength, 0)
            input_amp = np.amax(buf.frames)
            #logger.info(input_amp)
            setattr(bus, 'input_amp', input_amp)
        except Exception as e:
            logger.error(e)

        delay.wait(timeout=wait_time)



