#cython: language_level=3

from pippi.soundbuffer cimport SoundBuffer

cdef class Sampler:
    cdef object redis

    cpdef void write(Sampler self, str bank, SoundBuffer buf)
    cpdef void dub(Sampler self, str bank, SoundBuffer buf)
    cpdef SoundBuffer read(Sampler self, str bank)
    cpdef bint has(Sampler self, str bank)
    cpdef void clear(Sampler self, str bank)
