from pippi.soundbuffer cimport SoundBuffer
from .q cimport *

cdef struct BufNode:
    # Stack of currently playing buffers, 
    # looped over in the main jack callback 
    # and mixed into the output stream.
    double* snd
    int channels
    int samplerate
    int length
    double onset
    int pos

cdef N* bufnode_init(SoundBuffer snd, double onset)

cdef void mix_block(BufNode* node, double* out, int blocksize) nogil
cdef void mix_bufnodes(Q* q, double* out, int blocksize) nogil
cdef double[:,:] to_array(double* snd, int channels, int samplerate, int blocksize)
cdef double[:,:] mixed(Q* q, int channels, int samplerate, int blocksize)
