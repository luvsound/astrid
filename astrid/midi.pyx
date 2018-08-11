import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
import threading
import mido
import math
import time

from pippi import tune
from . import client
from .logger import logger

MIDI_MSG_NOTE_TEMPLATE = 'midi-message-{device}-note-{note}'
MIDI_MSG_CC_TEMPLATE = 'midi-message-{device}-cc-{cc}'
MIDI_LISTENER_KEY_TEMPLATE = '{}-midi-listener'

def find_device(substr, input_device=True):
    try:
        if input_device:
            devices = mido.get_input_names()
        else:
            devices = mido.get_output_names()

        for device_name in devices:
            if substr in device_name:
                return device_name
    except RuntimeError as e:
        logger.error('Could not query for devices: %s' % e)

    return None


class MidiDeviceBucket:
    def __init__(self, device=None, bus=None, mapping=None):
        self._device = device # full device / port name
        self._bus = bus
        self._mapping = mapping

    def __getattr__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        if not self._device:
            return default

        if self._mapping is not None \
        and key in self._mapping:
            key = self.__mapping[key]

        return getattr(self._bus, MIDI_MSG_CC_TEMPLATE.format(device=self._device, cc=key[2:]), default)

    def getnote(self, key, default=None):
        if not self._device:
            return default

        if self._mapping is not None \
        and key in self._mapping:
            key = self.__mapping[key]

        return getattr(self._bus, MIDI_MSG_NOTE_TEMPLATE.format(device=self._device, note=key), default)


cdef class MidiBucket:
    def __init__(self, devices, mappings, bus):
        self.bus = bus
        self.devices = self.map_device_buckets(devices, mappings)
        self.dummy = MidiDeviceBucket() # empty fallback

    def __call__(self, device_alias):
        return self.devices.get(device_alias, self.dummy)

    def map_device_buckets(self, devices=None, mappings=None):
        if devices is None:
            return {}

        device_buckets = {}
        for device_alias in devices:
            mapping = mappings.get(device_alias, None)
            device_fullname = find_device(device_alias)
            device_buckets[device_alias] = MidiDeviceBucket(device_fullname, self.bus, mapping)

        return device_buckets

class PlayNote(threading.Thread):
    def __init__(self, out, freq, amp, length):
        self.out = out
        self.freq = freq
        self.amp = amp
        self.length = length

        super().__init__()

    def run(self):
        note = int(math.floor(math.log(self.freq/440.0, 2) * 12 + 69))
        velocity = int(self.amp * 127)
        logger.info('MidiOutput ON %s %s %s %s %s' % (self.freq, self.amp, self.length, note, velocity))

        m = mido.Message('note_on', note=note, velocity=velocity)
        self.out.send(m)
        time.sleep(self.length)
        m = mido.Message('note_off', note=note)
        self.out.send(m)
        logger.info('MidiOutput OFF %s %s %s %s %s' % (self.freq, self.amp, self.length, note, velocity))


class MidiOutput(mp.Process):
    def __init__(self, event_loop, event_q):
        super().__init__()
        self.event_loop = event_loop
        self.event_q = event_q
        #self.out = mido.open_output('MidiSport 2x2 MIDI 1')
        self.pool = ThreadPoolExecutor(max_workers=256)
        logger.info('MidiOutput started up')

    def run(self):
        while True:
            freq, amp, length = self.event_q.get()
            logger.info('Got MSG: MidiOutput %s %s %s' % (freq, amp, length))
            e = PlayNote(self.out, freq, amp, length)
            logger.info(type(e))
            e.start()
            #self.event_loop.run_in_executor(self.pool, self._play, freq, amp, length)

class MidiListener(mp.Process):
    def __init__(self, instrument_name, device, triggers, bus):
        super(MidiListener, self).__init__()
        self.client = client.AstridClient()
        self.instrument_name = instrument_name
        self.device = device
        self.bus = bus
        self.triggers = triggers
        self.name = 'astrid-%s-midi-listener' % instrument_name

    def run(self):
        with mido.open_input(self.device) as events:
            for msg in events:
                #logger.info('midi: %s %s' % (self.device, msg))
                if self.bus.stop_listening.is_set():
                    break

                if msg.type == 'note_on':
                    freq = tune.mtof(msg.note)
                    amp = msg.velocity / 127
                    setattr(self.bus, MIDI_MSG_NOTE_TEMPLATE.format(device=self.device, note=msg.note), amp)

                    if self.triggers is not None \
                    and (self.triggers == -1 or msg.note in self.triggers):
                        self.client.send_cmd(['play', self.instrument_name, {'freq': freq, 'amp': amp}])
 
                elif msg.type == 'control_change':
                    value = msg.value / 127.0
                    setattr(self.bus, MIDI_MSG_CC_TEMPLATE.format(device=self.device, cc=msg.control), value)

def start_listener(instrument):
    listener = None
    if hasattr(instrument.renderer, 'MIDI'):
        devices = []
        if isinstance(instrument.renderer.MIDI, list):
            devices = instrument.renderer.MIDI
        else:
            devices = [ instrument.renderer.MIDI ]

        for i, device in enumerate(devices):
            triggers = None
            if hasattr(instrument.renderer, 'TRIG'):
                if isinstance(instrument.renderer.TRIG, list):
                    try:
                        triggers = instrument.renderer.TRIG[i]
                    except IndexError:
                        pass
                else:
                    triggers = instrument.renderer.TRIG

            device = find_device(device)

            listener = MidiListener(instrument.name, device, triggers, instrument.bus)
            listener.start()

    return listener


if __name__ == '__main__':
    outputs = mido.get_output_names()
    inputs = mido.get_input_names()
    print(outputs, inputs)

