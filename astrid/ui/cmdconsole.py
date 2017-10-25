import cmd
from astrid.server import AstridServer
from astrid.client import AstridClient

class AstridConsole(cmd.Cmd):
    """ Astrid Console 
    """

    prompt = '^_- '
    intro = 'Astrid Console'

    def __init__(self, server=None, client=None):
        cmd.Cmd.__init__(self)

        if server is None:
            self.server = AstridServer('astrid', pid_dir='/tmp')
        else:
            self.server = server

        if not self.server.is_running():
            self.server.start()
            print('Started astrid server')

        if client is None:
            self.client = AstridClient()
        else:
            self.client = client

    def do_p(self, cmd):
        self.client.send_cmd(['play'] + cmd.split(' '))

    def do_track(self, cmd):
        self.client.send_cmd(['analysis'] + cmd.split(' '))

    def do_a(self, cmd):
        self.client.send_cmd(['add'] + cmd.split(' '))

    def do_r(self, cmd):
        self.client.send_cmd(['reload'] + cmd.split(' '))

    def do_i(self, cmd):
        try:
            for instrument in self.client.list_instruments():
                if isinstance(instrument, bytes):
                    instrument = instrument.decode('ascii')
                print(instrument)
        except TypeError:
            pass

    def do_s(self, voice_id):
        print('Stopping all voices')
        self.client.send_cmd(['stopall'])

    def do_start(self, cmd):
        if not self.server.is_running():
            self.server.start()
            print('Started astrid server')
        else:
            print('Astrid server is already running')

    def do_stop(self, cmd):
        if self.server.is_running():
            self.client.send_cmd(['shutdown'])
            print('Sent shutdown signal')
        else:
            print('Astrid server is already stopped')

    def do_quit(self, cmd):
        self.quit()

    def do_EOF(self, line):
        return True

    def postloop(self):
        pass

    def start(self):
        self.cmdloop()

    def quit(self):
        if self.server.is_running():
            self.server.stop()

