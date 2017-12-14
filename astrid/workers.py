import multiprocessing as mp
import threading
from concurrent.futures import ThreadPoolExecutor
import queue
import time

from . import io
from . import midi
from . import orc
from . import names
from .logger import logger

class RenderProcess(mp.Process):
    def __init__(self, 
            buf_q, 
            play_q, 
            load_q, 
            reply_q, 
            shutdown_flag,
            stop_all, 
            stop_listening, 
            bus,
            event_loop, 
            cwd
        ):

        super(RenderProcess, self).__init__()

        self.instruments = {}
        self.voices = []
        self.buf_q = buf_q
        self.play_q = play_q
        self.load_q = load_q
        self.reply_q = reply_q
        self.stop_all = stop_all
        self.shutdown_flag = shutdown_flag
        self.stop_listening = stop_listening
        self.bus = bus
        self.render_pool = ThreadPoolExecutor(max_workers=16)
        self.event_loop = event_loop
        self.cwd = cwd
        self.q = queue.Queue()
        self.name = 'astrid-render-process'

        # FIXME get from env
        self.channels = 2
        self.samplerate = 44100
        self.blocksize = 0
        self.latency = 'low'
        self.device = None

    def load_renderer(self, instrument_name, instrument_path):
        renderer = orc.load_instrument(instrument_name, instrument_path)
        logger.debug('render process load_renderer %s' % renderer)
        self.instruments[instrument_name] = renderer
        return renderer

    def get_renderer(self, instrument_name):
        renderer = self.instruments.get(instrument_name, None)         
        if renderer is None:
            instrument_path = os.path.join(self.cwd, names.ORC_DIR, '%s.py' % instrument_name)
            renderer = self.load_renderer(instrument_name, instrument_path)
        logger.debug('render process get_renderer %s' % renderer)
        return renderer

    def run(self):
        logger.debug('render process init')

        def wait_for_shutdown(q, shutdown_flag):
            shutdown_flag.wait()
            q.put((names.SHUTDOWN, None))
            logger.debug('render process put shutdown')

        def wait_for_loads(load_q, q, shutdown_flag):
            while True:
                msg = load_q.get()
                logger.info('GOT LOAD')
                logger.info(msg)

                if msg == names.SHUTDOWN:
                    logger.debug('render process shutdown load queue')
                    break

                q.put((names.LOAD_INSTRUMENT, msg))
                logger.debug('render process put load %s %s' % msg)

                # dumb way to try to keep it to one load per process
                # FIXME this probably doesn't always work
                time.sleep(1)

        def wait_for_plays(play_q, q, shutdown_flag):
            while True:
                msg = play_q.get()

                if msg == names.SHUTDOWN:
                    logger.debug('render process shutdown play queue')
                    break

                q.put((names.PLAY_INSTRUMENT, msg))
                logger.debug('render process put play %s' % msg)

        load_listener = threading.Thread(name='astrid-load-queue-listener', target=wait_for_loads, args=(self.load_q, self.q, self.shutdown_flag))
        load_listener.start()

        play_listener = threading.Thread(name='astrid-play-queue-listener', target=wait_for_plays, args=(self.play_q, self.q, self.shutdown_flag))
        play_listener.start()

        shutdown_listener = threading.Thread(name='astrid-render-shutdown-listener', target=wait_for_shutdown, args=(self.q, self.shutdown_flag))
        shutdown_listener.start()

        try:
            while True:
                logger.debug('render process waiting for messages')
                action, cmd = self.q.get()
                logger.debug('got message %s %s' % (action, cmd))

                if action == names.LOAD_INSTRUMENT:
                    logger.debug('render process LOAD_INSTRUMENT %s %s' % cmd)
                    self.load_renderer(*cmd)

                elif action == names.PLAY_INSTRUMENT:
                    logger.debug('render process PLAY_INSTRUMENT %s' % cmd)
                    instrument_name = cmd[0]
                    params = None
                    if len(cmd) > 1:
                        params = cmd[1]

                    renderer = self.get_renderer(instrument_name)
                    if renderer is None:
                        logger.error('No renderer loaded for %s' % instrument_name)
                        continue

                    logger.debug('starting voice with inst %s and params %s' % (renderer, params))

                    device_aliases = []
                    midi_maps = {}

                    if hasattr(renderer, 'MIDI'): 
                        if isinstance(renderer.MIDI, list):
                            device_aliases = renderer.MIDI
                        else:
                            device_aliases = [ renderer.MIDI ]

                    for i, device in enumerate(device_aliases):
                        mapping = None
                        if hasattr(renderer, 'MAP'):
                            if isinstance(renderer.MAP, list):
                                try:
                                    mapping = renderer.MAP[i]
                                except IndexError:
                                    pass
                            else:
                                mapping = renderer.MAP

                            midi_maps[device] = mapping 

                        logger.debug('MIDI device mapping %s %s' % (device, mapping))

                    ctx = orc.EventContext(
                                params=params, 
                                instrument_name=instrument_name, 
                                running=threading.Event(),
                                stop_all=self.stop_all, 
                                stop_me=threading.Event(),
                                bus=self.bus, 
                                midi_devices=device_aliases, 
                                midi_maps=midi_maps, 
                            )

                    logger.debug('ctx %s' % ctx)

                    io.start_voice(self.event_loop, self.render_pool, renderer, ctx, self.buf_q, self.play_q)

                elif action == names.SHUTDOWN:
                    logger.debug('got shutdown')
                    break
        except Exception as e:
            logger.error(e)
     
        self.render_pool.shutdown(wait=True)
        load_listener.join()
        play_listener.join()
        shutdown_listener.join()
        logger.debug('render process finished')


