#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enlarged_chart_window.py – Fullscreen-Chart Fenster 🌿 v3.8 Swipe+ColorFix
Basierend auf v3.7 Final, erweitert um Swipe-Events.
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy_garden.graph import Graph, LinePlot
from kivy.utils import platform
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.graphics import Color, Rectangle
from kivy.core.text import LabelBase
from kivy.uix.modalview import ModalView

# -------------------------------------------------------
# 🌿 Scaling & Font
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.72
else:
    UI_SCALE = 1.0

def sp_scaled(v): return f"{int(v * UI_SCALE)}sp"
def dp_scaled(v): return dp(v * UI_SCALE)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    try:
        LabelBase.register(name="FA", fn_regular=FA_PATH)
    except Exception:
        pass

# -------------------------------------------------------
# Maps
# -------------------------------------------------------
TITLE_MAP = {
    "tile_t_in":  ("Internal Temperature", "°C"),
    "tile_h_in":  ("Internal Humidity", "%"),
    "tile_vpd_in":("Internal VPD", "kPa"),
    "tile_t_out": ("External Temperature", "°C"),
    "tile_h_out": ("External Humidity", "%"),
    "tile_vpd_out":("External VPD", "kPa"),
}

ALL_KEYS  = ["tile_t_in", "tile_h_in", "tile_vpd_in",
             "tile_t_out","tile_h_out","tile_vpd_out"]
INT_KEYS  = ["tile_t_in", "tile_h_in", "tile_vpd_in"]

INVALID_SENTINEL = -90.0  # filter -99

# -------------------------------------------------------
# Farben fix (Temp/Hum/VPD)
# -------------------------------------------------------
COLOR_MAP = {
    "tile_t_in":  (1.00, 0.45, 0.45),  # rot
    "tile_t_out": (1.00, 0.45, 0.45),
    "tile_h_in":  (0.35, 0.70, 1.00),  # blau
    "tile_h_out": (0.35, 0.70, 1.00),
    "tile_vpd_in":(0.80, 1.00, 0.45),  # grün-gelb
    "tile_vpd_out":(0.80, 1.00, 0.45),
}

# -------------------------------------------------------
# EnlargedChartWindow
# -------------------------------------------------------
class EnlargedChartWindow(BoxLayout):
    tile_key   = StringProperty("")
    chart_mgr  = ObjectProperty(None)
    _allowed   = ListProperty([])
    _index     = 0

    def __init__(self, chart_mgr, start_key="tile_t_in", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.chart_mgr = chart_mgr
        ext_present = bool(getattr(chart_mgr, "ext_present", True))
        self._allowed = ALL_KEYS if ext_present else INT_KEYS
        self._index = self._safe_index(start_key)
        self.tile_key = self._allowed[self._index]
        self._touch_start_x = None

        self._build_ui()
        self._refresh_titles_and_colors()
        self._update_chart()
        self._ev = Clock.schedule_interval(self._update_chart, 1.0)
        print(f"🌿 Enlarged gestartet key={self.tile_key}")

    # ---------------------------------------------------
    # UI
    # ---------------------------------------------------
    def _build_ui(self):
        with self.canvas.before:
            Color(0.02, 0.05, 0.03, 1)
            self._bg = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=lambda *_: setattr(self._bg, "size", self.size))
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos))

        # Header
        self._header = BoxLayout(orientation="vertical",
                                 size_hint_y=None,
                                 height=dp_scaled(96),
                                 padding=[dp_scaled(12), dp_scaled(8), dp_scaled(12), 0],
                                 spacing=dp_scaled(4))
        self._title_lbl = Label(markup=True, text="[b]—[/b]",
                                font_size=sp_scaled(18),
                                color=(0.80, 1.00, 0.85, 1),
                                halign="center", valign="middle",
                                size_hint_y=None, height=dp_scaled(38))
        self._value_lbl = Label(text="--", font_size=sp_scaled(28),
                                color=(0.95, 1.00, 0.95, 1),
                                bold=True, halign="center", valign="middle",
                                size_hint_y=None, height=dp_scaled(46))
        self._header.add_widget(self._title_lbl)
        self._header.add_widget(self._value_lbl)
        self.add_widget(self._header)

        # Graph
        self.graph = Graph(xlabel="Time", ylabel="", x_ticks_major=10, y_ticks_major=0.5,
                           background_color=(0.05, 0.07, 0.06, 1),
                           tick_color=(0.30, 0.80, 0.40, 1),
                           draw_border=False, xmin=0, xmax=60, ymin=0, ymax=1, size_hint_y=1.0)
        self.plot = LinePlot(line_width=4.0)
        self.graph.add_plot(self.plot)
        self.add_widget(self.graph)

        # Controls
        self._controls = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(58),
                                   spacing=dp_scaled(8), padding=[dp_scaled(8)]*4)

        def _btn(text, bg, cb, w=None, fs=16):
            b = Button(markup=True, text=text, font_size=sp_scaled(fs),
                       background_normal="", background_color=bg, on_release=lambda *_: cb())
            if w:
                b.size_hint_x = None
                b.width = dp_scaled(w)
            return b

        self._btn_prev = _btn("[font=FA]\uf060[/font]", (0.25, 0.45, 0.28, 1), lambda: self._switch(-1), w=58)
        self._btn_next = _btn("[font=FA]\uf061[/font]", (0.25, 0.45, 0.28, 1), lambda: self._switch(+1), w=58)
        self._btn_reset = _btn("[font=FA]\uf021[/font]  Reset", (0.25, 0.55, 0.25, 1), self._do_reset, fs=16)
        self._btn_home  = _btn("[font=FA]\uf015[/font]  Dashboard", (0.35, 0.28, 0.28, 1), self._close_view, fs=16)

        self._controls.add_widget(self._btn_prev)
        self._controls.add_widget(self._btn_next)
        self._controls.add_widget(self._btn_reset)
        self._controls.add_widget(self._btn_home)
        self.add_widget(self._controls)

    # ---------------------------------------------------
    # Touch → Swipe
    # ---------------------------------------------------
    def on_touch_down(self, touch):
        self._touch_start_x = touch.x
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._touch_start_x is not None:
            dx = touch.x - self._touch_start_x
            if abs(dx) > dp_scaled(60):
                self._switch(-1 if dx > 0 else +1)
        self._touch_start_x = None
        return super().on_touch_up(touch)

    # ---------------------------------------------------
    # Helpers
    # ---------------------------------------------------
    def _safe_index(self, key):
        return self._allowed.index(key) if key in self._allowed else 0

    def _unit(self, key):
        """Einheit dynamisch aus config.json lesen (°C ↔ °F, %, kPa)."""
        try:
            import config
            cfg = config.load_config()
            mode = cfg.get("unit", "°C")
        except Exception:
            mode = "°C"
        if key.startswith("tile_t_"):
            return "°F" if mode == "°F" else "°C"
        if key.startswith("tile_h_"):
            return "%"
        if key.startswith("tile_vpd_"):
            return "kPa"
        return ""

    def _title(self, key):
        return TITLE_MAP.get(key, (key, ""))[0]

    # ---------------------------------------------------
    # Titel, Farben und Linien-Stil aktualisieren (Dashboard-Schema)
    # ---------------------------------------------------
    def _refresh_titles_and_colors(self):
        """Setzt Titel, Einheit, Plotfarbe und Linienbreite nach Dashboard-Farbschema."""
        title, _ = TITLE_MAP.get(self.tile_key, (self.tile_key, ""))
        unit = self._unit(self.tile_key)
        self._title_lbl.text = f"[b]{title}[/b]"
        self.graph.ylabel = f"{title} ({unit})" if unit else title

        # --- Farbschema exakt wie Dashboard ---
        color_map = {
            "tile_t_in":  (1.00, 0.45, 0.45),  # 🔴 Rot
            "tile_h_in":  (0.35, 0.70, 1.00),  # 🔵 Blau
            "tile_vpd_in":(0.85, 1.00, 0.45),  # 💛 Gelb
            "tile_t_out": (1.00, 0.70, 0.35),  # 🟠 Orange
            "tile_h_out": (0.45, 0.95, 1.00),  # 🟦 Cyan
            "tile_vpd_out":(0.60, 1.00, 0.60), # 💚 Grün
        }
        rgb = color_map.get(self.tile_key, (0.4, 1.0, 0.6))

        # --- alten Plot sicher entfernen & neu anlegen (Graph-Color-Reset) ---
        try:
            if self.plot in self.graph.plots:
                self.graph.remove_plot(self.plot)
        except Exception:
            pass

        from kivy_garden.graph import LinePlot
        self.plot = LinePlot(color=(rgb[0], rgb[1], rgb[2], 1))
        self.plot.line_width = 4.0
        self.graph.add_plot(self.plot)

        # --- Achsen & Hintergrund angleichen ---
        self.graph.tick_color = (rgb[0]*0.7, rgb[1]*0.9, rgb[2]*0.7, 1)
        self.graph.background_color = (0.05, 0.07, 0.06, 1)
        self.graph.draw_border = False

        # --- Titel- und Wert-Farben leicht getönt für Harmonie ---
        self._title_lbl.color = (rgb[0]*0.9, rgb[1], rgb[2]*0.9, 1)
        self._value_lbl.color = (rgb[0]*0.9 + 0.1, rgb[1]*0.95 + 0.05, rgb[2]*0.9 + 0.1, 1)

    # ---------------------------------------------------
    # Daten anzeigen
    # ---------------------------------------------------
    def _update_chart(self, *_):
        try:
            buf = self.chart_mgr.buffers.get(self.tile_key, [])
            clean = [(x, y) for x, y in buf if isinstance(y, (int, float)) and y > INVALID_SENTINEL]
            if not clean:
                self.plot.points = []
                self._value_lbl.text = "--"
                return
            self.plot.points = clean
            xs, ys = zip(*clean)
            ymin, ymax = min(ys), max(ys)
            if abs(ymax - ymin) < 1e-6:
                ymax = ymin + 0.5
                ymin = ymin - 0.5
            margin = max((ymax - ymin) * 0.2, 0.2)
            self.graph.ymin = round(ymin - margin, 2)
            self.graph.ymax = round(ymax + margin, 2)
            cw = int(getattr(self.chart_mgr, "chart_window", 120) or 120)
            last_x = clean[-1][0]
            self.graph.xmax = max(last_x, cw)
            self.graph.xmin = max(0, self.graph.xmax - cw)
            unit = self._unit(self.tile_key)
            self._value_lbl.text = f"{clean[-1][1]:.2f} {unit}" if unit else f"{clean[-1][1]:.2f}"
        except Exception as e:
            print(f"⚠️ Enlarged Chart-Update Fehler ({self.tile_key}): {e}")

    # ---------------------------------------------------
    # Switch left/right
    # ---------------------------------------------------
    def _switch(self, direction):
        if not self._allowed:
            return
        ext_present = bool(getattr(self.chart_mgr, "ext_present", True))
        self._allowed = ALL_KEYS if ext_present else INT_KEYS
        if self.tile_key in self._allowed:
            self._index = self._allowed.index(self.tile_key)
        else:
            self._index = 0
        self._index = (self._index + direction) % len(self._allowed)
        self.tile_key = self._allowed[self._index]
        self._refresh_titles_and_colors()
        self._update_chart()
        print(f"➡️ Swipe switch → {self.tile_key}")

    # ---------------------------------------------------
    # Reset + Close
    # ---------------------------------------------------
    def _do_reset(self):
        try:
            if hasattr(self.chart_mgr, "reset_data"):
                self.chart_mgr.reset_data()
        except Exception as e:
            print("⚠️ Reset an ChartManager fehlgeschlagen:", e)
        self.plot.points = []
        self._value_lbl.text = "--"

    def _close_view(self, *_):
        parent = self.parent
        while parent and not isinstance(parent, ModalView):
            parent = parent.parent
        if parent:
            try:
                Clock.unschedule(self._update_chart)
            except Exception:
                pass
            parent.dismiss()
            print("🔙 Enlarged geschlossen")
