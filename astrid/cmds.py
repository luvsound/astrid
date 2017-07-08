import re

_re_instrument_name = re.compile(r'^\.(\w+)')
_re_instrument_param = re.compile(r'(\S*):(\S*)')

def parse(cmd):
    name = None
    params = ()

    if _re_instrument_name.match(cmd):
        pass

    return name, params
