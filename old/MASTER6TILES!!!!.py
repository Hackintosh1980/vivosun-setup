#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN 6-Tile Sinus Test – stabile Live-Animation
"""

import os, sys, math, time
from collections import deque
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty

# --- Garden-Pfad fix ---
base = os.path.dirname(__file__)
garden_path = os.path.join(base, "garden")
if garden_path not in sys.path:
    sys.path.append(garden_path)
from kivy_garden.graph import Graph, MeshLinePlot


KV = """
<Tile>:
    orientation: "vertical"
    padding: 8
    spacing: 6
    canvas.before:
        Color:
            rgba: 0.07, 0.11, 0.08, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14]
    Label:
        text: root.title
        color: 0.9, 1, 0.9, 1
        font_size: "18sp"
        bold: True
        size_hint_y: None
        height: "28dp"
    Graph:
        id: g
        xmin: 0
        xmax: 100
        ymin: -1.2
        ymax: 1.2
        background_color: 0, 0, 0, 1
        tick_color: 0.35, 1, 0.45, 0.4
        x_ticks_major: 20
        y_ticks_major: 1
        draw_border: False
        x_grid: False
        y_grid: False

<Dashboard>:
    orientation: "vertical"
    padding: 10
    spacing: 10
    GridLayout:
        id: grid
        cols: 3
        rows: 2
        spacing: 10
        Tile:
            id: t1
            title: "🌡 Temp In"
            accent: 1, 0.45, 0.45
        Tile:
            id: t2
            title: "💧 Hum In"
            accent: 0.35, 0.75, 1
        Tile:
            id: t3
            title: "🌿 VPD"
            accent: 0.85, 1, 0.45
        Tile:
            id: t4
            title: "🌡 Temp Out"
            accent: 1, 0.7, 0.35
        Tile:
            id: t5
            title: "💧 Hum Out"
            accent: 0.45, 0.95, 1
        Tile:
            id: t6
            title: "🔋 Battery"
            accent: 0.6, 1, 0.6

Dashboard:
"""


class Tile(BoxLayout):
    title = StringProperty("Sensor")
    accent = ListProperty([0.8, 1.0, 0.6])


class Dashboard(BoxLayout):
    pass


class Vivosun6GraphApp(App):
    def build(self):
        self.root = Builder.load_string(KV)
        ids = self.root.ids

        self.tiles = [ids.t1, ids.t2, ids.t3, ids.t4, ids.t5, ids.t6]
        self.plots = []
        self.buffers = []

        for t in self.tiles:
            plot = MeshLinePlot(color=[*t.accent, 1])
            t.ids.g.add_plot(plot)
            self.plots.append(plot)
            self.buffers.append(deque(maxlen=100))

        self.phase = 0.0
        self.phase_offsets = [0, 0.6, 1.2, 1.8, 2.4, 3.0]

        # Clock-Event speichern → bleibt aktiv auch bei Surface-Neustart
        self._clock_ev = Clock.schedule_interval(self.update_curves, 1/30.0)
        return self.root

    def update_curves(self, dt):
        self.phase += 0.2
        for i, (plot, buf) in enumerate(zip(self.plots, self.buffers)):
            y = math.sin(self.phase * (0.8 + i * 0.05) + self.phase_offsets[i])
            buf.append(y)
            plot.points = [(x, buf[x]) for x in range(len(buf))]
        # Debug-Ausgabe, um sicherzugehen, dass Clock läuft:
        print(f"Frame {int(self.phase)} OK")


if __name__ == "__main__":
    Vivosun6GraphApp().run()
