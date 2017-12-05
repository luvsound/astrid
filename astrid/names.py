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

MSG_PORT = 9191
MSG_HOST = 'localhost'

_cmdToName = {
    LOAD_INSTRUMENT: 'add', 
    RELOAD_INSTRUMENT: 'reload', 
    STOP_ALL_VOICES: 'stopall', 
    LIST_INSTRUMENTS: 'list', 
    PLAY_INSTRUMENT: 'play', 
    ANALYSIS: 'analysis', 
    SHUTDOWN: 'shutdown', 
    MSG_OK: 'ok', 
}

_nameToCmd = {
    'add': LOAD_INSTRUMENT, 
    'load': LOAD_INSTRUMENT, 
    'reload': RELOAD_INSTRUMENT, 
    'stopall': STOP_ALL_VOICES,
    'list': LIST_INSTRUMENTS, 
    'play': PLAY_INSTRUMENT, 
    'analysis': ANALYSIS,
    'shutdown': SHUTDOWN,
    'ok': MSG_OK, 
}

def ntoc(name):
    return _nameToCmd.get(name, None)

def cton(cmd):
    return _cmdToName.get(cmd, None)


