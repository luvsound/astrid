from libc.stdlib cimport malloc, calloc, free
import numpy as np

cdef BufQ* bufq_init() nogil:
    cdef BufQ* q = <BufQ*>malloc(sizeof(BufQ))
    pthread_mutex_init(q.lock, NULL)
    return q

cdef void bufq_destroy(BufQ* q) nogil:
    pthread_mutex_destroy(q.lock)
    free(q)

cdef N* bufq_pop(BufQ* q) nogil:
    cdef N* node = q.tail
    pthread_mutex_lock(q.lock)
    q.tail = node.prev
    if q.tail != NULL:
        q.tail.next = NULL
    node.prev = NULL
    pthread_mutex_unlock(q.lock)
    return node

cdef void bufq_push(BufQ* q, N* node) nogil:
    pthread_mutex_lock(q.lock)
    node.prev = NULL
    node.next = q.head
    if q.head != NULL:
        q.head.prev = node
    q.head = node
    pthread_mutex_unlock(q.lock)


cdef N* msgnode_init(int msgtype, void* params) nogil:
    cdef N* node = <N*>malloc(sizeof(N))
    cdef MSGNode* msgnode = <MSGNode*>malloc(sizeof(MSGNode))
    msgnode.msgtype = msgtype
    msgnode.params = params
    node.data = <void*>msgnode
    return node


cdef N* bufnode_init(SoundBuffer snd, double onset):
    cdef N* node = <N*>malloc(sizeof(N))
    cdef BufNode* bufnode = <BufNode*>malloc(sizeof(BufNode))
    cdef int length = len(snd)
    cdef int channels = snd.channels
    cdef int i = 0
    cdef int j = 0

    bufnode.snd = <double*>calloc(length * channels, sizeof(double))
    bufnode.channels = channels
    bufnode.samplerate = <int>snd.samplerate
    bufnode.length = length
    bufnode.onset = onset
    bufnode.pos = 0

    for i in range(length):
        for j in range(channels):
            bufnode.snd[i * channels + j] = snd.frames[i][j]

    node.data = <void*>bufnode

    return node


cdef void mix_block(BufNode* node, double* out, int blocksize) nogil:
    cdef int i = 0
    cdef int c = 0

    for i in range(blocksize):
        if node.pos < node.length:
            for c in range(node.channels):
                out[i * node.channels + c] += node.snd[node.pos * node.channels + c]
        else:
            break
        node.pos += 1


cdef void mix_bufnodes(BufQ* q, double* out, int blocksize) nogil:
    pthread_mutex_lock(q.lock)
    cdef N* current = q.head 
    pthread_mutex_unlock(q.lock)

    cdef BufNode* buf = <BufNode*>current.data

    while current != NULL:
        if buf.pos < buf.length:
            mix_block(buf, out, blocksize)
            
        current = current.next
        if current != NULL:
            buf = <BufNode*>current.data

cdef double[:,:] to_array(double* snd, int channels, int samplerate, int blocksize):
    cdef int i = 0
    cdef int c = 0
    cdef double[:,:] out = np.zeros((blocksize, channels))

    for i in range(blocksize):
        for c in range(channels):
            out[i][c] = snd[i * channels * c]
    free(snd)
    return out


cdef double[:,:] mixed(BufQ* q, int channels, int samplerate, int blocksize):
    cdef double* out = <double*>calloc(blocksize * channels, sizeof(double))
    mix_bufnodes(q, out, blocksize)
    return to_array(out, channels, samplerate, blocksize)

