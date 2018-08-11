cdef extern from "<pthread.h>" nogil:
    ctypedef int pthread_t
    ctypedef struct pthread_attr_t:
        pass

    ctypedef struct pthread_mutexattr_t:
        pass

    ctypedef struct pthread_mutex_t:
        pass

    int pthread_mutex_init(pthread_mutex_t* mutex, pthread_mutexattr_t* mutexattr)
    int pthread_mutex_lock(pthread_mutex_t* mutex)
    int pthread_mutex_unlock(pthread_mutex_t* mutex)
    int pthread_mutex_destroy(pthread_mutex_t* mutex)
    int pthread_join(pthread_t thread, void **value_ptr)
    int pthread_create(pthread_t *thread, const pthread_attr_t *attr,
        void *(*start_routine)(void*), void *arg)
