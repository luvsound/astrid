# distutils: libraries = portaudio
# cython: language_level=3
 
from __future__ import absolute_import
from libc.stdlib cimport malloc, calloc, free
from pippi.soundbuffer cimport SoundBuffer
cimport cython
import numpy as np


@cython.boundscheck(False)
@cython.wraparound(False)
cdef int mix_block(stream_ctx* ctx, unsigned long block_size):
    """ Add frames to output, removing from 
        playing list and adding to done queu 
        if no more frames are available.
    """
    cdef int i = 0
    cdef int c = 0

    for i in range(<int>block_size):
        if ctx.playing_current.pos < ctx.playing_current.length:
            for c in range(ctx.channels):
                ctx.out[i * ctx.channels + c] += ctx.playing_current.frames[ctx.playing_current.pos * ctx.channels + c]
        else:
            break
        ctx.playing_current.pos = ctx.playing_current.pos + 1

    #print('mixed')
    return 0

@cython.boundscheck(False)
@cython.wraparound(False)
cdef int main_callback(const void* inputbuffer, 
                             void* output,
                     unsigned long frameCount,
   const PaStreamCallbackTimeInfo* timeInfo,
             PaStreamCallbackFlags statusFlags,
                             void* current_context):
    cdef int i = 0
    cdef int j = 0
    cdef int c = 0

    cdef stream_ctx* ctx = <stream_ctx*>current_context

    for i in range(<int>frameCount):
        for c in range(ctx.channels):
            ctx.out[i * ctx.channels + c] = 0

    ctx.playing_current = ctx.playing_head
    cdef int count = 0
    while ctx.playing_current != NULL:
        if ctx.playing_current.pos < ctx.playing_current.length:
            mix_block(ctx, frameCount)
            
        ctx.playing_current = ctx.playing_current.next

        count += 1

    cdef float* out = <float*>output
    cdef const float* inp = <const float*>inputbuffer
    cdef double* rbp = &ctx.input_ringbuffer[ctx.input_write_head * ctx.channels]

    for i in range(<int>frameCount):
        for c in range(ctx.channels):
            out[j] = <float>ctx.out[i * ctx.channels + c]
            j += 1
    j = 0

    if inputbuffer != NULL:
        for i in range(<int>frameCount):
            for c in range(ctx.channels):
                rbp[ctx.input_write_head * ctx.channels + c ] = <double>inp[j]
                j += 1

        ctx.input_write_head = (ctx.input_write_head + 1) % ctx.input_framelength

    return 0

cdef class AstridMixer:
    def __cinit__(self, int block_size=64, int channels=2, int samplerate=44100, double ringbuffer_length=30):
        self.block_size = block_size
        self.channels = channels
        self.samplerate = samplerate

        cdef PaStream* stream
        cdef PaError err
        cdef PaStreamCallback* cb


        self.ctx = <stream_ctx*>malloc(sizeof(stream_ctx))
        self.ctx.out = <double*>calloc(block_size * channels, sizeof(double))
        self.ctx.input_framelength = <int>(ringbuffer_length * samplerate)
        self.ctx.input_ringbuffer = <double*>calloc(self.ctx.input_framelength * channels, sizeof(double))
        self.ctx.input_write_head = 0
        self.ctx.channels = channels
        self.ctx.playing_head = NULL
        self.ctx.playing_tail = NULL
        self.ctx.playing_current = NULL
        self.ctx.done_head = NULL
        self.ctx.done_tail = NULL
        #print('mixer ctx alloc')

        cb = <PaStreamCallback*>&main_callback

        err = Pa_Initialize()
        if(err != paNoError):
            print("Initialize err: %s" % Pa_GetErrorText(err))

        err = Pa_OpenDefaultStream(
                &stream, 0, channels, 
                paFloat32, samplerate, block_size, 
                cb, self.ctx
            )
        if(err != paNoError):
            print("Open default stream err: %s" % Pa_GetErrorText(err))

        self.ctx.stream = stream

        err = Pa_StartStream(stream)
        if(err != paNoError):
            print("Start stream err: %s" % Pa_GetErrorText(err))

        #print('started stream')

    def __dealloc__(self):
        #free(self.ctx.out)
        #free(self.ctx)
        pass

    cdef void _flush(self) except *:
        cdef playbuf* current = self.ctx.playing_head
        cdef playbuf* tofree = NULL
        while current != NULL:
            tofree = current
            current = current.next
            if tofree.frames != NULL:
                free(tofree.frames)
            free(tofree)

        self.ctx.done_head = NULL
        self.ctx.done_tail = NULL

    cdef void _add(self, SoundBuffer snd) except *:
        #print('mixer add')
        cdef int length = len(snd)
        cdef int channels = snd.channels

        cdef playbuf* buf = <playbuf*>malloc(sizeof(playbuf))
        buf.frames = <double*>calloc(length * channels, sizeof(double))

        cdef int i = 0
        cdef int j = 0

        for i in range(length):
            for j in range(channels):
                buf.frames[i * channels + j] = snd.frames[i][j]

        buf.length = length
        buf.channels = channels
        buf.pos = 0
        buf.next = NULL
        buf.prev = NULL

        if self.ctx.playing_head == NULL:
            self.ctx.playing_head = buf
            self.ctx.playing_tail = buf
        
        else:
            buf.prev = self.ctx.playing_tail
            self.ctx.playing_tail.next = buf
            self.ctx.playing_tail = buf

        #self._flush()

    def add(self, SoundBuffer snd):
        self._add(snd)

    cdef double[:,:] _read_input(self, int frames, int offset):
        cdef int i = 0
        cdef int c = 0
        cdef int read_head = 0
        cdef double[:,:] out = np.zeros((frames, self.channels))

        if frames > self.input_framelength:
            frames = self.input_framelength

        read_head = (self.input_write_head - frames + offset) % self.input_framelength
        for i in range(frames):
            for c in range(self.channels):
                out[i][c] = self.ctx.input_ringbuffer[read_head * self.channels + c]
            read_head = (read_head + 1) % self.input_framelength

        return out

    def read(self, int frames, int offset=0):
        #print('mixer.read')
        return SoundBuffer(self._read_input(frames, offset), self.channels, self.samplerate)

    def sleep(self, unsigned long msec):
        Pa_Sleep(msec)

    cdef void _shutdown(self) except *:
        cdef PaError err

        err = Pa_StopStream(self.ctx.stream)
        if(err != paNoError):
            print("Stop stream err: %s" % Pa_GetErrorText(err))

        err = Pa_CloseStream(self.ctx.stream)
        if(err != paNoError):
            print("Close stream err: %s" % Pa_GetErrorText(err))
     
        err = Pa_Terminate()
        if(err != paNoError):
            print("Terminate err: %s" % Pa_GetErrorText(err))

        #self._flush()

    def shutdown(self):
        self._shutdown()


