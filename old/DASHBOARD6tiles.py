#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Dashboard v3.5 – Neon Edition (6 Tiles)
Kivy + Kivy Garden Graph – APK-ready, smooth curves, neon glow
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

# --- Garden Graph Import Fix (lokales Modul einbinden) ---
import os, sys, math, random, time
from collections import deque

BASE_DIR = os.path.dirname(__file__)
GARDEN_DIR = os.path.join(BASE_DIR, "garden")
if GARDEN_DIR not in sys.path:
    sys.path.append(GARDEN_DIR)

from kivy_garden.graph import Graph, MeshLinePlot
# ---------------------------------------------------------

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty, BooleanProperty
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp

# --- optional Emoji-Font (falls vorhanden, kein Crash wenn nicht) ---
try:
    LabelBase.register(
        name="Emoji",
        fn_regular="/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
    )
except Exception:
    pass

# Startgröße für Desktop-Tests
Window.size = (1280, 740)

KV = """
#:import Graph kivy_garden.graph.Graph

<Header@BoxLayout>:
    size_hint_y: None
    height: "88dp"
    padding: 14
    spacing: 14
    canvas.before:
        Color:
            rgba: 0.05, 0.08, 0.06, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: "horizontal"
        spacing: 10
        Label:
            text: "🌱  VIVOSUN Thermo Dashboard v3.5 – Neon"
            bold: True
            font_size: "28sp"
            color: 0.90, 1, 0.92, 1
            halign: "left"
            valign: "middle"
            text_size: self.size
        Label:
            id: clocklbl
            text: app.header_right
            size_hint_x: None
            width: self.texture_size[0] + dp(18)
            color: 0.80, 1.00, 0.85, 1

<Footer>:
    size_hint_y: None
    height: "66dp"
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
        width: "168dp"
        background_normal: ""
        background_color: 0.12, 0.42, 0.22, 1
        on_release: app.toggle_sim()

<Tile>:
    orientation: "vertical"
    padding: 10
    spacing: 8
    canvas.before:
        # Tile-Body
        Color:
            rgba: 0.07, 0.11, 0.08, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16,16,16,16]
        # Neon-Glow (doppelter, dezenter Glow)
        Color:
            rgba: self.accent[0], self.accent[1], self.accent[2], 0.15
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
            width: 1.25
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
        font_size: "42sp"
        bold: True
        size_hint_y: None
        height: "58dp"
    Graph:
        id: g
        xmin: 0
        xmax: 60
        ymin: root.ymin
        ymax: root.ymax
        draw_border: False
        background_color: 0.05, 0.07, 0.06, 1
        tick_color: 0.35, 0.8, 0.45, 1
        label_options: {'color': (0.78, 1, 0.82, 1), 'bold': False}
        x_ticks_major: 10
        # y_ticks_major darf float sein (wir casten intern auf int beim Zeichnen)
        y_ticks_major: (root.ymax - root.ymin) / 5 if (root.ymax - root.ymin) > 0 else 1
        precision: "1"
        size_hint_y: 1

<Dashboard>:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: 0.02, 0.04 + (0.01 * (1 + (app._bg_phase % 1))), 0.03, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Header:
        id: header
    GridLayout:
        id: grid
        cols: 3
        rows: 2
        padding: 12
        spacing: 12
        Tile:
            id: tile_t_int
            title: "🌡 Intern Temp"
            unit: "°C"
            ymin: 10
            ymax: 40
            accent: 1, 0.45, 0.45
        Tile:
            id: tile_h_int
            title: "💧 Intern Hum"
            unit: "%"
            ymin: 20
            ymax: 100
            accent: 0.35, 0.70, 1
        Tile:
            id: tile_vpd_int
            title: "🌿 VPD Intern"
            unit: "kPa"
            ymin: 0
            ymax: 2.0
            accent: 0.85, 1.0, 0.45
        Tile:
            id: tile_t_ext
            title: "🌡 Extern Temp"
            unit: "°C"
            ymin: -5
            ymax: 45
            accent: 1.0, 0.70, 0.35
        Tile:
            id: tile_h_ext
            title: "💧 Extern Hum"
            unit: "%"
            ymin: 15
            ymax: 100
            accent: 0.45, 0.95, 1.0
        Tile:
            id: tile_batt
            title: "🔋 Batterie"
            unit: "%"
            ymin: 0
            ymax: 100
            accent: 0.60, 1.0, 0.60
    Footer:
        id: footer

Dashboard:
"""

# ---------- Smoothing (sanfte Zwischenschritte für weiche Kurven) ----------
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

# ------------------------------ Widgets ------------------------------
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

# ------------------------------ App ------------------------------
class VivosunApp(App):
    running = BooleanProperty(True)
    header_right = StringProperty("")
    _bg_phase = NumericProperty(0)

    def build(self):
        self.root = Builder.load_string(KV)
        self.footer = self.root.ids.footer

        ids = self.root.ids
        self.tiles = {
            "t_int": ids.tile_t_int,
            "h_int": ids.tile_h_int,
            "vpd_int": ids.tile_vpd_int,
            "t_ext": ids.tile_t_ext,
            "h_ext": ids.tile_h_ext,
            "batt":  ids.tile_batt,
        }

        # Deques (X läuft 0..n-1)
        self.buffers = {k: deque(maxlen=60) for k in self.tiles}
        self.plots = {}
        for k, t in self.tiles.items():
            p = MeshLinePlot(color=[*t.accent, 1])
            t.ids.g.add_plot(p)
            self.plots[k] = p

        self._t0 = time.time()
        self._update_ev = Clock.schedule_interval(self.update_all, 0.33)
        self._led_ev = Clock.schedule_interval(self._led_breathe, 1.0)
        self._bg_ev = Clock.schedule_interval(self._bg_animate, 0.12)
        Window.bind(on_focus=self._on_focus)
        return self.root

    def _phase(self, div): 
        return (time.time() - self._t0) / max(1e-6, div)

    def update_all(self, *_):
        if not self.running:
            return

        # --- Synth-Werte
        t_int = 25 + 2.3 * math.sin(self._phase(9.5)) + random.uniform(-0.22, 0.22)
        h_int = 62 + 7.4 * math.cos(self._phase(15.2)) + random.uniform(-0.8, 0.8)
        vpd   = max(0.0, (1 - h_int/100.0) * (t_int/10.0))
        t_ext = 18 + 6.4 * math.sin(self._phase(22.0)+0.6) + random.uniform(-0.28,0.28)
        h_ext = 55 + 11.5 * math.cos(self._phase(30.0)+0.8) + random.uniform(-1.0,1.0)
        last_b = self.buffers["batt"][-1] if self.buffers["batt"] else 88
        batt = max(0, min(100, last_b + random.choice([-0.1, 0, 0, 0.1])))

        vals = {
            "t_int": (t_int, "°C", 1),
            "h_int": (h_int, "%", 0),
            "vpd_int": (vpd, "kPa", 2),
            "t_ext": (t_ext, "°C", 1),
            "h_ext": (h_ext, "%", 0),
            "batt":  (batt, "%", 0),
        }
        for k, (v, u, p) in vals.items():
            self._push(k, v)
            self._upd_label_and_color(k, v, u, p)

        # Uhr (Sekunden fett)
        sec = int(time.time()) % 60
        self.header_right = time.strftime("%H:%M:") + f"[b]{sec:02d}[/b]"

        # Status-Pulse
        now = int(time.time())
        if now % 19 == 0:
            self._pulse_led([1, 0.85, 0.0, 1], "🟡 Daten Refresh…")
        elif now % 23 == 0:
            self._pulse_led([0, 1, 0, 1], "🟢 Simulation aktiv")

    def _push(self, key, val):
        b = self.buffers[key]
        b.append(val)
        pts = list(enumerate(b))
        pts = _smooth_points(pts, factor=3)
        self.plots[key].points = pts

    def _upd_label_and_color(self, k, v, u, p):
        t = self.tiles[k]
        t.value_text = f"{v:.{p}f} {u}"
        base = {
            "t_int": [1, 0.45, 0.45],
            "h_int": [0.35, 0.70, 1],
            "vpd_int": [0.85, 1, 0.45],
            "t_ext": [1, 0.70, 0.35],
            "h_ext": [0.45, 0.95, 1],
            "batt":  [0.60, 1, 0.60],
        }[k]
        cur = t.accent
        lerp = 0.10
        t.accent = [cur[i] + (base[i]-cur[i]) * lerp for i in range(3)]

    # Controls & FX
    def toggle_sim(self):
        self.running = not self.running
        self._pulse_led([0, 1, 0, 1] if self.running else [1, 0.35, 0.35, 1],
                        "🟢 Simulation fortgesetzt" if self.running else "⏸️ Simulation pausiert")

    def _pulse_led(self, color, text):
        self.footer.status_text = text
        (Animation(led_color=color, duration=0.25) +
         Animation(led_color=[0, 0.55, 0, 1], duration=0.60)).start(self.footer)

    def _led_breathe(self, *_):
        if self.running:
            g = 0.62 + 0.12 * math.sin(time.time() * 1.25)
            self.footer.led_color = [0, g, 0, 1]

    def _bg_animate(self, *_):
        self._bg_phase = (self._bg_phase + 0.03) % 1.0

    def _on_focus(self, _win, focus):
        self._update_ev.cancel()
        self._update_ev = Clock.schedule_interval(self.update_all, 0.33 if focus else 0.75)

# -------------------------------------------------------------------
if __name__ == "__main__":
    VivosunApp().run()
