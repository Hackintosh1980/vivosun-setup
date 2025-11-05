#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enlarged_chart_window.py – Fullscreen-Chart Fenster 🌿 v3.7 Final
Einheitliches Neon-Design passend zu Dashboard & Scatter.

• Zeigt einzelne Sensor-Kurven (Temp, Hum, VPD)
• Dynamisch via tile_key (tile_t_in, tile_h_in, …)
• Pfeile zum Umschalten zwischen Charts (respektiert ext_present)
• Controlbar unten (Home/Back, Reset, ◀ ▶)
• Zweite Zeile: großer Live-Wert + Einheit
• Farben/Line-Width exakt wie Dashboard (Tile.accent, 4.0)
• -99/-99 Werte werden gefiltert (keine Anzeige/keine Skalen-Sprünge)

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

# -------------------------------------------------------
# 🌿 Globales UI-Scaling
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.72
else:
    UI_SCALE = 1.0

def sp_scaled(v): return f"{int(v * UI_SCALE)}sp"
def dp_scaled(v): return dp(v * UI_SCALE)

# -------------------------------------------------------
# Fonts (FA)
# -------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    try:
        LabelBase.register(name="FA", fn_regular=FA_PATH)
    except Exception:
        pass
# -------------------------------------------------------

# Mapping: Titel + Einheit
TITLE_MAP = {
    "tile_t_in":  ("Internal Temperature", "°C"),
    "tile_h_in":  ("Internal Humidity",    "%"),
    "tile_vpd_in":("Internal VPD",         "kPa"),
    "tile_t_out": ("External Temperature", "°C"),
    "tile_h_out": ("External Humidity",    "%"),
    "tile_vpd_out":("External VPD",        "kPa"),
}

# Reihenfolge der Keys
ALL_KEYS  = ["tile_t_in", "tile_h_in", "tile_vpd_in",
             "tile_t_out","tile_h_out","tile_vpd_out"]
INT_KEYS  = ["tile_t_in", "tile_h_in", "tile_vpd_in"]
EXT_KEYS  = ["tile_t_out","tile_h_out","tile_vpd_out"]

# Filter-Schwelle für ungültige Messwerte
INVALID_SENTINEL = -90.0  # alles <= -90 raus (deckt -99/-99 zuverlässig ab)


class EnlargedChartWindow(BoxLayout):
    """Fullscreen-Chart im Neon-Stil mit Bottom-Controlbar."""
    tile_key   = StringProperty("")
    chart_mgr  = ObjectProperty(None)
    _allowed   = ListProperty([])
    _index     = 0

    def __init__(self, chart_mgr, start_key="tile_t_in", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.chart_mgr = chart_mgr

        # Welche Tiles sind erlaubt? (respektiert ext_present)
        ext_present = bool(getattr(self.chart_mgr, "ext_present", True))
        self._allowed = (ALL_KEYS if ext_present else INT_KEYS)

        # Start-Key einklinken
        self._index = self._safe_index(start_key)
        self.tile_key = self._allowed[self._index]

        # UI bauen
        self._build_ui()

        # Ersten Inhalt ziehen
        self._refresh_titles_and_colors()
        self._update_chart()

        # Regelmäßiges Update (wie Dashboard, aber schlank)
        self._ev = Clock.schedule_interval(self._update_chart, 1.0)

        print(f"🌿 Enlarged gestartet – key={self.tile_key} allowed={self._allowed}")

    # ---------------------------------------------------
    # UI
    # ---------------------------------------------------
    def _build_ui(self):
        # Hintergrund
        with self.canvas.before:
            Color(0.02, 0.05, 0.03, 1)
            self._bg = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=lambda *_: setattr(self._bg, "size", self.size))
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos))

        # Header (oben): Titel + große Wertzeile
        self._header = BoxLayout(orientation="vertical",
                                 size_hint_y=None,
                                 height=dp_scaled(96),
                                 padding=[dp_scaled(12), dp_scaled(8), dp_scaled(12), 0],
                                 spacing=dp_scaled(4))
        # Titelzeile
        self._title_lbl = Label(
            markup=True,
            text="[b]—[/b]",
            font_size=sp_scaled(18),
            color=(0.80, 1.00, 0.85, 1),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp_scaled(38),
        )
        # Große Wertzeile (zweite Zeile)
        self._value_lbl = Label(
            text="--",
            font_size=sp_scaled(28),
            color=(0.95, 1.00, 0.95, 1),
            bold=True,
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp_scaled(46),
        )
        self._header.add_widget(self._title_lbl)
        self._header.add_widget(self._value_lbl)
        self.add_widget(self._header)

        # Graph (Mitte)
        self.graph = Graph(
            xlabel="Time",
            ylabel="",  # wird dynamisch gesetzt
            x_ticks_major=10,
            y_ticks_major=0.5,
            background_color=(0.05, 0.07, 0.06, 1),
            tick_color=(0.30, 0.80, 0.40, 1),
            draw_border=False,
            xmin=0, xmax=60, ymin=0, ymax=1,
            size_hint_y=1.0
        )
        # Plot; Farbe/LineWidth setzen wir nach dem Ermitteln der Accent-Farbe
        self.plot = LinePlot(color=(0.3, 1.0, 0.5, 1))
        self.plot.line_width = 4.0  # wird ggf. gelassen (Dashboard-Style)
        self.graph.add_plot(self.plot)
        self.add_widget(self.graph)

        # Controlbar (unten)
        self._controls = BoxLayout(orientation="horizontal",
                                   size_hint_y=None,
                                   height=dp_scaled(58),
                                   spacing=dp_scaled(8),
                                   padding=[dp_scaled(8)]*4)

        def _btn(text, bg, cb, w=None, fs=16):
            b = Button(
                markup=True,
                text=text,
                font_size=sp_scaled(fs),
                background_normal="",
                background_color=bg,
                on_release=lambda *_: cb()
            )
            if w:
                b.size_hint_x = None
                b.width = dp_scaled(w)
            return b

        # ◀, ▶
        self._btn_prev = _btn("[font=FA]\uf060[/font]", (0.25, 0.45, 0.28, 1), lambda: self._switch(-1), w=58)
        self._btn_next = _btn("[font=FA]\uf061[/font]", (0.25, 0.45, 0.28, 1), lambda: self._switch(+1), w=58)
        # Reset (Chart + ChartManager)
        self._btn_reset = _btn("[font=FA]\uf021[/font]  Reset", (0.25, 0.55, 0.25, 1), self._do_reset, fs=16)
        # Back/Home
        self._btn_home  = _btn("[font=FA]\uf015[/font]  Dashboard", (0.35, 0.28, 0.28, 1), self._close_view, fs=16)

        # Reihenfolge: ◀ ▶ | Reset | Home
        self._controls.add_widget(self._btn_prev)
        self._controls.add_widget(self._btn_next)
        self._controls.add_widget(self._btn_reset)
        self._controls.add_widget(self._btn_home)

        self.add_widget(self._controls)

    # ---------------------------------------------------
    # Helpers
    # ---------------------------------------------------
    def _safe_index(self, key):
        """Liefert einen gültigen Index in _allowed; default 0."""
        if key in self._allowed:
            return self._allowed.index(key)
        return 0

    def _allowed_keys_now(self):
        """Erneut prüfen, ob externe Tiles verfügbar sein sollen."""
        ext_present = bool(getattr(self.chart_mgr, "ext_present", True))
        return (ALL_KEYS if ext_present else INT_KEYS)

    def _unit(self, key):
        return TITLE_MAP.get(key, ("", ""))[1]

    def _title(self, key):
        return TITLE_MAP.get(key, (key, ""))[0]

    def _accent_from_dashboard(self, default=(0.3, 1.0, 0.5)):
        """Versucht, die Tile-Farbe aus dem Dashboard zu holen."""
        try:
            from kivy.app import App
            app = App.get_running_app()
            dash = app.sm.get_screen("dashboard").children[0]
            tile = dash.ids.get(self.tile_key)
            if tile and hasattr(tile, "accent"):
                col = list(tile.accent)
                if len(col) >= 3:
                    return (col[0], col[1], col[2])
        except Exception:
            pass
        return default

    # ---------------------------------------------------
    # Titel, Farben und Linien-Stil aktualisieren
    # ---------------------------------------------------
    def _refresh_titles_and_colors(self):
        """Setzt Titel, Einheit, Plotfarbe und Linienbreite."""
        title, unit = TITLE_MAP.get(self.tile_key, (self.tile_key, ""))
        self._title_lbl.text = f"[b]{title}[/b]"
        self.graph.ylabel = f"{title} ({unit})" if unit else title

        # --- Farbe aus Dashboard holen ---
        try:
            from kivy.app import App
            app = App.get_running_app()
            dash = app.sm.get_screen("dashboard").children[0]
            tile = dash.ids.get(self.tile_key)
            if tile and hasattr(tile, "accent"):
                rgb = list(tile.accent)
            else:
                rgb = [0.3, 1.0, 0.5]   # fallback: hellgrün
        except Exception:
            rgb = [0.3, 1.0, 0.5]

        # --- Plot-Style ---
        self.plot.color = (rgb[0], rgb[1], rgb[2], 1)
        self.plot.line_width = 4.0          # identisch zum Dashboard-Look
        self.graph.tick_color = (rgb[0]*0.6, rgb[1]*0.8, rgb[2]*0.6, 1)


    # ---------------------------------------------------
    # Daten holen & anzeigen
    # ---------------------------------------------------
    def _update_chart(self, *_):
        try:
            # Bei Laufzeitänderung (ext_present) erlaubte Keys neu ziehen
            new_allowed = self._allowed_keys_now()
            if new_allowed != self._allowed:
                self._allowed = new_allowed
                # aktuellen Key einpassen
                if self.tile_key not in self._allowed:
                    # zurück auf erstes internes Tile
                    self._index = 0
                    self.tile_key = self._allowed[self._index]
                    self._refresh_titles_and_colors()

            # Buffer ziehen
            buf = self.chart_mgr.buffers.get(self.tile_key, [])
            if not buf:
                self.plot.points = []
                self._value_lbl.text = "--"
                return

            # -99/-99 filtern: alles <= -90 raus
            clean = [(x, y) for (x, y) in buf if isinstance(y, (int, float)) and y > INVALID_SENTINEL]
            if not clean:
                self.plot.points = []
                self._value_lbl.text = "--"
                return

            # Darstellung
            self.plot.points = clean
            xs, ys = zip(*clean)
            ymin, ymax = min(ys), max(ys)
            if abs(ymax - ymin) < 1e-6:
                ymax = ymin + 0.5
                ymin = ymin - 0.5

            margin = max((ymax - ymin) * 0.2, 0.2)
            self.graph.ymin = round(ymin - margin, 2)
            self.graph.ymax = round(ymax + margin, 2)

            # X-Achse: Fenstergröße aus ChartManager (falls vorhanden)
            cw = int(getattr(self.chart_mgr, "chart_window", 120) or 120)
            last_x = clean[-1][0]
            self.graph.xmax = max(last_x, cw)
            self.graph.xmin = max(0, self.graph.xmax - cw)

            # Großer Wert + Einheit
            unit = self._unit(self.tile_key)
            self._value_lbl.text = f"{clean[-1][1]:.2f} {unit}" if unit else f"{clean[-1][1]:.2f}"

        except Exception as e:
            print(f"⚠️ Enlarged Chart-Update Fehler ({self.tile_key}): {e}")

    # ---------------------------------------------------
    # Umschalten ◀ ▶ (respektiert _allowed)
    # ---------------------------------------------------
    def _switch(self, direction):
        if not self._allowed:
            return
        # Aktuelle Liste prüfen (ext_present kann sich geändert haben)
        self._allowed = self._allowed_keys_now()
        # Index der aktuellen tile_key
        if self.tile_key in self._allowed:
            self._index = self._allowed.index(self.tile_key)
        else:
            self._index = 0
        # Drehen
        self._index = (self._index + direction) % len(self._allowed)
        self.tile_key = self._allowed[self._index]
        self._refresh_titles_and_colors()
        self._update_chart()
        print(f"➡️ Enlarged: switch to {self.tile_key}")

    # ---------------------------------------------------
    # Reset (löscht Kurven & triggert ChartManager.reset_data)
    # ---------------------------------------------------
    def _do_reset(self):
        try:
            if hasattr(self.chart_mgr, "reset_data"):
                self.chart_mgr.reset_data()
        except Exception as e:
            print("⚠️ Reset-Delegation an ChartManager fehlgeschlagen:", e)
        # Lokale Anzeige leeren
        self.plot.points = []
        self._value_lbl.text = "--"

    # ---------------------------------------------------
    # Schließen (zurück zum Dashboard)
    # ---------------------------------------------------
    def _close_view(self, *_):
        from kivy.uix.modalview import ModalView
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
