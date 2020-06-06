#cython: language_level=3

import redis
import numpy as np
from pippi.soundbuffer cimport SoundBuffer
from .logger import logger

cdef class Circle:
    def __cinit__(self, str name='inputbuffer'):
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.blocksize = int(self.redis.get('BLOCKSIZE'))
        self.samplerate = int(self.redis.get('SAMPLERATE'))
        self.channels = int(self.redis.get('CHANNELS'))
        self.maxblocks = <int>(self.samplerate * 30) // self.blocksize
        self.name = name

    cpdef void add(Circle self, double[:,:] block):
        self.redis.lpush(self.name, bytes(block))
        self.redis.ltrim(self.name, 0, self.maxblocks-1)

    cpdef SoundBuffer read(Circle self, double length, tuple channels=None, double offset=0):
        if channels is None:
            channels = (0,)
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

        return SoundBuffer(out, channels=len(channels), samplerate=self.samplerate).remix(1).remix(2) # FIXME channel outs
