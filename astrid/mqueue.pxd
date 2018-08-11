from posix.types cimport mode_t

cdef extern from "<mqueue.h>" nogil:
    ctypedef unsigned long mqd_t
    ctypedef struct mq_attr:
        pass

    int mq_close(mqd_t mqdes)
    int mq_getattr(mqd_t mqdes, mq_attr* attr)
    mqd_t mq_open(const char* name, int oflags, mode_t mode, mq_attr* attr)
    ssize_t mq_receive(mqd_t mqdes, char* msg_ptr, size_t msg_len, unsigned int* msg_prio)
    int mq_send(mqd_t mqdes, const char* msg_ptr, size_t msg_len, unsigned int msg_prio)
    int mq_setattr(mqd_t mqdes, const mq_attr* newattr, mq_attr* oldattr)
    int mq_unlink(const char* name)

