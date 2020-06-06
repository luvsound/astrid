#cython: language_level=3

import redis
import msgpack
import numpy as np
from pippi.soundbuffer cimport SoundBuffer
from astrid.logger import logger

# Low density patterns at first, fill in down to fast pulse
# x              x     x              x  x         x 
#     x        x         x            x     x          x
# x  x  x  x  x  x  x  x  x  x  x  x  x  x  x  x  x  x
#
# etc
# Bugfixes only, plus this...
# Maybe better orchestration control of voices -- missing things like voice stopping, param updates, global values, etc
# Finish all instrument scripts & MIDI hookups
# Don't wory about structure, transitions too much

cdef class Sampler:
    def __cinit__(self):
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0)

    cpdef void write(Sampler self, str bank, SoundBuffer buf):
        self.redis.set(bank, msgpack.packb({
            'l': len(buf), 
            's': buf.samplerate, 
            'c': buf.channels,
            'f': bytes(buf.frames), 
        }))

    cpdef void dub(Sampler self, str bank, SoundBuffer buf):
        pass

    cpdef SoundBuffer read(Sampler self, str bank):
        s = msgpack.unpackb(self.redis.get(bank))
        #logger.info('READ %s' % s.keys())
        #return SoundBuffer()
        f = np.ndarray((s[b'l'], s[b'c']), dtype='d', buffer=bytearray(s[b'f']))
        return SoundBuffer(f, channels=s[b'c'], samplerate=s[b's'])

    cpdef bint has(Sampler self, str bank):
        return self.redis.exists(bank) > 0

    cpdef void clear(Sampler self, str bank):
        self.redis.unlink(bank)


    """
    cpdef void write(Sampler self, double[:,:] block):
        self.redis.lpush(self.name, bytes(block))
        self.redis.ltrim(self.name, 0, self.maxblocks-1)

    cpdef SoundBuffer read(Sampler self, double length, tuple channels=None, double offset=0):
        if channels is None:
            channels = (1,2)
        cdef int framelength = <int>(length * self.samplerate)
        cdef int numblocks = framelength // self.blocksize
        cdef double[:,:] out = np.zeros((framelength, len(channels)), dtype='d')  
        cdef double[:,:] block
        cdef int o = <int>(offset * self.samplerate) // self.blocksize
        o = min(o, (framelength - self.blocksize) // self.blocksize)
        cdef int i = (numblocks * self.blocksize) - self.blocksize
        for b in self.redis.lrange(self.name, o, o+numblocks-1):
            block = np.ndarray((self.blocksize, self.channels), dtype='d', buffer=bytearray(b))
            for j in range(self.blocksize):
                for c in range(len(channels)):
                    out[i+j,c] = block[j,channels[c]-1]

            i -= self.blocksize

        return SoundBuffer(out, channels=len(channels), samplerate=self.samplerate)
    """
