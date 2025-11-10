#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_dashboard_toggle_grid.py – Dummy Dashboard 🌿 v4
2 Reihen × 3 Spalten, umschaltbar 3↔6 Tiles
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, math
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy_garden.graph import Graph, LinePlot
from kivy.graphics import Color, Rectangle
from kivy.uix.label import Label
from kivy.uix.button import Button

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(BASE_DIR), "assets")
BG_PATH = os.path.join(ASSETS_DIR, "tiles_bg.png")

# ------------------------------------------------------------
# Einzelnes Tile mit grünem Rasterhintergrund
# ------------------------------------------------------------
class Tile(FloatLayout):
    def __init__(self, title, color, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.color = color
        self._tick = 0
        self._build_ui()
        Clock.schedule_interval(self._update_plot, 0.3)

    def _build_ui(self):
        # Hintergrundbild (fill mode)
        if os.path.exists(BG_PATH):
            bg = Image(
                source=BG_PATH,
                fit_mode="fill",
                size_hint=(1, 1),
                pos_hint={"x": 0, "y": 0},
                allow_stretch=True,
                keep_ratio=False,
            )
            self.add_widget(bg)
        else:
            with self.canvas.before:
                Color(0.0, 0.2, 0.05, 1)
                Rectangle(size=self.size, pos=self.pos)

        # halbtransparente Headerleiste
        with self.canvas.before:
            Color(0, 0, 0, 0.25)
            self._hdr = Rectangle(size=(self.width, 26), pos=(self.x, self.top - 26))
        self.bind(size=self._update_hdr, pos=self._update_hdr)

        lbl = Label(
            text=self.title,
            font_size="14sp",
            color=(0.9, 1.0, 0.9, 1.0),
            size_hint=(1, None),
            height=26,
            pos_hint={"x": 0, "top": 1},
        )
        self.add_widget(lbl)

        # Graph transparent
        self.graph = Graph(
            xmin=0,
            xmax=60,
            ymin=0,
            ymax=1,
            draw_border=False,
            background_color=(0, 0, 0, 0),
            tick_color=(0, 0, 0, 0),
            x_ticks_major=20,
            y_ticks_major=0.5,
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )

        # dicke Linien
        self.plot = LinePlot(color=self.color, line_width=5.5)
        self.graph.add_plot(self.plot)
        self.add_widget(self.graph)

    def _update_hdr(self, *args):
        self._hdr.size = (self.width, 26)
        self._hdr.pos = (self.x, self.top - 26)

    def _update_plot(self, dt):
        """Sinuslinien-Dummy"""
        self._tick += 1
        phase = (self._tick / 5.0)
        pts = [(x, 0.5 + 0.4 * math.sin((x / 6.0) + phase)) for x in range(60)]
        self.plot.points = pts


# ------------------------------------------------------------
# Dashboard mit 2×3 Grid und Toggle
# ------------------------------------------------------------
class DummyDashboard(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.tile_count = 6
        self._build_header()
        self._build_grid()

    def _build_header(self):
        bar = BoxLayout(size_hint_y=None, height=42, padding=[10, 5], spacing=10)
        lbl = Label(
            text="[b]Dummy Dashboard[/b]",
            markup=True,
            font_size="18sp",
            color=(0.8, 1.0, 0.8, 1.0),
        )
        self._toggle_btn = Button(
            text="Switch to 3 Tiles",
            font_size="14sp",
            background_normal="",
            background_color=(0.25, 0.5, 0.25, 1),
        )
        self._toggle_btn.bind(on_release=self._toggle_tiles)
        bar.add_widget(lbl)
        bar.add_widget(self._toggle_btn)
        self.add_widget(bar)

    def _build_grid(self):
        if hasattr(self, "_grid"):
            self.remove_widget(self._grid)

        # immer 3 Spalten – 1 oder 2 Reihen
        rows = 2 if self.tile_count == 6 else 1
        self._grid = GridLayout(cols=3, rows=rows, padding=10, spacing=10)
        self._populate_tiles()
        self.add_widget(self._grid)

    def _populate_tiles(self):
        tiles_full = [
            ("Internal Temp", (1.0, 0.5, 0.5, 1)),
            ("Internal Hum", (0.4, 0.8, 1.0, 1)),
            ("Internal VPD", (0.8, 1.0, 0.4, 1)),
            ("External Temp", (1.0, 0.8, 0.5, 1)),
            ("External Hum", (0.5, 1.0, 0.9, 1)),
            ("External VPD", (0.6, 1.0, 0.6, 1)),
        ]
        if self.tile_count == 3:
            tiles = tiles_full[:3]
        else:
            tiles = tiles_full
        for title, color in tiles:
            self._grid.add_widget(Tile(title, color))

    def _toggle_tiles(self, *_):
        if self.tile_count == 6:
            self.tile_count = 3
            self._toggle_btn.text = "Switch to 6 Tiles"
        else:
            self.tile_count = 6
            self._toggle_btn.text = "Switch to 3 Tiles"
        self._build_grid()


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
class DummyApp(App):
    def build(self):
        return DummyDashboard(size_hint=(1, 1))


if __name__ == "__main__":
    DummyApp().run()
