cdef SoundBuffer _cbuf_to_py(double* snd, int channels, int samplerate, int length):
    cdef int i = 0
    cdef int c = 0
    cdef int read_head = 0
    cdef double[:,:] out = np.zeros((length, channels))

    for i in range(length):
        for c in range(channels):
            out[i][c] = snd[i * channels * c]

    return SoundBuffer(out, channels, samplerate)


def init_queue():
    self.ctx = <stream_ctx*>malloc(sizeof(stream_ctx))
    #self.ctx = <stream_ctx*>stream_ctx_ptr
    self.ctx.out = <double*>calloc(block_size * channels, sizeof(double))
    self.ctx.ringbuffer_length = <int>(ringbuffer_length * samplerate * channels)
    self.ctx.ringbuffer = <double*>calloc(self.ctx.ringbuffer_length, sizeof(double))
    self.ctx.ringbuffer_pos = 0
    #self.ctx.ringbuffer_length = ringbuffer_length
    #self.ctx.ringbuffer = ringbuffer
    #self.ctx.ringbuffer_pos = ringbuffer_pos
    self.ctx.channels = channels
    self.ctx.samplerate = samplerate
    self.ctx.playing_head = NULL
    self.ctx.playing_tail = NULL
    self.ctx.playing_current = NULL


cdef void _flush_queue(self) except *:
    cdef playbuf* current = self.ctx.playing_head
    while current != NULL:
        if current.pos > current.length and current.frames != NULL:
            free(current.frames)
            current.frames = NULL
        current = current.next

cdef void _remove_from_queue(

cdef void _add_to_queue(SoundBuffer snd) except *:
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


