import multiprocessing as mp

import numpy as np
import sounddevice as sd
import pyaudio
import zmq

from . import orc

BROADCAST_PORT = 9191
VOICE_STOP_CMD = 'STOP'
ALL_VOICES = 'ALL'

class IOManager:
    def __init__(self):
        self.manager = mp.Manager()
        self.session = self.manager.Namespace()
        self.voices = {}
        self.last_voice_id = 0

        self.context = zmq.Context()
        self.sender = self.context.socket(zmq.PUSH)
        self.sender.bind('tcp://*:{}'.format(BROADCAST_PORT))

    def get_voice_id(self):
        self.last_voice_id += 1
        return self.last_voice_id

    def open_stream(self, samplerate=44100, channels=2, device='default'):
        p = pyaudio.PyAudio()
        out = p.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=samplerate,
            output=True
        )

        return p, out

    def _play(self, name, params=None, voice_id=None):
        instrument = orc.load(name)
        context = zmq.Context()
        receiver = context.socket(zmq.PULL)
        receiver.connect('tcp://localhost:{}'.format(BROADCAST_PORT))

        playing = True

        while playing:
            instrument_generator = instrument.play(params)
            for sound in instrument_generator:
                p, out = self.open_stream(sound.samplerate, sound.channels)
                sound = np.ravel(sound.frames.astype(np.float32)).tostring()
                out.write(sound)
                out.close()
                p.terminate()

            try:
                cmds = receiver.recv(zmq.DONTWAIT)
                print(cmds, type(cmds))
                cmds = str(cmds).split(' ')
                if cmds[0] == str(voice_id) \
                    and cmds[1] == VOICE_STOP_CMD:
                    print('playing=False')
                    playing = False

            except zmq.Again as e:
                print('zmq.Again', e)
                pass


    def play(self, name, params):
        voice_id = self.get_voice_id()
        self.voices[voice_id] = (name, params, mp.Process(target=self._play, args=(name, params, voice_id)))

        playing = getattr(self.session, 'playing', {})
        playing[voice_id] = True
        setattr(self.session, 'playing', playing)
        self.voices[voice_id][2].start()

        return voice_id

    def stop_voice(self, voice_id):
        self.sender.send_string(' '.join([voice_id, VOICE_STOP_CMD]))

    def stop_all(self):
        self.sender.send_string(' '.join([ALL_VOICES, VOICE_STOP_CMD]))

    def quit(self):
        self.sender.close()
        self.context.destroy()
