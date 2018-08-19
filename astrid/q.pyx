from libc.stdlib cimport malloc, calloc, free

cdef Q* q_init() nogil:
    cdef Q* q = <Q*>malloc(sizeof(Q))
    pthread_mutex_init(q.push_lock, NULL)
    pthread_mutex_init(q.pop_lock, NULL)
    pthread_cond_init(q.empty_cond, NULL)
    return q

cdef void q_destroy(Q* q) nogil:
    pthread_mutex_destroy(q.push_lock)
    pthread_mutex_destroy(q.pop_lock)
    pthread_cond_destroy(q.empty_cond)
    free(q)

cdef N* q_pop(Q* q) nogil:
    cdef N* node = q.tail
    pthread_mutex_lock(q.pop_lock)
    while q.tail != NULL:
        pthread_cond_wait(q.empty_cond, q.pop_lock)
    q.tail = node.prev
    if q.tail != NULL:
        q.tail.next = NULL
    node.prev = NULL
    pthread_mutex_unlock(q.pop_lock)
    return node

cdef void q_push(Q* q, N* node) nogil:
    pthread_mutex_lock(q.push_lock)
    node.prev = NULL
    node.next = q.head
    if q.head != NULL:
        q.head.prev = node
    q.head = node
    pthread_mutex_unlock(q.push_lock)

cdef N* msgnode_init(int msgtype, void* params) nogil:
    cdef N* node = <N*>malloc(sizeof(N))
    cdef MSGNode* msgnode = <MSGNode*>malloc(sizeof(MSGNode))
    msgnode.msgtype = msgtype
    msgnode.params = params
    node.data = <void*>msgnode
    return node

