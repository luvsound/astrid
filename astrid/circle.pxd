#cython: language_level=3

from pippi.soundbuffer cimport SoundBuffer

cdef class Circle:
    cdef object redis
    cdef int blocksize
    cdef int samplerate
    cdef int channels
    cdef int maxblocks
    cdef str name

    cpdef void add(Circle self, double[:,:] block)
    cpdef SoundBuffer read(Circle self, double length, tuple channels=*, double offset=*)
