from aubio import pitch
import numpy as np
import threading
import queue

from .logger import logger
from . import names

def pitch_tracker(bus, read_q, response_q, shutdown_signal):
    logger.info('starting pitch tracker')
    window_size = 4096
    hop_size = bus.block_size
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
            p = tracker(buf.frames.base[:,0].astype('float32').flatten())[0]
            if tracker.get_confidence() >= tolerance:
                setattr(bus, 'input_pitch', p)
        except Exception as e:
            logger.error(e)

        delay.wait(timeout=wait_time)

def envelope_follower(bus, read_q, response_q, shutdown_flag):
    logger.info('started envelope follower')
    wait_time = 0.015
    delay = threading.Event()
    framelength = int(wait_time * bus.samplerate)

    while True:
        if shutdown_flag.is_set():
            break

        try:
            read_q.put((names.ENVELOPE_FOLLOWER, framelength))
            buf = response_q.get()
            input_amp = np.amax(buf.frames)
            setattr(bus, 'input_amp', input_amp)
        except Exception as e:
            logger.error(e)

        delay.wait(timeout=wait_time)



