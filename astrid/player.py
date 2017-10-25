players = set()

def init(onsets=None):
    """ Register a module-level function 
        as a play method with an optional 
        onset list or callback
    """
    def decorate(func):
        if func not in players:
            players.add((func, onsets))
        return func

    return decorate
