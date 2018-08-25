from .midi cimport MidiBucket

cdef class ParamBucket:
    cdef object _params

cdef class EventContext:
    cdef public object before
    cdef public MidiBucket m
    cdef public ParamBucket p
    cdef public object client
    cdef public str instrument_name
    cdef public object running
    cdef public object shutdown
    cdef public object stop_me
    cdef public object bus
    cdef public object sounds
    cdef public int count

cdef class Instrument:
    cdef public str name
    cdef public object renderer
    cdef public object shutdown
    cdef public object sounds 
