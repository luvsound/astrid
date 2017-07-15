import os
import random

from kivy.app import App
from kivy.core.window import Window
from kivy.extras.highlight import PythonLexer
from kivy.event import EventDispatcher
from kivy.garden.graph import Graph, MeshLinePlot, SmoothLinePlot
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty, StringProperty

from kivy.uix.accordion import Accordion, AccordionItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.codeinput import CodeInput
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.uix.textinput import TextInput

from astrid.server import AstridServer
from pippi import dsp, oscs, interpolation

class Waveform(BoxLayout):
    def __init__(self, sound, **kwargs):
        super().__init__(**kwargs)
        graph_size_x = 1024
        graph_size_y = 60

        self.orientation='vertical'
        self.size_hint=(1, None)
        self.height=graph_size_y

        colors = []
        for _ in range(sound.channels):
            colors += [ [random.triangular(0.5, 1), random.triangular(0.5, 1), random.triangular(0.5, 1)] ]

        for channel in range(sound.channels):
            graph = Graph(
                    x_ticks_minor=10, 
                    x_ticks_major=100, 
                    y_ticks_major=1, 
                    y_grid_label=False, 
                    x_grid_label=False, 
                    padding=0, 
                    x_grid=True, 
                    draw_border=False, 
                    y_grid=False, 
                    xmin=-0, 
                    xmax=graph_size_x, 
                    ymin=-1, 
                    ymax=1,
                    size_hint=(1, 1), 
                )

            plot = SmoothLinePlot(color=colors[channel])
            points = [ sound[x][channel] for x in range(len(sound)) ]
            points = interpolation.linear(points, graph_size_x)
            points = [ (x, point) for x, point in enumerate(points) ]
            plot.points = points
            graph.add_plot(plot)
            self.add_widget(graph)

class InstrumentPanel(TabbedPanel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.size_hint = (1,1)
        self.do_default_tab = True
        self.tab_pos = 'top_left'

        home_dir = '/home/hecanjog'
        orc_dir = '/home/hecanjog/code'

        browser = FileChooserListView()
        browser.rootpath = orc_dir
        browser.path = orc_dir
        browser.font_name = '../../files/fonts/terminus/terminus.ttf'
        browser.font_size = 12
        browser.bind(on_submit=self._open_selection)

        self.default_tab_text = 'ORC'
        self.default_tab_content = browser

    def _open_selection(self, instance, selection, event):
        for path in selection:
            self._open_instrument(path)

    def _open_instrument(self, path):
        with open(path) as instrument:
            contents = instrument.read()
            codebox = Codebox(contents, path)
            tab = TabbedPanelHeader(text=os.path.basename(path).replace('.py', ''), content=codebox)
            self.add_widget(tab)
            self.switch_to(tab)

        msg = Message(text='Saved to {}\nTo play it, type \n    p {}'.format(path, os.path.basename(path).replace('.py', '')))
        #self.parent.parent.console.messages.add_widget(msg)

class ConsoleMessageDispatcher(EventDispatcher):
    def __init__(self, **kwargs):
        self.register_event_type('on_console_message')
        super().__init__(**kwargs)

    def do_something(self, value):
        self.dispatch('on_console_message', value)

    def on_console_message(self, *args):
        print('on_console_message', args)

def make_sound():
    osc = oscs.Osc()
    osc.amp = 0.3
    length = 4000

    freqs = [80, 100, 111]
    tones = []
    for freq in freqs:
        osc.freq = freq
        tone = osc.play(length)
        tone = tone.pan(random.random())
        tones += [ tone ]

    out = dsp.mix(tones)

    return out

class Voice(Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_name = '../../files/fonts/terminus/terminus.ttf'
        self.font_size = 12
        self.halign = 'left'
        self.valign = 'middle'
        self.markup = True
        self.color = [1,1,1,1]
        self.padding = (6, 0)
        self.disabled_color = [0.8, 0.8, 0.8, 1]
        self.size_hint = (1,1)
        self.bind(size=self.setter('text_size'))

    def on_size(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.1, random.triangular(0.15, 0.2), 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)

class VoiceList(BoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orientation = 'vertical'

        for _ in range(random.randint(3, 12)):
            #params = ' '.join([ '{}:{}'.format(random.choice(['o', 'd', 'f', 'a', 'v']), random.randint(1, 20)) for _ in range(random.randint(3, 8)) ])
            #label = Voice(text='voice [b]{}[/b]'.format(params))
            #self.add_widget(label)
            pass

class Message(Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_name = '../../files/fonts/terminus/terminus.ttf'
        self.font_size = 12
        self.halign = 'left'
        self.valign = 'middle'
        self.markup = True
        self.padding = (6, 0)
        self.color = [1,1,1,1]
        self.disabled_color = [0.8, 0.8, 0.8, 1]
        self.size_hint = (1,1)
        self.bind(size=self.setter('text_size'))

    def on_size(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.1, 0.1, random.triangular(0.2, 0.3), 1)
            Rectangle(pos=self.pos, size=self.size)

class MessageList(BoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orientation = 'vertical'

        for _ in range(random.randint(3, 12)):
            #msg = Message(text='msg [b]msg[/b]')
            #self.add_widget(msg)
            pass

class Codebox(BoxLayout):
    def __init__(self, contents, path, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.last_saved = contents

        self.codebox = CodeInput(size_hint=(1,1), text=contents, lexer=PythonLexer(), style_name='native')
        self.codebox.bind(text=self._on_change)

        self.last_saved = contents
        self.codebox.font_name = '../../files/fonts/terminus/terminus.ttf'
        self.codebox.font_size = 12
        self.codebox.padding = [10,10,10,10]
        self.codebox.selection_color = [random.triangular(0.5, 1), random.triangular(0.5, 1), random.triangular(0.5, 1), 0.5]
        self.codebox.background_color = [0.1,0.1,0.1,1]
        self.codebox.filepath = path

        self.add_widget(self.codebox)

    def _on_change(self, instance, value):
        if value != self.last_saved:
            instance.background_color = [0.1, 0.1, 0.3, 1]
        else:
            instance.background_color = [0.1,0.1,0.1,1]

class Prompt(RelativeLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        prompt_winky = TextInput()
        prompt_winky.text = '^_- '
        prompt_winky.multiline=False
        prompt_winky.size_hint=(1, None)
        prompt_winky.height=25
        prompt_winky.readonly=False
        prompt_winky.font_name = '../../files/fonts/terminus/terminus.ttf'
        prompt_winky.font_size = 12
        prompt_winky.foreground_color = [1,1,1,1]
        prompt_winky.background_color = [0.1,0.1,0.1,1]

        prompt_input = TextInput()
        prompt_input.multiline=False
        prompt_input.size_hint=(1, None)
        prompt_input.height=25
        prompt_input.readonly=False
        prompt_input.font_name = '../../files/fonts/terminus/terminus.ttf'
        prompt_input.font_size = 12
        prompt_input.foreground_color = [1,1,1,1]
        prompt_input.background_color = [0.1,0.1,0.1,1]

        self.add_widget(prompt_winky)
        self.add_widget(prompt_input)

class Console(BoxLayout):
    def __init__(self, *args, **kwargs):
        kwargs.update({'orientation': 'vertical'})
        super().__init__(*args, **kwargs)

        prompt = Prompt()
        self.messages = MessageList()

        self.add_widget(self.messages)
        self.add_widget(prompt)

class Astrid(App):
    def start(self):
        #self.server = AstridServer()
        #self.server.start()
        return self.run()

    def quit(self):
        #self.io.quit()
        exit()

    def save_current(self):
        content = self.instrument_panel.current_tab.content.codebox.text
        self.instrument_panel.current_tab.content.last_saved = content
        path = self.instrument_panel.current_tab.content.codebox.filepath

        with open(path, 'w') as script:
            script.write(content)

        msg = Message(text='Saved to {}\nTo play it, type \n    p {}'.format(path, os.path.basename(path).replace('.py', '')))
        self.console.messages.add_widget(msg)

        self.instrument_panel.current_tab.content.codebox.background_color = [0.1,0.1,0.1,1]

    def handle_keys(self, window, scancode, y, char, mods):
        print(self, window, scancode, y, char, mods)
        if 'ctrl' in mods and scancode == 113:
            self.quit()

        elif 'ctrl' in mods and scancode == 115:
            self.save_current()

    def build(self):
        Window.bind(on_key_down=self.handle_keys)

        # containers
        main = GridLayout(cols=2)
        sidebar = BoxLayout(orientation='vertical', size_hint=(None, 1), width=320)

        # main widgets
        self.console = Console()
        voicelist = VoiceList()
        instrument_panel = InstrumentPanel()
        waveform = Waveform(make_sound())

        self.instrument_panel = instrument_panel

        # sidebar: waveform, voices, console
        sidebar.add_widget(waveform)
        sidebar.add_widget(voicelist)
        sidebar.add_widget(self.console)

        # left column: instrument_panel
        # right column: sidebar
        main.add_widget(instrument_panel)
        main.add_widget(sidebar)

        return main
