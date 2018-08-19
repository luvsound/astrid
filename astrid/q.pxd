from .pthread cimport *

cdef struct MSGNode:
    # Messages translated from zmq: play, load, etc
    # Passed from main Q to msg handler Q based on msgtype.
    int msgtype
    void* params

cdef struct Q:
    N* head
    N* tail
    N* current
    pthread_mutex_t* pop_lock
    pthread_mutex_t* push_lock
    pthread_cond_t* empty_cond

cdef struct N:
    N* prev
    N* next
    void* data

cdef Q* q_init() nogil
cdef N* q_pop(Q* q) nogil
cdef void q_push(Q* q, N* node) nogil
cdef void q_destroy(Q* q) nogil

cdef N* msgnode_init(int msgtype, void* params) nogil

