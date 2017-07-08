import importlib.util
from importlib import reload
import os
import sys
import re
import glob
import logging
import urwid

from astrid import io

logging.basicConfig(filename='pippi.log', level=logging.INFO)

class AstridConsole(urwid.Pile):
    def __init__(self, *args, **kwargs):
        self.palette = [
            ('voice', 'white', 'dark green'), 
            ('instrument', 'white', 'dark blue'), 
            ('prompt', 'light blue', 'black'), 
            ('message', 'black', 'light green'), 
            ('param', 'white', 'dark magenta'), 
            ('black', 'black', 'black'), 
        ]

        header_rows = 30

        self.commands = []
        self.history_pos = -1
        self.prompt = urwid.Edit([('prompt', '^_-'), ('black', ' ')])

        self.voices = urwid.Pile([urwid.Text(('voice', 'Voices'))])
        self.instruments = urwid.Pile([urwid.Text(('instrument', 'Instruments'))])

        self.params = urwid.AttrMap(urwid.Text(('param', '')), 'param')
        self.message = urwid.AttrMap(urwid.Text(('message', '')), 'message')

        self.columns = urwid.Columns((
            self.voices,
            #(1, urwid.SolidFill('\u2502')), 
            self.instruments,
        )) 

        widgets = (self.columns, self.params, self.message, self.prompt)

        self.manager = io.IOManager()

        super(AstridConsole, self).__init__(widgets)

    def start(self):
        self.loop = urwid.MainLoop(urwid.Filler(self, 'bottom'), self.palette)
        self.loop.run()

    def refresh_voices(self):
        self.voices.contents = []
        for voice_id, instrument in self.manager.voices.items():
            name, params, _ = instrument
            self.voices.contents += [ (urwid.Text(('voice', 'V%s %s %s' % (voice_id, name, params))), self.voices.options()) ]

    def handle_cmd(self, cmd):
        if cmd in ('q', 'quit', 'exit'):
            self.quit()
        else:
            cmds = cmd.split(' ')
            instrument_name = None
            if cmds[0] == 'p':
                instrument_name = cmds[1]
                voice_id = self.manager.play(instrument_name, None)
                self.refresh_voices()
            elif cmds[0] == 's':
                try:
                    voice_id = cmds[1]
                    self.manager.stop_voice(voice_id)
                except IndexError:
                    self.manager.stop_all()
                    self.refresh_voices()

    def keypress(self, size, key):
        super(AstridConsole, self).keypress(size, key)
        if key == 'enter':
            cmd = self.prompt.get_edit_text()
            self.handle_cmd(cmd)
            self.prompt.set_edit_text('')
            self.commands += [ cmd ]

        elif key == 'up':
            self.history_pos += 1
            try:
                cmd = self.commands[self.history_pos]
                self.prompt.set_edit_text(cmd)
            except IndexError:
                pass
        elif key == 'down':
            self.history_pos -= 1
            try:
                cmd = self.commands[self.history_pos]
                self.prompt.set_edit_text(cmd)
            except IndexError:
                pass

        else:
            self.history_pos = 0

    def quit(self):
        self.manager.quit()
        self.loop.screen.stop()
        print('Bye!')
        raise urwid.ExitMainLoop()

