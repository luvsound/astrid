import cmd
from astrid.io import IOManager

class AstridConsole(cmd.Cmd):
    """ Astrid Console 
    """

    prompt = '^_- '
    intro = 'Astrid Console'

    def __init__(self):
        cmd.Cmd.__init__(self)

        self.io = IOManager()

    def do_p(self, cmd):
        pass

    def do_i(self, cmd):
        """List the number of voices for currently running instrument scripts.
        """
        voice_info = self.io.get_voice_info()

        if len(voice_info) > 0:
            print('voices playing:')
            for voice_id, instrument_name in voice_info.iteritems():
                print('    {} - {}'.format(voice_id, instrument_name))
            print()

    def do_s(self, voice_id):
        if voice_id == '':
            for voice_id, inst in self.io.get_voice_info().iteritems():
                self.params.set('%s-loop' % voice_id, False)
        else:
            self.params.set('%s-loop' % voice_id, False)

    def do_reload(self, opt):
        if opt == 'on':
            setattr(self.io.ns, 'reload', True)
        else:
            setattr(self.io.ns, 'reload', False)

    def do_quit(self, cmd):
        self.quit()

    def do_EOF(self, line):
        return True

    def postloop(self):
        pass

    def start(self):
        self.cmdloop()

    def quit(self):
        exit()

