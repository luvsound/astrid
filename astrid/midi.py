import logging
from logging.handlers import SysLogHandler
import multiprocessing as mp

import mido
from service import find_syslog

from pippi import tune
from astrid import client

MIDI_MSG_NOTE_TEMPLATE = 'midi-message-{device}-note-{note}'
MIDI_MSG_CC_TEMPLATE = 'midi-message-{device}-cc-{cc}'
MIDI_LISTENER_KEY_TEMPLATE = '{}-midi-listener'

logger = logging.getLogger('astrid')
if not logger.handlers:
    logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
logger.setLevel(logging.DEBUG)

def find_device(substr, input_device=True):
    if input_device:
        devices = mido.get_input_names()
    else:
        devices = mido.get_output_names()

    for device_name in devices:
        if substr in device_name:
            return device_name

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

        return getattr(self._bus, MIDI_MSG_CC_TEMPLATE.format(device=self._device, cc=key), default)

    def getnote(self, key, default=None):
        if not self._device:
            return default

        if self._mapping is not None \
        and key in self._mapping:
            key = self.__mapping[key]

        return getattr(self._bus, MIDI_MSG_NOTE_TEMPLATE.format(device=self._device, note=key), default)


class MidiBucket:
    def __init__(self, devices, mappings, bus):
        logger.info((self, devices, mappings, bus))
        self.bus = bus
        self.devices = self.map_device_buckets(devices, mappings)
        self.dummy = MidiDeviceBucket() # empty fallback

    def __call__(self, device_alias):
        return self.devices.get(device_alias, self.dummy)

    def map_device_buckets(self, devices, mappings=None):
        logger.info((devices, mappings))
        device_buckets = {}
        for device_alias in devices:
            mapping = mappings.get(device_alias, None)
            device_buckets[device_alias] = MidiDeviceBucket(device_alias, self.bus, mapping)

        logger.info(device_buckets)
        return device_buckets


class MidiListener(mp.Process):
    def __init__(self, instrument_name, device, triggers, bus, stop_listening=None):
        super(MidiListener, self).__init__()
        logger.debug('MidiListener init')
        self.client = client.AstridClient()
        self.instrument_name = instrument_name
        self.device = device
        self.stop_listening = stop_listening
        self.bus = bus
        self.triggers = triggers

    def run(self):
        logger.debug('MidiListener run %s' % self.device)
        with mido.open_input(self.device) as events:
            logger.debug('waiting for events %s' % events)
            for msg in events:
                logger.debug('got msg %s' % msg)
                if self.stop_listening.is_set():
                    break

                if msg.type == 'note_on':
                    freq = tune.mtof(msg.note)
                    logger.debug('freq %s' % freq)
                    amp = msg.velocity / 127
                    logger.debug('amp %s' % amp)
                    logger.debug('freq amp %s %s' % (freq, amp))
                    setattr(self.bus, MIDI_MSG_NOTE_TEMPLATE.format(device=self.device, note=msg.note), amp)
                    logger.debug('got msg %s' % msg)

                    if self.triggers is not None \
                    and (self.triggers == -1 or msg.note in self.triggers):
                        logger.debug('sending play cmd %s' % msg)
                        self.client.send_cmd(['play', self.instrument_name, {'freq': freq, 'amp': amp}])
                        logger.debug('sent play cmd %s' % self.instrument_name)
 
                elif msg.type == 'control_change':
                    value = msg.value / 127
                    setattr(self.bus, MIDI_MSG_CC_TEMPLATE.format(device=self.device, cc=msg.control), value)

def start_listener(name, renderer, bus, stop_listening):
    listener = None
    if hasattr(renderer, 'MIDI'):
        logger.debug('has MIDI %s' % renderer.MIDI)

        devices = []
        if isinstance(renderer.MIDI, list):
            devices = renderer.MIDI
        else:
            devices = [ renderer.MIDI ]

        for i, device in enumerate(devices):
            triggers = None
            if hasattr(renderer, 'TRIG'):
                if isinstance(renderer.TRIG, list):
                    try:
                        triggers = renderer.TRIG[i]
                    except IndexError:
                        pass
                else:
                    triggers = renderer.TRIG

            logger.debug('MIDI device triggers %s %s' % (device, triggers))
            device = find_device(device)

            logger.debug('creating MidiListener %s %s %s' % (device, triggers, bus))
            listener = MidiListener(name, device, triggers, bus, stop_listening)
            logger.debug('starting listener')
            listener.start()

    return listener


if __name__ == '__main__':
    outputs = mido.get_output_names()
    inputs = mido.get_input_names()
    print(outputs, inputs)

