#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neon Graph Test – 6 simultaneous sine waves (smooth animated)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, sys, math, random
from kivy.app import App
from kivy.clock import Clock

# --- Garden Path Fix ---
base = os.path.dirname(__file__)
garden_path = os.path.join(base, "garden")
if garden_path not in sys.path:
    sys.path.append(garden_path)

from kivy_garden.graph import Graph, MeshLinePlot


class MultiSineApp(App):
    def build(self):
        # Haupt-Graph
        self.graph = Graph(
            xmin=0, xmax=100, ymin=-1.5, ymax=1.5,
            x_ticks_major=20, y_ticks_major=4,
            background_color=(0, 0, 0, 1),
            border_color=(0.1, 1, 0.6, 0.35),
            tick_color=(0.35, 1, 0.45, 0.5),
            draw_border=True,
            x_grid=False, y_grid=False
        )

        # Farben für 6 Linien
        colors = [
            (1.0, 0.3, 0.3, 1),
            (0.3, 0.7, 1.0, 1),
            (0.9, 1.0, 0.4, 1),
            (1.0, 0.7, 0.3, 1),
            (0.5, 1.0, 0.8, 1),
            (0.8, 0.5, 1.0, 1),
        ]

        # MeshLinePlots erstellen
        self.plots = []
        for c in colors:
            p = MeshLinePlot(color=c)
            self.graph.add_plot(p)
            self.plots.append(p)

        self.phase = 0
        self.samples = 200
        self.update_plot(0)
        Clock.schedule_interval(self.update_plot, 1 / 30.0)
        return self.graph

    def update_plot(self, dt):
        self.phase += 0.15
        for i, plot in enumerate(self.plots):
            # Frequenz + Phase variieren für schöne Überlagerung
            freq = 0.15 + (i * 0.05)
            amp = 0.7 + (i * 0.1)
            plot.points = [
                (x, math.sin((x / 10.0) * freq + self.phase + i) * amp * 0.8)
                for x in range(self.samples)
            ]
        # Refresh Graph (manuell, weil Garden-Version minimal ist)
        self.graph._redraw()


if __name__ == "__main__":
    MultiSineApp().run()
