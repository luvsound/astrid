cdef mqd_t* mq_init(const char* name):
    cdef mq_attr* attr = <mq_attr*>malloc(sizeof(mq_attr))
    cdef mqd_t* mq = <mqd_t*>malloc(sizeof(mqd_t))

    attr.mq_flags = 0
    attr.mq_maxmsg = 1024
    attr.mq_msgsize = sizeof(N)
    attr.mq_curmsgs = 0

    mq = &mq_open(name, O_CREAT | O_RDONLY, 0644, attr)
