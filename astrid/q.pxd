from pippi.soundbuffer cimport SoundBuffer
from .pthread cimport *
from .mqueue cimport *

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

cdef struct MSGNode:
    # Messages translated from zmq: play, load, etc
    # Passed from main Q to msg handler Q based on msgtype.
    int msgtype
    void* params

cdef struct BufQ:
    N* head
    N* tail
    N* current
    pthread_mutex_t* lock

cdef struct N:
    N* prev
    N* next
    void* data


cdef BufQ* bufq_init() nogil
cdef N* bufq_pop(BufQ* q) nogil
cdef void bufq_push(BufQ* q, N* node) nogil
cdef void bufq_destroy(BufQ* q) nogil

cdef N* msgnode_init(int msgtype, void* params) nogil
cdef N* bufnode_init(SoundBuffer snd, double onset)

cdef void mix_block(BufNode* node, double* out, int blocksize) nogil
cdef void mix_bufnodes(BufQ* q, double* out, int blocksize) nogil
cdef double[:,:] to_array(double* snd, int channels, int samplerate, int blocksize)
cdef double[:,:] mixed(BufQ* q, int channels, int samplerate, int blocksize)
