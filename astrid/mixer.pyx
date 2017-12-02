# distutils: libraries = portaudio

from libc.stdlib cimport malloc, calloc, free
from pippi.soundbuffer cimport SoundBuffer
cimport cython

#@cython.boundscheck(False)
#@cython.wraparound(False)
cdef int mix_block(stream_ctx *ctx, unsigned long block_size):
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
            ctx.playing_current.pos += 1
        else:
            print('end of buffer')
            # Remove playbuf from stack
            if ctx.playing_current.prev != NULL:
                ctx.playing_current.prev.next = ctx.playing_current.next

            if ctx.playing_current.next != NULL:
                ctx.playing_current.next.prev = ctx.playing_current.prev

            if ctx.done_head == NULL:
                ctx.done_head = ctx.playing_current
                ctx.done_tail = ctx.playing_current
            else:
                ctx.playing_current.prev = ctx.done_tail
                ctx.done_tail.next = ctx.playing_current
                ctx.done_tail = ctx.playing_current

            break

    return 0

@cython.boundscheck(False)
@cython.wraparound(False)
cdef int main_callback(const void *input, 
                             void *output,
                    unsigned long frameCount,
  const PaStreamCallbackTimeInfo* timeInfo,
            PaStreamCallbackFlags statusFlags,
                             void *current_context):
    """ Starting at root node, follow the chain of 
        buffers in the playing stack until the end, 
        Summing each and writing samples out to the 
        stream.

        As buffers are read, if no more samples are available, 
        remove the buffer from the stack. Which involves:
        Setting the value of next_buffer->previous to 
        deleted_buffer->previous, and deleted_buffer->previous->next to 
        next_buffer... then freeing memory.
    """
    cdef stream_ctx *ctx = <stream_ctx*>current_context

    ctx.playing_current = ctx.playing_head
    cdef int count = 0
    while ctx.playing_current != NULL:
        mix_block(ctx, frameCount)
        ctx.playing_current = ctx.playing_current.next
        count += 1

    cdef int i = 0
    cdef int j = 0
    cdef int c = 0

    cdef float *out = <float*>output

    for i in range(<int>frameCount):
        for c in range(ctx.channels):
            out[j] = <float>ctx.out[i * ctx.channels + c]
            j += 1

    return 0

cdef class AstridMixer:
    def __cinit__(self, int block_size=64, int channels=2, int samplerate=44100):
        self.block_size = block_size
        self.channels = channels
        self.samplerate = samplerate

        cdef PaStream* stream
        cdef PaError err
        cdef PaStreamCallback* cb

        self.ctx = <stream_ctx*>malloc(sizeof(stream_ctx))
        self.ctx.out = <double*>calloc(block_size * channels, sizeof(double))
        self.ctx.channels = channels
        self.ctx.playing_head = NULL
        self.ctx.playing_tail = NULL
        self.ctx.playing_current = NULL
        self.ctx.done_head = NULL
        self.ctx.done_tail = NULL

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

    def __dealloc__(self):
        free(self.ctx.out)
        free(self.ctx)

    cdef void _flush(self) except *:
        cdef playbuf *current = self.ctx.playing_head
        cdef playbuf *tofree = NULL
        while current != NULL:
            tofree = current
            current = current.next
            if tofree.frames != NULL:
                free(tofree.frames)
            free(tofree)

        self.ctx.done_head = NULL
        self.ctx.done_tail = NULL

    cdef void _add(self, SoundBuffer snd) except *:
        cdef int length = len(snd)
        cdef int channels = snd.channels

        cdef playbuf *buf = <playbuf*>malloc(sizeof(playbuf))
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

    def sleep(self, long msec):
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


