from .q cimport *

cdef struct RendererParams:
    Q* play_q
    Q* buf_q
