#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Neon Scatter – T vs. RH (VPD-Style)
Kivy + Kivy Garden Graph + Canvas-Dots Overlay (APK-ready)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, sys, math, random, time
from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty, BooleanProperty
from kivy.garden.graph import Graph
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, InstructionGroup
from kivy.core.text import LabelBase

# Fallback-Pfad für lokalen Garden-Graph (schadet nicht)
sys.path.append(os.path.join(os.path.dirname(__file__), "garden", "graph"))

# Emoji-Font optional registrieren (kein Crash, wenn nicht vorhanden)
try:
    LabelBase.register(
        name="Emoji",
        fn_regular="/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
    )
except Exception:
    pass

Window.size = (1200, 720)

KV = """
<Header@BoxLayout>:
    size_hint_y: None
    height: "86dp"
    padding: 12
    spacing: 12
    canvas.before:
        Color:
            rgba: 0.06, 0.10, 0.07, 1
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: "🌿  VIVOSUN Neon Scatter (T vs RH)"
        bold: True
        font_size: "28sp"
        color: 0.9, 1, 0.9, 1
    Label:
        text: app.header_right
        size_hint_x: None
        width: self.texture_size[0] + dp(12)
        color: 0.8, 1, 0.8, 1

<Footer>:
    size_hint_y: None
    height: "64dp"
    padding: 10
    spacing: 10
    canvas.before:
        Color:
            rgba: 0.05, 0.09, 0.06, 1
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: root.status_text
        color: 1,1,1,1
        font_size: "18sp"

<ScatterPane>:
    orientation: "vertical"
    padding: 12
    spacing: 12
    canvas.before:
        # dezenter dynamischer Hintergrund
        Color:
            rgba: 0.02, 0.04 + (0.01 * (1 + (app._bg_phase % 1))), 0.03, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Header:
    BoxLayout:
        size_hint_y: 1
        padding: 8
        spacing: 8
        canvas.before:
            Color:
                rgba: 0.07, 0.11, 0.08, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [16,16,16,16]

        Graph:
            id: graph
            xlabel: "Temperature (°C)"
            ylabel: "Relative Humidity (%)"
            xmin: 10
            xmax: 40
            ymin: 15
            ymax: 100
            x_ticks_major: 5
            y_ticks_major: 10
            precision: "0"
            draw_border: False
            background_color: 0.05, 0.07, 0.06, 1
            tick_color: 0.35, 0.8, 0.45, 1
            label_options: {'color': (0.78, 1, 0.82, 1), 'bold': False}

    Footer:
        id: footer

ScatterPane:
"""

# ---------- Helper: Dots-Overlay über dem Graph ----------
class NeonDotsOverlay:
    """
    Zeichnet Scatter-Dots direkt auf graph.canvas.after.
    Koordinaten-Mapping: Datenraum (x,y) -> Widgetraum (px,py).
    """
    def __init__(self, graph, radius=5.0):
        self.graph = graph
        self.radius = radius
        self._group = InstructionGroup()
        self.graph.canvas.after.add(self._group)

    def clear(self):
        self._group.clear()

    def _map(self, x, y):
        g = self.graph
        if g.xmax == g.xmin:
            return 0, 0
        if g.ymax == g.ymin:
            return 0, 0
        px = (x - g.xmin) / (g.xmax - g.xmin) * g.width + g.x
        py = (y - g.ymin) / (g.ymax - g.ymin) * g.height + g.y
        # in lokale Koordinaten der Canvas (0..width/height relativ zum Graph)
        # Für canvas.after verwenden wir absolute pos; Ellipse erwartet Eltern-Koords:
        return px, py

    def add_points(self, points, color=(0.4, 1.0, 0.7, 0.9), glow=True):
        """
        points: Iterable[(x,y)]
        color: RGBA
        """
        # leichter Glow: zwei Ellipsen (groß transparent + klein kräftig)
        r = self.radius
        r2 = r * 2.2 if glow else r
        cr, cg, cb, ca = color

        for (x, y) in points:
            px, py = self._map(x, y)
            if not (self.graph.x <= px <= self.graph.right and self.graph.y <= py <= self.graph.top):
                continue
            if glow:
                self._group.add(Color(cr, cg, cb, ca * 0.18))
                self._group.add(Ellipse(pos=(px - r2, py - r2), size=(r2 * 2, r2 * 2)))
            self._group.add(Color(cr, cg, cb, ca))
            self._group.add(Ellipse(pos=(px - r, py - r), size=(r * 2, r * 2)))

# ---------- Root Widgets ----------
class Footer(BoxLayout):
    status_text = StringProperty("🟢 Neon Scatter live")

class ScatterPane(BoxLayout):
    pass

# ---------- App ----------
class NeonScatterApp(App):
    running = BooleanProperty(True)
    header_right = StringProperty("")
    _bg_phase = NumericProperty(0)

    def build(self):
        self.root = Builder.load_string(KV)
        self.footer = self.root.ids.footer
        self.graph = self.root.ids.graph

        # Overlay für Punkte
        self.overlay = NeonDotsOverlay(self.graph, radius=4.0)

        # Datenpuffer (T vs RH)
        self.points = deque(maxlen=600)   # ~10 Minuten bei 1 Hz mit 1 Punkt/Sec
        self._t0 = time.time()

        # Timer
        self._update_ev = Clock.schedule_interval(self._update, 0.50)
        Clock.schedule_interval(self._bg_animate, 0.12)

        return self.root

    # simple Synthese einer VPD-ähnlichen Punktwolke
    def _synth_point(self):
        phase = (time.time() - self._t0)
        # Temperatur: 18..32°C
        t = 25 + 6 * math.sin(phase * 0.09 + 0.7) + random.uniform(-0.6, 0.6)
        # RH: 35..85%, leicht korreliert
        rh_base = 60 - 10 * math.sin(phase * 0.07)
        rh = rh_base + random.uniform(-18, 18)
        rh = max(15, min(100, rh))
        return (max(10, min(40, t)), rh)

    def _update(self, *_):
        if not self.running:
            return

        # neue Punkte sammeln
        for _ in range(6):  # pro Tick einige Punkte → dichter Scatter
            self.points.append(self._synth_point())

        # Anzeige
        self.overlay.clear()

        # Farbstreu: grün (ok), gelb (grenz), rot (zu trocken/zu feucht)
        # hier sehr einfach: RH < 40% → rot, 40..70 → grün, >70 → gelb
        cluster_green = []
        cluster_yellow = []
        cluster_red = []
        for x, y in self.points:
            if y < 40:
                cluster_red.append((x, y))
            elif y > 70:
                cluster_yellow.append((x, y))
            else:
                cluster_green.append((x, y))

        # sanfter Neon-Look
        self.overlay.add_points(cluster_green,  color=(0.40, 1.00, 0.70, 0.95), glow=True)
        self.overlay.add_points(cluster_yellow, color=(1.00, 0.90, 0.40, 0.90), glow=True)
        self.overlay.add_points(cluster_red,    color=(1.00, 0.45, 0.45, 0.90), glow=True)

        # Header-Uhr
        sec = int(time.time()) % 60
        self.header_right = time.strftime("%H:%M:") + f"[b]{sec:02d}[/b]"

        # Footer-Status dezent variieren
        if sec % 20 == 0:
            self.footer.status_text = "🟡 Refresh…"
        elif sec % 23 == 0:
            self.footer.status_text = "🟢 Neon Scatter live"

    def _bg_animate(self, *_):
        self._bg_phase = (self._bg_phase + 0.03) % 1.0

if __name__ == "__main__":
    NeonScatterApp().run()
