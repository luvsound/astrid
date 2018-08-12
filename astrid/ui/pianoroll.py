from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.graphics import Color, Bezier, Line, Ellipse, Rectangle
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty, ListProperty, ObjectProperty, BooleanProperty
import random
from pippi import dsp, tune
from astrid import orc
import multiprocessing as mp

UPDATE_INTERVAL = 1/30
NOTELANE_HEIGHT = 12 
NOTELANE_GUTTER = 1 
NOTES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

Builder.load_string('''
#:import tune pippi.tune

<HeaderBar>:
    size_hint: (1, None)
    height: 20

    canvas:
        Color:
            rgba: 0.1,0.1,0.1,1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: self.parent.statusline
        color: 1, 1, 1, 1
        size: self.parent.size
        text_size: self.size
        size_hint: (None, 1)
        font_size: '10sp'
        bold: True
        pos: (2, self.parent.pos[1])
        valign: 'middle'
        halign: 'left'

    BoxLayout:
        width: 340
        size_hint: (None, 1)
        pos: (root.width - self.width, self.parent.pos[1])
        orientation: 'horizontal'

        SnapCheckBox:
            text: 'Snap  '
            size_hint: (1.5, 1)
            font_size: '10sp'
            text_size: self.size
            color: 1,1,1,1
            valign: 'middle'
            halign: 'left'

        SelectAllButton:
            font_size: '10sp'
            size_hint: (2, 1)
            text: 'Select (A)ll'

        ClearButton:
            font_size: '10sp'
            size_hint: (2, 1)
            text: '(C)lear Selections'

        RenderButton:
            font_size: '10sp'
            size_hint: (2, 1)
            text: '(R)ender'

<Note>:
    height: 12
    minimum_width: 5
    canvas:
        Color:
            rgba: (0,0,0.5,0.5) if self.highlighted else (0.75,0,0.75,0.5)
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: (0,0,0.5,0.25) if self.highlighted else (0.75,0,0.75,0.25)
        Rectangle:
            pos: (self.pos[0]+2, self.pos[1]-2)
            size: self.size

    Label:
        text: ' ' + self.parent.freq
        color: 1, 1, 1, 1
        pos: self.parent.pos
        size: self.parent.size
        size_hint: (None, 1)
        font_size: '8sp'
        bold: True
        valign: 'middle'
        halign: 'left'


<NoteLanes>:
    pos: (0, self.scroll_offset)

<NoteLane>:
    width: root.width
    height: 12
    size_hint: (1, None)
    pos: (0, (self.index * 13))
    freq: '%5.2f  ' % tune.ntf(self.note.lower(), self.octave)

    canvas:
        Color:
            rgba: (0.85,0.85,0.85,0.75) if self.note.lower() == 'c' else (0.9,0.9,0.9,0.75)
        Rectangle:
            pos: self.pos
            size: self.size

    PianoKey:
        pos: (0, self.parent.pos[1])
        note: self.parent.note
        octave: self.parent.octave
        freq: self.parent.freq
        width: 60
        height: 12

        canvas:
            Color:
                rgba: (1,1,1,1) if len(self.note) == 1 else (0,0,0,1)
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: self.parent.freq
            color: 0.5, 0.5, 0.5, 1
            pos: self.parent.pos
            size: self.parent.size
            text_size: self.size
            size_hint: (None, 1)
            font_size: '8sp'
            bold: True
            pos: (2, self.parent.pos[1])
            valign: 'middle'
            halign: 'right'

        Label:
            text: '' if self.parent.note.lower() != 'c' else '%s%s' % (self.parent.note, self.parent.octave)
            color: (0,0,0,1) if len(self.parent.note) == 1 else (1,1,1,1)
            pos: self.parent.pos
            size: self.parent.size
            text_size: self.size
            size_hint: (None, 1)
            font_size: '8sp'
            bold: True
            pos: (2, self.parent.pos[1])
            valign: 'middle'
            halign: 'left'

''')

def snap_to_grid(length=1, grid=1, roundup=False):
    if roundup:
        trunclength = (length // grid) * grid
        length = grid + trunclength if length - trunclength > 0 else trunclength
    else:
        length = (length // grid) * grid
    return length

def length_to_pixels(length, snap=False, grid=1, roundup=False):
    if snap:
        length = snap_to_grid(length, grid, roundup)
    return length * 60.0

def pixels_to_length(pixels, snap=False, grid=1, roundup=False):
    length = pixels / 60.0
    if snap:
        length = snap_to_grid(length, grid, roundup)
    return length

class SnapCheckBox(CheckBox, Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        app = App.get_running_app()
        self.active = app.snap
        self.bind(active=self.on_checkbox_active)

    def on_checkbox_active(self, obj, value):
        app = App.get_running_app()
        app.snap = value

class SelectAllButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.select_all()

class ClearButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.clear_selections()

class RenderButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.offline_render()

class NoteLanes(FloatLayout):
    new_note = ObjectProperty()
    drawing_note = BooleanProperty(False)
    notes = ListProperty([])
    scroll_offset = NumericProperty(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keyboard = Window.request_keyboard(self._cleanup_keyboard, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
        self._keyboard.bind(on_key_up=self._on_key_up)

        count = 0
        for octave in range(11):
            for note in NOTES:
                n = NoteLane(count, note, octave)
                self.add_widget(n)
                self.notes.append(n)
                count += 1

    def _cleanup_keyboard(self):
        self._keyboard.unbind(on_key_down=self._on_key_down)
        self._keyboard.unbind(on_key_up=self._on_key_up)

    def _on_key_up(self, keyboard, keycode):
        app = App.get_running_app()
        if keycode[1] == 'shift':
            app.shift_enabled = False

        print('up',keycode)

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        print('down',keycode, modifiers)
        app = App.get_running_app()
        app.shift_enabled = 'shift' in modifiers
        scroll_amount = 13 if 'shift' not in modifiers else 130
        if keycode[1] in ('up', 'k'):
            self.scroll_offset -= scroll_amount
        elif keycode[1] in ('down', 'j'):
            self.scroll_offset += scroll_amount
        elif keycode[1] == 'i':
            app.input_mode = 'insert'
        elif keycode[1] == 's':
            app.input_mode = 'select'
        elif keycode[1] == 'a':
            app.select_all()
        elif keycode[1] == 'c':
            app.clear_selections()
        elif keycode[1] == 'r':
            app.offline_render()
        elif keycode[1] in ('x', 'delete', 'backspace'):
            app.delete_selected()

    def on_pos(self, obj, value):
        for notelane in self.notes:
            notelane.pos = (0, (notelane.index * 13) + self.scroll_offset)

    def init_new_note(self, index, pos):
        if pos[0] > 60:
            app = App.get_running_app()
            notelane = self.notes[index]
            self.new_note = Note(index, pos, notelane, app.snap, app.grid) 
            self.drawing_note = True
            notelane.notes.append(self.new_note)
            notelane.add_widget(self.new_note)

    def update_new_note(self, pos):
        if self.drawing_note:
            self.new_note.update(pos)

    def finalize_new_note(self, pos):
        if self.drawing_note:
            self.new_note.update(pos)
            self.drawing_note = False

class Note(Widget):
    index = NumericProperty()
    notelane = ObjectProperty()
    highlighted = BooleanProperty(False)
    freq = StringProperty()
    onset = NumericProperty()
    length = NumericProperty()
    minlength = NumericProperty(0.01)
    beat = NumericProperty() # index pos in grid
    snap = BooleanProperty(False)
    grid = NumericProperty() # gridsize

    def __init__(self, index, pos, notelane, snap, grid, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.notelane = notelane
        self.index = index
        self.freq = notelane.freq
        self.snap = snap
        self.grid = grid
        self.minlength = self.grid if self.snap else self.minlength

        self.bind(length=self._redraw)
        self.bind(onset=self._redraw)

        self.onset = pixels_to_length(pos[0], snap, grid)
        self.length = self.minlength

    def _redraw(self, obj, value):
        self.width = max(length_to_pixels(self.length), 5)
        self.pos = (length_to_pixels(self.onset), self.notelane.pos[1])

    def update(self, pos):
        width = pos[0] - self.pos[0]
        print(width, self.snap, self.grid, self.minlength)
        self.length = max(pixels_to_length(width, self.snap, self.grid, True), self.minlength)

    def toggle_highlight(self):
        self.highlighted = not self.highlighted

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            if app.input_mode == 'select':
                if not app.shift_enabled:
                    app.clear_selections()
                self.toggle_highlight()
                return True

        return super().on_touch_down(touch)

class NoteLane(Widget):
    note = StringProperty() # pitch class name
    octave = NumericProperty()
    freq = StringProperty()
    notes = ListProperty() # Note() widget references
    index = NumericProperty()

    def __init__(self, index, note, octave, *args, **kwargs):
        self.index = index
        self.note = note
        self.octave = octave
        super().__init__(*args, **kwargs)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            if app.input_mode == 'insert':
                self.parent.init_new_note(self.index, touch.pos)
                return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            if app.input_mode == 'insert':
                if app.shift_enabled or self.parent.new_note.index == self.index:
                    self.parent.update_new_note(touch.pos)       
                else:
                    self.parent.init_new_note(self.index, touch.pos)
                return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.parent.finalize_new_note(touch.pos)       
            return True
        return super().on_touch_up(touch)

    def on_pos(self, obj, value):
        for note in self.notes:
            note.pos = (note.pos[0], self.pos[1])

class PianoKey(Widget):
    note = StringProperty()
    octave = NumericProperty()
    freq = StringProperty()


class HeaderBar(FloatLayout):
    statusline = StringProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_status()

    def update_status(self):
        self.statusline = '%5.2f | %s | %s | %s' % (self.get_bpm(), self.get_div(), self.get_barlength(), self.get_input_mode())

    def get_bpm(self):
        app = App.get_running_app()
        return app.bpm

    def get_div(self):
        app = App.get_running_app()
        return app.grid

    def get_barlength(self):
        app = App.get_running_app()
        return app.barlength

    def get_input_mode(self):
        app = App.get_running_app()
        return app.input_mode

class PianoRollWrapper(BoxLayout):
    orientation = 'vertical'
    gridwidth = NumericProperty(30)
    barlength = NumericProperty(4)
    bpm = NumericProperty(120.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with self.canvas:
            Color(0.8,0.8,0.8,1)
            self.r = Rectangle(pos=self.pos, size=self.size)

            self.lines = []
            for i in range(100):
                if i % self.barlength == 0:
                    Color(0,0,0,1)
                else:
                    Color(0,0,0,0.3)

                if i > 0:
                    points = [i * self.gridwidth + 60, 0, i * self.gridwidth + 60, self.height]
                    l = Line(points=points, width=1)
                    self.lines += [ l ]

        self.bind(pos=self.update_grid)
        self.bind(size=self.update_grid)

    def update_grid(self, *args):
        self.r.size = self.size
        self.gridwidth = length_to_pixels(60.0 / self.bpm)
        for i, l in enumerate(self.lines):
            x = (i+1) * self.gridwidth + 60
            l.points = [x, 0, x, self.height]
        
class PianoRoll(App):
    input_mode = StringProperty('insert')
    bpm = NumericProperty(120.0)
    snap = BooleanProperty(True)
    grid = NumericProperty(0.5)
    barlength = NumericProperty(4)
    shift_enabled = BooleanProperty(False)
    rendering = BooleanProperty(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(bpm=self._calc_gridsize)

    def _calc_gridsize(self, obj, value):
        self.grid = 60.0 / self.bpm

    def build(self):
        self.wrapper = PianoRollWrapper()
        self.lanes = NoteLanes()
        self.header = HeaderBar()

        self.wrapper.add_widget(self.lanes)
        self.wrapper.add_widget(self.header)
        return self.wrapper

    def on_input_mode(self, obj, value):
        self.header.update_status()

    def select_all(self):
        for notelane in self.lanes.notes:
            for note in notelane.notes:
                note.highlighted = True

    def clear_selections(self):
        for notelane in self.lanes.notes:
            for note in notelane.notes:
                note.highlighted = False

    def delete_selected(self):
        for notelane in self.lanes.notes:
            for noteindex, note in enumerate(notelane.notes):
                if note.highlighted:
                    notelane.remove_widget(note)
                    notelane.notes[noteindex] = None
            notelane.notes = filter(None, notelane.notes)

    def offline_render(self):
        print('BEGIN RENDER')
        self.rendering = True
        notes = []
        maxlength = 0
        for notelane in self.lanes.notes:
            for noteindex, note in enumerate(notelane.notes):
                notes += [(note.onset, note.length, note.freq)]
                maxlength = max(maxlength, note.onset + note.length)

        out = dsp.buffer(length=maxlength)

        # load instrument
        manager = mp.Manager()
        bus = manager.Namespace()
        bus.stop_all = manager.Event() # voices
        bus.shutdown_flag = manager.Event() # render & analysis processes
        bus.stop_listening = manager.Event() # midi listeners
        instrument = orc.load_instrument('default', 'orc/pianotone.py', bus)

        for note in notes:
            params = {'length': float(note[1]), 'freq': float(note[2])}
            ctx = instrument.create_ctx(params)
            generator = instrument.renderer.play(ctx)
            for snd in generator:
                out.dub(snd, float(note[0]))

        # render
        out.write('pianoroll_render.wav')
        self.rendering = False
        print('DONE RENDERING')

if __name__ == '__main__':
    PianoRoll().run()
