from .q cimport BufQ

cdef void init_voice(object instrument, object params, BufQ* buf_q, object event_q)
