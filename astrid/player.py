players = set()

def init(onsets=None):
    """ Register a module-level function 
        as a play method with an optional 
        onset list or callback
    """
    def decorate(func):
        p = (func, onsets)
        if p not in players:
            players.add(p)
        return func

    return decorate
