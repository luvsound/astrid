#cython: language_level=3

""" Config values, flags, and message translations
"""

LOAD_INSTRUMENT = 1
LIST_INSTRUMENTS = 2
PLAY_INSTRUMENT = 3
MSG_OK = 4
RENDER_PROCESS_SHUTDOWN_SIGNAL = 5
RELOAD_INSTRUMENT = 6
STOP_ALL_VOICES = 7
SHUTDOWN = 8
ANALYSIS = 9
MSG_INVALID_INSTRUMENT = 10
ADD_BUFFER = 11
READ_INPUT = 12
MSG_BAD_PARAMS = 16
REGISTER_PORT = 17
SET_VALUE = 18
STOP_INSTRUMENT = 19

ENVELOPE_FOLLOWER = 14
PITCH_TRACKER = 15

MSG_PORT = 9191
MSG_HOST = 'localhost'

ORC_DIR = 'orc'

_cmdToName = {
    LOAD_INSTRUMENT: 'add', 
    RELOAD_INSTRUMENT: 'reload', 
    STOP_INSTRUMENT: 'stopinstrument', 
    STOP_ALL_VOICES: 'stopall', 
    LIST_INSTRUMENTS: 'list', 
    PLAY_INSTRUMENT: 'play', 
    ANALYSIS: 'analysis', 
    SHUTDOWN: 'shutdown', 
    MSG_OK: 'ok', 
    MSG_BAD_PARAMS: 'bad_params', 
    REGISTER_PORT: 'register_port', 
    MSG_INVALID_INSTRUMENT: 'invalid_instrument', 
    ADD_BUFFER: 'add_buffer',
    READ_INPUT: 'read_input',
    SET_VALUE: 'set_value',
}

_nameToCmd = {
    'add': LOAD_INSTRUMENT, 
    'load': LOAD_INSTRUMENT, 
    'reload': RELOAD_INSTRUMENT, 
    'stopinstrument': STOP_INSTRUMENT, 
    'stopall': STOP_ALL_VOICES,
    'list': LIST_INSTRUMENTS, 
    'play': PLAY_INSTRUMENT, 
    'analysis': ANALYSIS,
    'shutdown': SHUTDOWN,
    'ok': MSG_OK, 
    'bad_params': MSG_BAD_PARAMS, 
    'register_port': REGISTER_PORT,
    'invalid_instrument': MSG_INVALID_INSTRUMENT,
    'add_buffer': ADD_BUFFER,
    'read_input': READ_INPUT,
    'set_value': SET_VALUE,
}

def ntoc(name):
    return _nameToCmd.get(name, None)

def cton(cmd):
    return _cmdToName.get(cmd, None)


