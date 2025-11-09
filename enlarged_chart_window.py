#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enlarged_chart_window.py – Fullscreen-Chart 🌿 v4.3 Stable
• Voll sync mit Dashboard Start/Stop
• Force-Anzeige beim Öffnen (auch wenn kein Live)
• BT-LED reaktiv auf Polling-State
• MAC/RSSI Anzeige stabil
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, traceback
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy_garden.graph import Graph, LinePlot
from kivy.utils import platform
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.core.text import LabelBase
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle, Ellipse
from kivy_garden.graph import MeshLinePlot
from kivy.animation import Animation
# ----------------------------------------------------
# Font scaling + FontAwesome
# ----------------------------------------------------
UI_SCALE = 0.72 if platform == "android" else 1.0
def sp_scaled(v): return f"{int(v * UI_SCALE)}sp"
def dp_scaled(v): return dp(v * UI_SCALE)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    try:
        LabelBase.register(name="FA", fn_regular=FA_PATH)
    except Exception:
        pass

# ----------------------------------------------------
# Static maps
# ----------------------------------------------------
TITLE_MAP = {
    "tile_t_in":  ("Internal Temperature", "°C"),
    "tile_h_in":  ("Internal Humidity", "%"),
    "tile_vpd_in":("Internal VPD", "kPa"),
    "tile_t_out": ("External Temperature", "°C"),
    "tile_h_out": ("External Humidity", "%"),
    "tile_vpd_out":("External VPD", "kPa"),
}
ALL_KEYS = list(TITLE_MAP.keys())
INT_KEYS = [k for k in ALL_KEYS if "_out" not in k]
COLOR_MAP = {
    "tile_t_in": (1.00, 0.45, 0.45),
    "tile_t_out":(1.00, 0.70, 0.35),
    "tile_h_in": (0.35, 0.70, 1.00),
    "tile_h_out":(0.45, 0.95, 1.00),
    "tile_vpd_in":(0.85, 1.00, 0.45),
    "tile_vpd_out":(0.60, 1.00, 0.60),
}
INVALID_SENTINEL = -90.0

# ----------------------------------------------------
# EnlargedChartWindow
# ----------------------------------------------------
class EnlargedChartWindow(BoxLayout):
    tile_key = StringProperty("")
    chart_mgr = ObjectProperty(None)
    _allowed = ListProperty([])
    _index = 0

    def __init__(self, chart_mgr, start_key="tile_t_in", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.chart_mgr = chart_mgr
        self._allowed = ALL_KEYS if getattr(chart_mgr, "ext_present", True) else INT_KEYS
        self._index = self._safe_index(start_key)
        self.tile_key = self._allowed[self._index]
        self._touch_start_x = None
        self._graph_ok = True
        self._stale_warned = False
        self._force_until_data = True

        self._build_ui()
        self._refresh_titles_and_colors()

        # Erstes Update forcen, danach bis erste Daten da sind
        Clock.schedule_once(lambda *_: self._update_chart(force=True), 0.3)
        self._ev = Clock.schedule_interval(
            lambda dt: self._update_chart(force=self._force_until_data), 1.0
        )

    # ----------------------------------------------------
    def _safe_index(self, key):
        try:
            return self._allowed.index(key)
        except Exception:
            return 0

    def _unit_for_key(self, key):
        try:
            import config
            cfg = config.load_config()
            unit = cfg.get("unit", "°C")
        except Exception:
            unit = "°C"
        if key.startswith("tile_t_"): return unit
        if key.startswith("tile_h_"): return "%"
        if key.startswith("tile_vpd_"): return "kPa"
        return ""

    def _title(self, key):
        return TITLE_MAP.get(key, (key, ""))[0]

    def _allowed_keys_now(self):
        return ALL_KEYS if getattr(self.chart_mgr, "ext_present", True) else INT_KEYS

    # ----------------------------------------------------
    # UI
    # ----------------------------------------------------
    def _build_ui(self):
        with self.canvas.before:
            Color(0.02, 0.05, 0.03, 1)
            self._bg = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=lambda *_: setattr(self._bg, "size", self.size))
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos))

       # ---------------------------------------------------
        # Header mit halbtransparentem Hintergrund
        # ---------------------------------------------------
        header = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp_scaled(70),
            padding=[dp_scaled(12), dp_scaled(8), dp_scaled(12), 0],
            spacing=dp_scaled(8)
        )

        # 💚 Leicht durchsichtiger grüner Hintergrund
        with header.canvas.before:
            Color(0.0, 0.3, 0.1, 0.45)  # R,G,B,Alpha (Alpha=Transparenz)
            self._header_bg = Rectangle(size=header.size, pos=header.pos)

        # Dynamisch mit Fenstergröße mitwachsen
        header.bind(size=lambda *_: setattr(self._header_bg, "size", header.size))
        header.bind(pos=lambda *_: setattr(self._header_bg, "pos", header.pos))
        
        # --- Linke Seite ---
        left = BoxLayout(orientation="vertical", size_hint_x=0.6, spacing=dp_scaled(2))
        self._value_lbl = Label(
            text="--", font_size=sp_scaled(28), color=(0.95, 1, 0.95, 1),
            bold=True, halign="left", valign="middle",
            size_hint_y=None, height=dp_scaled(36)
        )
        self._title_lbl = Label(
            markup=True, text="[b]—[/b]",
            font_size=sp_scaled(16),
            color=(0.8, 1, 0.85, 1),
            halign="left", valign="middle",
            size_hint_y=None, height=dp_scaled(24)
        )
        left.add_widget(self._value_lbl)
        left.add_widget(self._title_lbl)

        # --- Rechte Seite ---
        right = BoxLayout(orientation="horizontal", size_hint_x=0.4, spacing=dp_scaled(6))
        self._led_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp_scaled(28))
        with self._led_box.canvas:
            self._led_color = Color(1, 0, 0, 1)
            self._led_ellipse = Ellipse(size=(dp_scaled(16), dp_scaled(16)))

        def _pos_led(*_):
            self._led_ellipse.pos = (
                self._led_box.x + dp_scaled(6),
                self._led_box.y + (self._led_box.height - dp_scaled(16)) / 2
            )

        self._led_box.bind(pos=_pos_led, size=_pos_led)

        self._mac_lbl = Label(text="--", font_size=sp_scaled(13), color=(0.8, 1, 0.9, 1))
        self._rssi_lbl = Label(text="-- dBm", font_size=sp_scaled(13), color=(0.8, 1, 0.9, 1))
        rbox = BoxLayout(orientation="vertical")
        rbox.add_widget(self._mac_lbl)
        rbox.add_widget(self._rssi_lbl)
        right.add_widget(self._led_box)
        right.add_widget(rbox)

        header.add_widget(left)
        header.add_widget(right)
        self.add_widget(header)

        
        # Graph (transparent) mit stabilem Hintergrundbild darunter – Logik unverändert
        try:
            # Wrapper für Bild + Graph (keine weitere Logik anrühren)
            from kivy.uix.floatlayout import FloatLayout
            from kivy.uix.image import Image

            wrapper = FloatLayout(size_hint_y=1.0)

            # Hintergrundbild laden (füllt den Wrapper)
            bg_path = os.path.join(BASE_DIR, "assets", "tiles_bg.png")
            if os.path.exists(bg_path):
                bg_img = Image(
                    source=bg_path,
                    fit_mode="fill",           # modern statt keep_ratio/allow_stretch
                    size_hint=(1, 1),
                    pos_hint={"x": 0, "y": 0}
                )
                wrapper.add_widget(bg_img)
                print(f"🖼️ Hintergrund aktiv: {bg_path}")
            else:
                print("⚠️ tiles_bg.png nicht gefunden!")

            # Dein Graph – identische Achsen/Parameter, aber transparenter Hintergrund
            self.graph = Graph(
                xlabel="Time", ylabel="",
                x_ticks_major=10, y_ticks_major=0.5,
                background_color=(0, 0, 0, 0),   # transparent über dem Bild
                tick_color=(0.3, 0.8, 0.4, 1),
                draw_border=False,
                xmin=0, xmax=60, ymin=0, ymax=1,
                size_hint_y=1.0
            )

            # Dein dicker Mesh-Plot (VIVOSUN-Look)
            self.plot = MeshLinePlot(color=(0.8, 1.0, 0.8, 1))
            self.plot.line_width = 5.5
            self.graph.add_plot(self.plot)

            # Reihenfolge: erst Bild, dann Graph
            wrapper.add_widget(self.graph)

            # Wrapper statt Graph direkt einhängen (Buttons/Logik bleiben unberührt)
            self.add_widget(wrapper)

        except Exception as e:
            self._graph_ok = False
            self.add_widget(Label(text=f"⚠️ Graph not supported: {e}", color=(1, 0.8, 0.6, 1)))
        # Controls
        controls = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp_scaled(58), spacing=dp_scaled(8), padding=[dp_scaled(8)]*4
        )

        def _btn(text, bg, cb, w=None, fs=16):
            b = Button(
                markup=True, text=text, font_size=sp_scaled(fs),
                background_normal="", background_color=bg
            )
            # Button-Builder übergibt standardmäßig den Button (cb(b))
            b.bind(on_release=lambda *_: cb(b))
            if w:
                b.size_hint_x = None
                b.width = dp_scaled(w)
            return b

        controls.add_widget(_btn("[font=FA]\uf060[/font]", (0.25, 0.45, 0.28, 1),
                                 lambda *_: self._switch(-1), 58))
        controls.add_widget(_btn("[font=FA]\uf061[/font]", (0.25, 0.45, 0.28, 1),
                                 lambda *_: self._switch(+1), 58))
        # Reset: übergib einen Lambda-Wrapper, der das Button-Arg ignoriert
        controls.add_widget(_btn("[font=FA]\uf021[/font] Reset", (0.25, 0.55, 0.25, 1),
                                 lambda *_: self._do_reset()))

        # Start/Stop identisch zum Dashboard (ruft App-Handler auf)
        from kivy.app import App
        app = App.get_running_app()
        self._btn_startstop = _btn("[font=FA]\uf04d[/font] Stop", (0.6, 0.2, 0.2, 1),
                                   lambda b: app.on_stop_pressed(b))
        controls.add_widget(self._btn_startstop)

        controls.add_widget(_btn("[font=FA]\uf015[/font] Dashboard", (0.35, 0.28, 0.28, 1),
                                 lambda *_: self._close_view()))
        self.add_widget(controls)

        # Button-State beim Öffnen synchronisieren
        try:
            running = bool(getattr(app.chart_mgr, "running", True))
            if running:
                self._btn_startstop.text = "[font=FA]\uf04d[/font] Stop"
                self._btn_startstop.background_color = (0.6, 0.2, 0.2, 1)
            else:
                self._btn_startstop.text = "[font=FA]\uf04b[/font] Start"
                self._btn_startstop.background_color = (0.2, 0.6, 0.2, 1)
        except Exception:
            pass

    # ----------------------------------------------------
    # Live-Update
    # ----------------------------------------------------
    def _update_chart(self, *_, force=False):
        try:
            mgr = self.chart_mgr
            if not mgr:
                return

            active = bool(getattr(mgr, "running", False))
            paused = bool(getattr(mgr, "_user_paused", False))

            # LED-State
            if paused:
                self._led_color.rgba = (1.0, 0.9, 0.1, 1)  # gelb = pausiert
            elif active:
                self._led_color.rgba = (0.0, 1.0, 0.0, 1)  # grün = aktiv
            else:
                self._led_color.rgba = (0.4, 0.1, 0.1, 1)  # rot = aus

            # Daten
            buf = mgr.buffers.get(self.tile_key, [])
            clean = [(x, y) for x, y in buf if isinstance(y, (int, float)) and y > INVALID_SENTINEL]

            # Force-Modus nur bis erste Daten da sind
            if force and clean:
                self._force_until_data = False

            # Bei Stop/Pause: Anzeige einfrieren, nichts löschen
            if (not active or paused) and not force:
                if clean:
                    unit = self._unit_for_key(self.tile_key)
                    self._value_lbl.text = f"{clean[-1][1]:.2f} {unit}"
                    if self._graph_ok:
                        self.plot.points = clean
                return

            # Keine Daten: Anzeige neutral
            if not clean:
                self._value_lbl.text = "--"
                if self._graph_ok:
                    self.plot.points = []
                return

            # Live-Betrieb oder erzwungene Initialanzeige
            if self._graph_ok:
                self.plot.points = clean
                ys = [y for _, y in clean]
                y_min, y_max = min(ys), max(ys)
                if abs(y_max - y_min) < 1e-6:
                    y_min, y_max = y_min - 0.5, y_max + 0.5
                margin = max((y_max - y_min) * 0.2, 0.2)
                self.graph.ymin = round(y_min - margin, 2)
                self.graph.ymax = round(y_max + margin, 2)
                cw = int(getattr(mgr, "chart_window", 120) or 120)
                last_x = clean[-1][0]
                self.graph.xmax = max(last_x, cw)
                self.graph.xmin = max(0, self.graph.xmax - cw)
                self._value_lbl.text = f"{clean[-1][1]:.2f} {self._unit_for_key(self.tile_key)}"

            # Header Info (MAC + RSSI)
            app = self._get_app_safe()
            self._mac_lbl.text = str(getattr(app, "current_mac", None)
                                     or getattr(mgr, "cfg", {}).get("device_id", "--"))
            rssi = getattr(app, "last_rssi", None)
            self._rssi_lbl.text = f"{int(rssi)} dBm" if isinstance(rssi, (int, float)) else "-- dBm"

        except Exception as e:
            if not self._stale_warned:
                print("⚠️ Enlarged update error:", e)
                self._stale_warned = True

    # ----------------------------------------------------
    def _get_app_safe(self):
        try:
            from kivy.app import App
            return App.get_running_app()
        except Exception:
            return type("X", (), {})()

    # ----------------------------------------------------
    # Tile-Wechsel + Farben/Labels aktualisieren
    # ----------------------------------------------------
    def _switch(self, direction):
        allowed = self._allowed_keys_now()
        if not allowed:
            return
        try:
            idx = allowed.index(self.tile_key)
        except ValueError:
            idx = 0
        idx = (idx + direction) % len(allowed)
        self.tile_key = allowed[idx]
        self._refresh_titles_and_colors()
        # beim Wechsel sofort aktualisieren (auch im Pause/Stop-Fall)
        try:
            self._update_chart(force=True)
        except Exception:
            pass

    def _refresh_titles_and_colors(self):
        title = self._title(self.tile_key)
        unit  = self._unit_for_key(self.tile_key)
        try:
            self._title_lbl.text = f"[b]{title}[/b]"
        except Exception:
            pass

        if getattr(self, "_graph_ok", False):
            try:
                self.graph.ylabel = f"{title} ({unit})"
                rgb = COLOR_MAP.get(self.tile_key, (0.4, 1.0, 0.6))
                # alten Plot entfernen
                try:
                    if hasattr(self, "plot") and self.plot in self.graph.plots:
                        self.graph.remove_plot(self.plot)
                except Exception:
                    pass
                # neuen Plot setzen
                self.plot = LinePlot(color=(rgb[0], rgb[1], rgb[2], 1), line_width=4.0)
                self.graph.add_plot(self.plot)
                self.graph.tick_color = (rgb[0]*0.7, rgb[1]*0.9, rgb[2]*0.7, 1)
            except Exception:
                pass

    # ----------------------------------------------------
    # Aktionen
    # ----------------------------------------------------
    def _do_reset(self, *_, **__):
        """Komplett-Reset des aktuellen Charts – identisch zum Dashboard-Reset."""
        try:
            mgr = getattr(self, "chart_mgr", None)
            if not mgr:
                print("⚠️ Kein ChartManager vorhanden – Reset abgebrochen.")
                return
            if hasattr(mgr, "reset_data"):
                mgr.reset_data()
            if getattr(self, "_graph_ok", False):
                self.plot.points = []
            self._value_lbl.text = "--"
            print("🔁 Enlarged → Chart vollständig zurückgesetzt.")
        except Exception as e:
            print("💥 Reset-Fehler im Enlarged:", e)

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

    # (optional) lokaler Toggle – wird aktuell nicht benutzt, da Dashboard-Handler verwendet wird
    def _toggle_startstop(self, button):
        """Start/Stop wie Dashboard; nur falls direkt gebraucht."""
        mgr = getattr(self, "chart_mgr", None)
        if not mgr:
            return

        running = bool(getattr(mgr, "running", True))

        if running and hasattr(mgr, "user_stop"):
            mgr.user_stop()
            button.text = "[font=FA]\uf04b[/font] Start"
            button.background_color = (0.2, 0.6, 0.2, 1)
            self._led_color.rgba = (1.0, 0.9, 0.1, 1)
            print("⏸️ Enlarged → Charts eingefroren (user_stop)")

        elif not running and hasattr(mgr, "user_start"):
            mgr.user_start()
            button.text = "[font=FA]\uf04d[/font] Stop"
            button.background_color = (0.6, 0.2, 0.2, 1)
            self._led_color.rgba = (0.0, 1.0, 0.0, 1)
            print("▶️ Enlarged → Polling fortgesetzt (user_start)")

        # 🔄 Rück-Sync zum Dashboard (fix: echter ScreenManager-Zugriff)
        try:
            from kivy.app import App
            app = App.get_running_app()
            dash_screen = app.sm.get_screen("dashboard")
            dash_root = dash_screen.children[0]
            dash_btn = dash_root.ids.get("btn_startstop")
            if dash_btn:
                dash_btn.text = button.text
                dash_btn.background_color = button.background_color
            print("🔄 Dashboard-Button visuell synchronisiert.")
        except Exception as e:
            print("⚠️ Rück-Sync zum Dashboard fehlgeschlagen:", e)

    # ----------------------------------------------------
    # Touch-Swipe
    # ----------------------------------------------------
    def on_touch_down(self, touch):
        self._touch_start_x = touch.x
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._touch_start_x is None:
            return super().on_touch_up(touch)
        dx = touch.x - self._touch_start_x
        threshold = dp_scaled(40)
        if abs(dx) > threshold:
            self._switch(-1 if dx > 0 else +1)
        self._touch_start_x = None
        return super().on_touch_up(touch)
