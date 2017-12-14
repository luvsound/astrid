from __future__ import absolute_import
import collections
import threading
import queue

from .logger import logger
from . import names
from .mixer import AstridMixer

   
class AudioStream(threading.Thread):
    def __init__(self, 
            buf_q, 
            read_q, 
            envelope_follower_response_q, 
            pitch_tracker_response_q, 
            shutdown_flag, 
            block_size=64, 
            channels=2, 
            samplerate=44100
        ):
        super(AudioStream, self).__init__()
        self.q = queue.Queue()
        self.buf_q = buf_q
        self.read_q = read_q
        self.envelope_follower_response_q = envelope_follower_response_q
        self.pitch_tracker_response_q = pitch_tracker_response_q
        self.block_size = block_size
        self.channels = channels
        self.samplerate = samplerate
        self.shutdown_flag = shutdown_flag

    def run(self):
        def wait_for_bufs(buf_q, q, shutdown_flag):
            while True:
                msg = buf_q.get()
                logger.info(msg)

                if msg == names.SHUTDOWN:
                    logger.debug('audiostream shutdown buf queue')
                    break

                q.put((names.ADD_BUFFER, msg))
                logger.debug('audiostream put buf')

        def wait_for_reads(read_q, q, shutdown_flag):
            while True:
                msg = read_q.get()

                if msg == names.SHUTDOWN:
                    logger.debug('audiostream shutdown read queue')
                    break

                q.put((names.READ_INPUT, msg))
                logger.debug('audiostream put read')

        def wait_for_shutdown(q, shutdown_flag):
            shutdown_flag.wait()
            q.put((names.SHUTDOWN, None))
            logger.debug('audiostream put shutdown')

        buf_listener = threading.Thread(name='astrid-buf-queue-listener', target=wait_for_bufs, args=(self.buf_q, self.q, self.shutdown_flag))
        buf_listener.start()

        read_listener = threading.Thread(name='astrid-read-queue-listener', target=wait_for_reads, args=(self.read_q, self.q, self.shutdown_flag))
        read_listener.start()

        shutdown_listener = threading.Thread(name='astrid-render-shutdown-listener', target=wait_for_shutdown, args=(self.q, self.shutdown_flag))
        shutdown_listener.start()

        mixer = AstridMixer(self.block_size, self.channels, self.samplerate)
        logger.info('started audiostream QUEUE')

        while True:
            action, data = self.q.get()
            if action == names.SHUTDOWN:
                break

            elif action == names.ADD_BUFFER:
                try:
                    logger.info('adding %s to ASTRID MIXER' % data)
                    mixer.add(data)
                except Exception as e:
                    logger.error(e)

            elif action == names.READ_INPUT:
                try:
                    target, frames = data
                    buf = mixer.read(frames)
                    if target == names.ENVELOPE_FOLLOWER:
                        self.envelope_follower_response_q.put(buf)
                    elif target == names.PITCH_TRACKER:
                        self.pitch_tracker_response_q.put(buf)

                except Exception as e:
                    logger.error(e)

        mixer.shutdown()
        buf_listener.join()
        read_listener.join()
        shutdown_listener.join()


def play_sequence(buf_q, player, ctx, onsets, done_playing_event):
    """ Play a sequence of overlapping oneshots
    """
    if not isinstance(onsets, collections.Iterable):
        try: 
            onsets = onsets(ctx)
        except Exception as e:
            logger.error('Onset callback failed with msg %s' % e)

    delay = threading.Event()

    count = 0
    logger.debug('playing %s onsets %s' % (len(onsets), onsets))
    for onset in onsets:
        delay_time = onset
        logger.info('play note c:%s o:%s d:%s' % (count, onset, delay_time))

        if delay_time > 0:
            delay.wait(timeout=delay_time)
        
        try:
            generator = player(ctx)
            for snd in generator:
                buf_q.put(snd)

        except Exception as e:
            logger.error('Error during %s generator render: %s' % (ctx.instrument_name, e))

        if ctx.stop_all.is_set() or ctx.stop_me.is_set():
            break

        count += 1

    delay.wait(timeout=snd.dur)
    done_playing_event.set()

def start_voice(event_loop, executor, renderer, ctx, buf_q, play_q):
    ctx.running.set()
    logger.debug('start voice %s' % renderer)

    loop = False
    if hasattr(renderer, 'loop'):
        loop = renderer.loop

    logger.debug('loop %s' % loop)

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
            
        logger.debug('scheduling player onsets %s %s %s' % (count, player, onsets))
        try:
            event_loop.run_in_executor(executor, play_sequence, buf_q, player, ctx, onsets, done_playing_event)
        except Exception as e:
            logger.error('error calling play_sequence: %s' % e)

        count += 1

    logger.debug('waiting for play to complete')
    done_playing_event.wait()
    logger.debug('got done playing event')
    ctx.running.clear()

    if hasattr(renderer, 'done'):
        logger.info('running player done callback')
        event_loop.run_in_executor(executor, renderer.done, ctx)

    logger.info('done playing')
    try:
        if loop:
            msg = [ctx.instrument_name, ctx.get_params()]
            logger.debug('retrigger %s' % msg)
            play_q.put(msg)
    except Exception as e:
        logger.error(e)

