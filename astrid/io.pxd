from pippi.soundbuffer cimport SoundBuffer

cdef class BufferNode:
    cdef public SoundBuffer snd
    cdef public double start_time
    cdef public double onset
    cdef public int pos
    cdef public int done_playing
    cpdef double[:,:] next_block(BufferNode self, int block_size)

cdef void init_voice(object instrument, object params, object buf_q)
cdef tuple collect_players(object instrument)
