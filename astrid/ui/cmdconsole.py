import cmd
from astrid.server import AstridServer

class AstridConsole(cmd.Cmd):
    """ Astrid Console 
    """

    prompt = '^_- '
    intro = 'Astrid Console'

    def __init__(self):
        cmd.Cmd.__init__(self)

        self.server = AstridServer('astrid', pid_dir='/tmp')
        if not self.server.is_running():
            self.server.start()

    def do_p(self, cmd):
        self.server.send_cmd(['play'] + cmd.split(' '))

    def do_a(self, cmd):
        self.server.send_cmd(['add'] + cmd.split(' '))

    def do_i(self, cmd):
        try:
            for instrument in self.server.list_instruments():
                if isinstance(instrument, bytes):
                    instrument = instrument.decode('ascii')
                print(instrument)
        except TypeError:
            pass

    def do_s(self, voice_id):
        self.server.send_cmd(['stop'] + cmd.split(' '))

    def do_quit(self, cmd):
        self.quit()

    def do_EOF(self, line):
        return True

    def postloop(self):
        pass

    def start(self):
        self.cmdloop()

    def quit(self):
        self.server.stop()
        exit()

