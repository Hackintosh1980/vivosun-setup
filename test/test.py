#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_enlarged_dummy.py – Minimaltest für Graph + Hintergrundbild
Zeigt Dummy-Plot auf transparentem Graph mit Hintergrundbild.
"""

import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy_garden.graph import Graph, LinePlot
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(BASE_DIR), "assets")

class DummyGraph(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self._build_ui()

    def _build_ui(self):
        # Hintergrund
        from kivy.uix.floatlayout import FloatLayout
        wrapper = FloatLayout()

        bg_path = os.path.join(ASSETS_DIR, "tiles_bg.png")
        if os.path.exists(bg_path):
            bg = Image(source=bg_path, fit_mode="fill", size_hint=(1, 1))
            wrapper.add_widget(bg)
            print(f"🖼️ Hintergrund aktiv: {bg_path}")
        else:
            print("⚠️ tiles_bg.png nicht gefunden!")

        # Graph mit transparentem Hintergrund
        try:
            self.graph = Graph(
                xlabel="Time (s)", ylabel="Value",
                xmin=0, xmax=60, ymin=0, ymax=1,
                draw_border=False,
                background_color=(0, 0, 0, 0),
                tick_color=(0.6, 0.9, 0.7, 1),
                size_hint=(1, 1)
            )

            self.plot = LinePlot(color=(0.3, 1.0, 0.3, 1), line_width=3)
            self.graph.add_plot(self.plot)

            wrapper.add_widget(self.graph)

            # Canvas-Highlight
            with wrapper.canvas.before:
                Color(0.2, 1.0, 0.6, 0.1)
                self._glow = Rectangle(size=wrapper.size, pos=wrapper.pos)
            wrapper.bind(size=lambda *_: setattr(self._glow, "size", wrapper.size))
            wrapper.bind(pos=lambda *_: setattr(self._glow, "pos", wrapper.pos))

            # Dummy-Plot-Update
            Clock.schedule_interval(self._update_dummy, 0.5)
            print("✅ Graph erfolgreich initialisiert.")

        except Exception as e:
            print("💥 Graph init failed:", e)

        self.add_widget(wrapper)

    def _update_dummy(self, dt):
        """Erzeugt eine Wellenlinie mit laufendem Zeitindex."""
        import math
        t = getattr(self, "_tick", 0)
        self._tick = t + 1
        self.plot.points = [(x, 0.5 + 0.3 * math.sin((x + t) / 5.0)) for x in range(60)]
        print(f"⏱️ Frame {t} gezeichnet ({len(self.plot.points)} Punkte)")

class TestApp(App):
    def build(self):
        return DummyGraph()

if __name__ == "__main__":
    TestApp().run()
