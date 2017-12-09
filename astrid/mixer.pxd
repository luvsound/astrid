from pippi.soundbuffer cimport SoundBuffer, RingBuffer

cdef extern from 'portaudio.h':
    ctypedef int PaError
    ctypedef void PaStream

    cdef const char *Pa_GetErrorText( PaError errorCode )

    PaError Pa_Initialize()
    PaError Pa_StartStream(PaStream *stream)
    PaError Pa_StopStream(PaStream *stream)
    PaError Pa_AbortStream(PaStream *stream)
    PaError Pa_CloseStream(PaStream *stream)
    PaError Pa_Terminate()
    void Pa_Sleep(long msec)

    ctypedef unsigned long PaSampleFormat
    ctypedef double PaTime
    ctypedef unsigned long PaStreamFlags
    ctypedef unsigned long PaStreamCallbackFlags
    ctypedef unsigned long PaSampleFormat
    ctypedef int PaDeviceIndex

    PaSampleFormat paFloat32
    PaSampleFormat paInt32
    PaSampleFormat paInt24
    PaSampleFormat paInt16
    PaSampleFormat paInt8
    PaSampleFormat paUInt8
    PaSampleFormat paCustomFormat
    PaSampleFormat paNonInterleaved

    ctypedef struct PaStreamParameters:
        PaDeviceIndex device
        int channelCount
        PaSampleFormat sampleFormat
        PaTime suggestedLatency
        void *hostApiSpecificStreamInfo

    ctypedef struct PaStreamCallbackTimeInfo:
        PaTime inputBufferAdcTime
        PaTime currentTime
        PaTime outputBufferDacTime

    ctypedef int (*PaStreamCallback) (const void *input, void *output,
                                        unsigned long frameCount,
                                        const PaStreamCallbackTimeInfo* timeInfo,
                                        PaStreamCallbackFlags statusFlags,
                                        void *userData)

    PaError Pa_OpenStream(PaStream** stream,
                       const PaStreamParameters *inputParameters,
                       const PaStreamParameters *outputParameters,
                       double sampleRate,
                       unsigned long framesPerBuffer,
                       PaStreamFlags streamFlags,
                       PaStreamCallback *streamCallback,
                       void *userData )

    PaError Pa_OpenDefaultStream(PaStream** stream,
                  int numInputChannels,
                  int numOutputChannels,
                  PaSampleFormat sampleFormat,
                  double sampleRate,
                  unsigned long framesPerBuffer,
                  PaStreamCallback *streamCallback,
                  void *userData )


    ctypedef enum PaErrorCode:
        paNoError = 0
        paNotInitialized = -10000
        paUnanticipatedHostError
        paInvalidChannelCount
        paInvalidSampleRate
        paInvalidDevice
        paInvalidFlag
        paSampleFormatNotSupported
        paBadIODeviceCombination
        paInsufficientMemory
        paBufferTooBig
        paBufferTooSmall
        paNullCallback
        paBadStreamPtr
        paTimedOut
        paInternalError
        paDeviceUnavailable
        paIncompatibleHostApiSpecificStreamInfo
        paStreamIsStopped
        paStreamIsNotStopped
        paInputOverflowed
        paOutputUnderflowed
        paHostApiNotFound
        paInvalidHostApi
        paCanNotReadFromACallbackStream
        paCanNotWriteToACallbackStream
        paCanNotReadFromAnOutputOnlyStream
        paCanNotWriteToAnInputOnlyStream
        paIncompatibleStreamHostApi
        paBadBufferPtr


cdef struct playbuf:
    double* frames
    int length
    int channels
    int pos
    playbuf* prev
    playbuf* next

cdef struct stream_ctx:
    double* out
    playbuf* playing_head
    playbuf* playing_tail
    playbuf* playing_current
    playbuf* done_head
    playbuf* done_tail
    PaStream* stream
    double* input_ringbuffer
    int input_write_head
    int input_framelength
    int channels


cdef class AstridMixer:
    cdef public int block_size
    cdef public int channels
    cdef public int samplerate
    cdef stream_ctx* ctx
    cdef RingBuffer input_ringbuffer

    cdef void _add(self, SoundBuffer sound) except *
    cdef void _flush(self) except *
    cdef void _shutdown(self) except *
    cdef double[:,:] _read_input(self, int frames, int offset)

