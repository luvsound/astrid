import random

from kivy.app import App
from kivy.extras.highlight import PythonLexer
from kivy.garden.graph import Graph, MeshLinePlot, SmoothLinePlot
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty, StringProperty
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.codeinput import CodeInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from pippi import dsp, oscs, interpolation

INITIAL_SCRIPT= """\
from pippi import dsp, oscs
import random

def play(ctl):
    osc = oscs.Osc()
    osc.amp = 0.75
    length = 4000

    osc.freq = 80
    left = osc.play(length)
    left = left.pan(0)
    osc.freq = 100
    right = osc.play(length)
    right = right.pan(1)
    out = dsp.mix([ left, right ])

    return out
"""

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

def make_sound():
    osc = oscs.Osc()
    osc.amp = 0.75
    length = 4000

    osc.freq = 80
    left = osc.play(length)
    left = left.pan(0)
    osc.freq = 100
    right = osc.play(length)
    right = right.pan(1)
    out = dsp.mix([ left, right ])

    return out

class Voice(Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_name = '../../files/fonts/terminus/terminus.ttf'
        self.font_size = 12
        self.halign = 'left'
        self.valign = 'center'
        self.markup = True
        self.color = [1,1,1,1]
        self.disabled_color = [0.8, 0.8, 0.8, 1]
        self.size = self.texture_size

    def on_size(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.1, 0.1, random.triangular(0.2, 0.3), 1)
            Rectangle(pos=self.pos, size=self.size)

class VoiceList(BoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orientation = 'vertical'

        for _ in range(random.randint(3, 12)):
            params = ' '.join([ '{}:{}'.format(random.choice(['o', 'd', 'f', 'a', 'v']), random.randint(1, 20)) for _ in range(random.randint(3, 8)) ])
            label = Voice(text='voice [b]{}[/b]'.format(params))
            self.add_widget(label)

class Codebox(BoxLayout):
    def __init__(self, *args, **kwargs):
        super(Codebox, self).__init__(*args, **kwargs)

        codebox = CodeInput(size_hint=(1,1), text=INITIAL_SCRIPT, lexer=PythonLexer(), style_name='native')

        codebox.font_name = '../../files/fonts/terminus/terminus.ttf'
        codebox.font_size = 12
        codebox.padding = [10,10,10,10]
        codebox.selection_color = [random.triangular(0.5, 1), random.triangular(0.5, 1), random.triangular(0.5, 1), 0.5]
        codebox.background_color = [0.1,0.1,0.1,1]

        self.add_widget(codebox)

class Console(BoxLayout):
    def __init__(self, *args, **kwargs):
        kwargs.update({'orientation': 'vertical'})
        super().__init__(*args, **kwargs)

        messages = TextInput(text='MESSAGES', multiline=True, focus=False, size_hint=(1, 1), readonly=True)
        commands = TextInput(text='^_- ', multiline=False, size_hint=(1, None), height=25, readonly=False)

        messages.font_name = '../../files/fonts/terminus/terminus.ttf'
        messages.font_size = 12
        messages.foreground_color = [0.8,0.8,0.8,1]
        messages.background_color = [0.1,0.1,0.1,1]

        commands.font_name = '../../files/fonts/terminus/terminus.ttf'
        commands.font_size = 12
        commands.foreground_color = [1,1,1,1]
        commands.background_color = [0.1,0.1,0.1,1]

        self.add_widget(messages)
        self.add_widget(commands)


class Astrid(App):
    def start(self):
        return self.run()

    def build(self):
        layout = GridLayout(cols=2)
        right_pane = BoxLayout(orientation='vertical')
        codebox = Codebox()
        console = Console()
        voicelist = VoiceList()

        sound = make_sound()
        graph = Waveform(sound)
        right_pane.add_widget(graph)

        right_pane.add_widget(voicelist)
        right_pane.add_widget(console)

        layout.add_widget(codebox)
        layout.add_widget(right_pane)

        return layout
