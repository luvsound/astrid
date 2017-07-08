from kivy.app import App
import random
from pippi import dsp, oscs, interpolation
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.codeinput import CodeInput
from kivy.uix.gridlayout import GridLayout
from kivy.garden.graph import Graph, MeshLinePlot, SmoothLinePlot
from kivy.extras.highlight import PythonLexer

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
        super(Console, self).__init__(*args, **kwargs)

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
        graph_size_x = 1024
        graph_size_y = 100

        layout = GridLayout(cols=2)
        right_pane = BoxLayout(orientation='vertical')
        codebox = Codebox()
        console = Console()

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

        colors = []
        for _ in range(out.channels):
            colors += [ [random.triangular(0.5, 1), random.triangular(0.5, 1), random.triangular(0.5, 1)] ]

        for channel in range(out.channels):
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
                    size_hint=(1, None), 
                    height=graph_size_y
                )

            plot = SmoothLinePlot(color=colors[channel])
            points = [ out[x][channel] for x in range(len(out)) ]
            points = interpolation.linear(points, graph_size_x)
            points = [ (x, point) for x, point in enumerate(points) ]
            plot.points = points
            graph.add_plot(plot)
            right_pane.add_widget(graph)

        right_pane.add_widget(console)

        layout.add_widget(codebox)
        layout.add_widget(right_pane)

        return layout
