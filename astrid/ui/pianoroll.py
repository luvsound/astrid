from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Bezier, Line, Ellipse, Rectangle
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty, ListProperty, ObjectProperty, BooleanProperty
import random
from pippi import tune

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
            rgba: 0,0,0.5,1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: self.parent.statusline
        color: 1, 1, 1, 1
        pos: self.parent.pos
        size: self.parent.size
        text_size: self.size
        size_hint: (None, 1)
        font_size: '10sp'
        bold: True
        pos: (2, self.parent.pos[1])
        valign: 'middle'
        halign: 'left'

    BoxLayout:
        width: 420
        size_hint: (None, 1)
        pos: (root.width - self.width, self.parent.pos[1])
        orientation: 'horizontal'
        InsertButton:
            font_size: '10sp'
            text: '(I)nsert'
        SelectButton:
            font_size: '10sp'
            text: '(S)elect'
        SelectAllButton:
            font_size: '10sp'
            text: 'Select (A)ll'
        ClearButton:
            font_size: '10sp'
            text: '(C)lear Selections'
        DeleteButton:
            font_size: '10sp'
            text: '(D)elete Selected'

<Note>:
    height: 12
    minimum_width: 5
    canvas:
        Color:
            rgba: (0,0.25,0.25,0.5) if self.highlighted else (0.75,0,0.75,0.5)
        Rectangle:
            pos: self.pos
            size: self.size

<NoteLanes>:
    pos: (0, self.scroll_offset)

<NoteLane>:
    width: root.width
    height: 12
    size_hint: (1, None)
    pos: (0, (self.index * 13))
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
        width: 60
        height: 12

        canvas:
            Color:
                rgba: (1,1,1,1) if len(self.note) == 1 else (0,0,0,1)
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: '%5.2f  ' % tune.ntf(self.parent.note.lower(), self.parent.octave)
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

class InsertButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.input_mode = 'insert'

class SelectButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.input_mode = 'select'

class SelectAllButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.select_all()

class ClearButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.clear_selections()

class DeleteButton(Button):
    def on_press(self):
        app = App.get_running_app()
        app.delete_selected()

class NoteLane(Widget):
    note = StringProperty() # pitch class name
    octave = NumericProperty()
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
            if app.shift_enabled or self.parent.new_note.index == self.index:
                self.parent.update_new_note(touch.pos)       
            elif app.input_mode == 'insert':
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

class Note(Widget):
    index = NumericProperty()
    notelane = ObjectProperty()
    highlighted = BooleanProperty(False)

    def __init__(self, index, pos, notelane, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.notelane = notelane
        self.pos = (pos[0], self.notelane.pos[1])
        self.width = 5
        self.index = index

    def update(self, pos):
        width = pos[0] - self.pos[0]
        self.width = max(width, 5)

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

    def _on_key_down(self, keyboard, keycode, text, modifiers):
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
        elif keycode[1] == 'd':
            app.delete_selected()

    def on_pos(self, obj, value):
        for notelane in self.notes:
            notelane.pos = (0, (notelane.index * 13) + self.scroll_offset)

    def init_new_note(self, index, pos):
        notelane = self.notes[index]
        self.new_note = Note(index, pos, notelane) 
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
        return app.grid_div

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
                    points = [i * self.gridwidth, 0, i * self.gridwidth, self.height]
                    l = Line(points=points, width=1)
                    self.lines += [ l ]

        self.bind(pos=self.update_grid)
        self.bind(size=self.update_grid)

    def update_grid(self, *args):
        self.r.size = self.size
        for i, l in enumerate(self.lines):
            x = (i+1) * self.gridwidth + 60
            l.points = [x, 0, x, self.height]
        

class PianoRoll(App):
    input_mode = StringProperty('insert')
    bpm = NumericProperty(120.0)
    grid_div = NumericProperty(1)
    barlength = NumericProperty(4)
    shift_enabled = BooleanProperty(False)

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

if __name__ == '__main__':
    PianoRoll().run()
