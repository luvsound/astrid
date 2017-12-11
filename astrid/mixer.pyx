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

    return 0

@cython.boundscheck(False)
@cython.wraparound(False)
cdef int output_callback(const void* inputbuffer, 
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
    for i in range(<int>frameCount):
        for c in range(ctx.channels):
            out[j] = <float>ctx.out[i * ctx.channels + c]
            j += 1

    return 0


@cython.boundscheck(False)
@cython.wraparound(False)
cdef int input_callback(const void* inputbuffer, 
                             void* output,
                     unsigned long frameCount,
   const PaStreamCallbackTimeInfo* timeInfo,
             PaStreamCallbackFlags statusFlags,
                             void* current_context):
    cdef int i = 0
    cdef int j = 0
    cdef int c = 0

    cdef stream_ctx* ctx = <stream_ctx*>current_context

    cdef const float* inp = <const float*>inputbuffer

    if inputbuffer != NULL:
        for i in range(<int>frameCount * ctx.channels):
            ctx.ringbuffer[ctx.ringbuffer_pos] = <double>inp[i]
            ctx.ringbuffer_pos += 1

    return 0

cdef class AstridMixer:
    def __cinit__(self, int block_size=64, int channels=2, int samplerate=44100, double ringbuffer_length=30):
        self.block_size = block_size
        self.channels = channels
        self.samplerate = samplerate

        cdef PaStream* input_stream
        cdef PaStream* output_stream
        cdef PaError err
        cdef PaStreamCallback* inputcb
        cdef PaStreamCallback* outputcb

        self.ctx = <stream_ctx*>malloc(sizeof(stream_ctx))
        self.ctx.out = <double*>calloc(block_size * channels, sizeof(double))
        self.ctx.ringbuffer_length = <int>(ringbuffer_length * samplerate * channels)
        self.ctx.ringbuffer = <double*>calloc(self.ctx.ringbuffer_length, sizeof(double))
        self.ctx.ringbuffer_pos = 0
        self.ctx.channels = channels
        self.ctx.samplerate = samplerate
        self.ctx.playing_head = NULL
        self.ctx.playing_tail = NULL
        self.ctx.playing_current = NULL

        inputcb = <PaStreamCallback*>&input_callback
        outputcb = <PaStreamCallback*>&output_callback

        err = Pa_Initialize()
        if(err != paNoError):
            print("Initialize err: %s" % Pa_GetErrorText(err))

        self.input_params = <PaStreamParameters*>malloc(sizeof(PaStreamParameters))
        self.input_params.device = Pa_GetDefaultInputDevice()
        self.input_params.channelCount = channels
        self.input_params.sampleFormat = paFloat32
        self.input_params.suggestedLatency = Pa_GetDeviceInfo(self.input_params.device).defaultHighInputLatency
        self.input_params.hostApiSpecificStreamInfo = NULL

        self.output_params = <PaStreamParameters*>malloc(sizeof(PaStreamParameters))
        self.output_params.device = Pa_GetDefaultOutputDevice()
        self.output_params.channelCount = channels
        self.output_params.sampleFormat = paFloat32
        self.output_params.suggestedLatency = Pa_GetDeviceInfo(self.output_params.device).defaultHighInputLatency
        self.output_params.hostApiSpecificStreamInfo = NULL

        err = Pa_OpenStream(
                &output_stream, 
                NULL,
                self.output_params, 
                <double>samplerate, 
                <unsigned long>block_size, 
                0, 
                outputcb, 
                self.ctx
            )

        if(err != paNoError):
            print("Open default stream err: %s" % Pa_GetErrorText(err))

        self.ctx.output_stream = output_stream

        err = Pa_StartStream(output_stream)
        if(err != paNoError):
            print("Start stream err: %s" % Pa_GetErrorText(err))

        err = Pa_OpenStream(
                &input_stream,
                self.input_params,
                NULL,
                <double>samplerate, 
                paFramesPerBufferUnspecified,
                0, 
                inputcb, 
                self.ctx
            )

        if(err != paNoError):
            print("Open default stream err: %s" % Pa_GetErrorText(err))

        self.ctx.input_stream = input_stream

        err = Pa_StartStream(input_stream)
        if(err != paNoError):
            print("Start stream err: %s" % Pa_GetErrorText(err))


    cdef void _flush(self) except *:
        cdef playbuf* current = self.ctx.playing_head
        while current != NULL:
            if current.pos > current.length and current.frames != NULL:
                free(current.frames)
                current.frames = NULL
            current = current.next

    cdef void _add(self, SoundBuffer snd) except *:
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

        self._flush()


    def add(self, SoundBuffer snd):
        self._add(snd)

    cdef double[:,:] _read_input(self, int frames, int offset):
        cdef int i = 0
        cdef int c = 0
        cdef int read_head = 0
        cdef double[:,:] out = np.zeros((frames, self.channels))

        if frames * self.ctx.channels > self.ctx.ringbuffer_length:
            frames = self.ctx.ringbuffer_length // self.ctx.channels

        read_head = (self.ctx.ringbuffer_pos - ((frames + offset) * self.ctx.channels)) % self.ctx.ringbuffer_length
        for i in range(frames):
            for c in range(self.channels):
                out[i][c] = self.ctx.ringbuffer[read_head % self.ctx.ringbuffer_length]
                read_head += 1

        return out

    def read(self, int frames, int offset=0):
        return SoundBuffer(self._read_input(frames, offset), self.channels, self.samplerate)

    def sleep(self, unsigned long msec):
        Pa_Sleep(msec)

    cdef void _shutdown(self) except *:
        cdef PaError err

        err = Pa_StopStream(self.ctx.output_stream)
        if(err != paNoError):
            print("Stop output stream err: %s" % Pa_GetErrorText(err))

        err = Pa_CloseStream(self.ctx.output_stream)
        if(err != paNoError):
            print("Close output stream err: %s" % Pa_GetErrorText(err))

        err = Pa_StopStream(self.ctx.input_stream)
        if(err != paNoError):
            print("Stop input stream err: %s" % Pa_GetErrorText(err))

        err = Pa_CloseStream(self.ctx.input_stream)
        if(err != paNoError):
            print("Close input stream err: %s" % Pa_GetErrorText(err))
     
        err = Pa_Terminate()
        if(err != paNoError):
            print("Terminate err: %s" % Pa_GetErrorText(err))

        self._flush()

        if self.ctx != NULL:
            if self.ctx.ringbuffer != NULL:
                free(self.ctx.ringbuffer)

            if self.ctx.out != NULL:
                free(self.ctx.out)

            free(self.ctx)

        if self.input_params != NULL:
            free(self.input_params)

        if self.output_params != NULL:
            free(self.output_params)

    def shutdown(self):
        self._shutdown()


