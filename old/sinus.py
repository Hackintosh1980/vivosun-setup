#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neon Graph Test – animated sine
"""

import os, sys, math
from kivy.app import App
from kivy.clock import Clock

# --- Garden Pfad fix ---
base = os.path.dirname(__file__)
garden_path = os.path.join(base, "garden")
if garden_path not in sys.path:
    sys.path.append(garden_path)

from kivy_garden.graph import Graph, MeshLinePlot


class LiveSineApp(App):
    def build(self):
        self.graph = Graph(
            xmin=0, xmax=100, ymin=-1.2, ymax=1.2,
            x_ticks_major=10, y_ticks_major=4,
            background_color=(0, 0, 0, 1),
            border_color=(0.2, 1, 0.5, 0.4),
            tick_color=(0.3, 1, 0.3, 0.5),
            draw_border=True, x_grid=False, y_grid=False
        )
        self.plot = MeshLinePlot(color=(0.4, 1, 0.6, 1))
        self.graph.add_plot(self.plot)
        self.phase = 0
        self.samples = 200
        self.update_plot(0)
        Clock.schedule_interval(self.update_plot, 1 / 30.0)
        return self.graph

    def update_plot(self, dt):
        self.phase += 0.3
        self.plot.points = [(x, math.sin((x / 10.0) + self.phase)) for x in range(self.samples)]
        self.graph._redraw()


if __name__ == "__main__":
    LiveSineApp().run()
