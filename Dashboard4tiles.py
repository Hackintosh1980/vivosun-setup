#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Dashboard – Neon 4 Tiles (Temp/Hum In+Out)
Kivy + Garden Graph (lokal) – APK-ready
"""

# --- Garden Graph Import Fix (lokale Kopie einbinden) ---
import os, sys, time, math, random
from collections import deque

BASE_DIR = os.path.dirname(__file__)
GARDEN_DIR = os.path.join(BASE_DIR, "garden")
if GARDEN_DIR not in sys.path:
    sys.path.append(GARDEN_DIR)

from kivy_garden.graph import Graph, MeshLinePlot  # <- deine lokale graph.py

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty, BooleanProperty
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.metrics import dp

# Desktop-Startgröße (optional)
Window.size = (1100, 680)


KV = """
#:import Graph kivy.garden.graph.Graph

<Footer>:
    size_hint_y: None
    height: "62dp"
    padding: 10
    spacing: 10
    canvas.before:
        Color:
            rgba: 0.04, 0.07, 0.05, 1
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: root.status_text
        color: 1,1,1,1
        font_size: "18sp"
        shorten: True
        shorten_from: "right"
    Widget:
        size_hint_x: None
        width: dp(36)
        canvas:
            Color:
                rgba: root.led_color
            Ellipse:
                pos: self.pos
                size: self.size
    Button:
        text: "⏯  Start / Stop"
        size_hint_x: None
        width: "160dp"
        background_normal: ""
        background_color: 0.12, 0.42, 0.22, 1
        on_release: app.toggle_sim()

<Tile>:
    orientation: "vertical"
    padding: 10
    spacing: 8
    canvas.before:
        # Grundpanel
        Color:
            rgba: 0.07, 0.11, 0.08, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16,16,16,16]
        # Neon-Glow dezent
        Color:
            rgba: self.accent[0], self.accent[1], self.accent[2], 0.16
        RoundedRectangle:
            pos: self.x - dp(2), self.y - dp(2)
            size: self.width + dp(4), self.height + dp(4)
            radius: [18,18,18,18]
        Color:
            rgba: self.accent[0], self.accent[1], self.accent[2], 0.10
        RoundedRectangle:
            pos: self.x - dp(5), self.y - dp(5)
            size: self.width + dp(10), self.height + dp(10)
            radius: [22,22,22,22]
        # Rahmen
        Color:
            rgba: self.accent[0], self.accent[1], self.accent[2], 0.28
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 16,16,16,16)
            width: 1.2
    BoxLayout:
        size_hint_y: None
        height: "30dp"
        Label:
            text: root.title
            color: 0.85, 1, 0.9, 1
            font_size: "16sp"
            halign: "left"
            valign: "middle"
            text_size: self.size
    Label:
        id: big
        text: root.value_text
        color: 1,1,1,1
        font_size: "40sp"
        bold: True
        size_hint_y: None
        height: "56dp"
    Graph:
        id: g
        xmin: 0
        xmax: 120
        ymin: root.ymin
        ymax: root.ymax
        x_ticks_major: 6         # 0..120 → alle 20
        y_ticks_major: 5         # 5 Rasterlinien
        x_grid_label: False
        y_grid_label: False
        draw_border: False
        background_color: 0.05, 0.07, 0.06, 1
        tick_color: 0.35, 0.8, 0.45, 1
        size_hint_y: 1

<Dashboard>:
    orientation: "vertical"
    # Hintergrund-Neon-Puls
    canvas.before:
        Color:
            rgba: 0.02, 0.04 + (0.01 * (1 + (app._bg_phase % 1))), 0.03, 1
        Rectangle:
            pos: self.pos
            size: self.size

    GridLayout:
        id: grid
        cols: 2
        rows: 2
        padding: 12
        spacing: 12
        Tile:
            id: tile_t_in
            title: "🌡 Temp IN"
            unit: "°C"
            ymin: 10
            ymax: 40
            accent: 1.00, 0.45, 0.45
        Tile:
            id: tile_t_out
            title: "🌡 Temp OUT"
            unit: "°C"
            ymin: -5
            ymax: 45
            accent: 1.0, 0.70, 0.35
        Tile:
            id: tile_h_in
            title: "💧 Hum IN"
            unit: "%"
            ymin: 20
            ymax: 100
            accent: 0.35, 0.70, 1.0
        Tile:
            id: tile_h_out
            title: "💧 Hum OUT"
            unit: "%"
            ymin: 15
            ymax: 100
            accent: 0.45, 0.95, 1.0
    Footer:
        id: footer

Dashboard:
"""


# --- weiches Linien-Glätten (einfach, fix & schnell)
def _smooth_points(points, factor=2):
    if len(points) < 3 or factor < 2:
        return points
    out = []
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        out.append((x0, y0))
        mx = (x0 + x1) / 2.0
        my = (y0 + y1) / 2.0
        if factor >= 2:
            out.append((mx, (y0 + my) / 2.0))
        if factor >= 3:
            out.append(((mx + x1) / 2.0, (my + y1) / 2.0))
    out.append(points[-1])
    return out


class Footer(BoxLayout):
    led_color = ListProperty([0, 1, 0, 1])
    status_text = StringProperty("🟢 Simulation aktiv")


class Tile(BoxLayout):
    title = StringProperty("Title")
    unit = StringProperty("")
    value_text = StringProperty("--")
    ymin = NumericProperty(0)
    ymax = NumericProperty(100)
    accent = ListProperty([0.8, 1.0, 0.6])


class Dashboard(BoxLayout):
    pass


class Vivosun4TilesApp(App):
    running = BooleanProperty(True)
    _bg_phase = NumericProperty(0)

    def build(self):
        self.root = Builder.load_string(KV)
        self.footer = self.root.ids.footer

        ids = self.root.ids
        self.tiles = {
            "t_in":  ids.tile_t_in,
            "t_out": ids.tile_t_out,
            "h_in":  ids.tile_h_in,
            "h_out": ids.tile_h_out,
        }

        # Datenpuffer & Plots
        self.buffers = {k: deque(maxlen=120) for k in self.tiles}  # 120 Punkte sichtbar
        self.plots = {}
        colors = {
            "t_in":  [1.00, 0.45, 0.45, 1],
            "t_out": [1.00, 0.70, 0.35, 1],
            "h_in":  [0.35, 0.70, 1.00, 1],
            "h_out": [0.45, 0.95, 1.00, 1],
        }
        for key, t in self.tiles.items():
            p = MeshLinePlot(color=colors[key])
            t.ids.g.add_plot(p)
            self.plots[key] = p

        self._t0 = time.time()
        self._update_ev = Clock.schedule_interval(self.update_all, 0.25)
        self._bg_ev = Clock.schedule_interval(self._bg_animate, 0.12)
        return self.root

    # --- Simulation
    def _phase(self, div):
        return (time.time() - self._t0) / max(1e-6, div)

    def update_all(self, *_):
        if not self.running:
            return

        # Synth-Werte
        t_in  = 25 + 2.3 * math.sin(self._phase(9.0))  + random.uniform(-0.15, 0.15)
        t_out = 18 + 6.0 * math.sin(self._phase(20.0)) + random.uniform(-0.25, 0.25)
        h_in  = 62 + 7.0 * math.cos(self._phase(14.0)) + random.uniform(-0.8, 0.8)
        h_out = 55 + 10.0* math.cos(self._phase(28.0)) + random.uniform(-1.0, 1.0)

        self._push("t_in",  t_in);   self._set_label("t_in",  t_in,  "°C", 1)
        self._push("t_out", t_out);  self._set_label("t_out", t_out, "°C", 1)
        self._push("h_in",  h_in);   self._set_label("h_in",  h_in,  "%",  0)
        self._push("h_out", h_out);  self._set_label("h_out", h_out, "%",  0)

        # sanfter Status-Pulse alle ~20–25s
        now = int(time.time())
        if now % 22 == 0:
            self._pulse_led([0.9, 0.9, 0.2, 1], "🟡 Daten Refresh …")
        elif now % 25 == 0:
            self._pulse_led([0, 1, 0, 1], "🟢 Simulation aktiv")

    def _push(self, key, val):
        b = self.buffers[key]
        b.append(val)
        pts = list(enumerate(b))            # x: 0..N-1
        pts = _smooth_points(pts, factor=3) # weichzeichnen
        self.plots[key].points = pts

    def _set_label(self, key, value, unit, prec):
        t = self.tiles[key]
        t.value_text = f"{value:.{prec}f} {unit}"

    # --- Controls & FX
    def toggle_sim(self):
        self.running = not self.running
        if self.running:
            self._pulse_led([0, 1, 0, 1], "🟢 Simulation fortgesetzt")
        else:
            self._pulse_led([1, 0.35, 0.35, 1], "⏸️ Simulation pausiert")

    def _pulse_led(self, color, text):
        self.footer.status_text = text
        (Animation(led_color=color, duration=0.25) +
         Animation(led_color=[0, 0.55, 0, 1], duration=0.60)).start(self.footer)

    def _bg_animate(self, *_):
        self._bg_phase = (self._bg_phase + 0.03) % 1.0


if __name__ == "__main__":
    Vivosun4TilesApp().run()
