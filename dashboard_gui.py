#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Dashboard v3.6 – Neon Stable (NoFooter Edition)
Kompatibel mit main.py & ChartManager v3.6
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.utils import platform
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from kivy.core.window import Window
import config


# -------------------------------------------------------
# 🌿 Globales UI-Scaling
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.7
else:
    UI_SCALE = 1.0

def sp_scaled(v): 
    return f"{int(v * UI_SCALE)}sp"

def dp_scaled(v): 
    return dp(v * UI_SCALE)

# -------------------------------------------------------
# 💻 Desktop-Startgröße setzen
# -------------------------------------------------------

if platform not in ("android", "ios"):
    try:
        Window.size = (1400, 800)      # Breite, Höhe
        Window.minimum_width = 900
        Window.minimum_height = 600
        Window.title = "VIVOSUN Ultimate Dashboard 🌿"
        print(f"🖥️ Desktop window initialized: {Window.size}")
    except Exception as e:
        print(f"⚠️ Window init failed: {e}")
# -------------------------------------------------------
# 🌱 Font Setup
# -------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")

if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
    print("✅ Font Awesome geladen:", FA_PATH)
else:
    print("❌ Font fehlt:", FA_PATH)


# -------------------------------------------------------
# 🧩 KV-Layout
# -------------------------------------------------------
KV = f"""
<Header>:
    size_hint_y: None
    height: dp(38)
    padding: [dp(14), dp(8), dp(14), dp(8)]
    spacing: dp(14)
    canvas.before:
        Color:
            rgba: 0.05, 0.08, 0.06, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: "horizontal"
        spacing: dp(10)

        # ---- Titel links ----
        Label:
            markup: True
            text: "[font=FA]\\uf06d[/font]  Ultimate Thermo Dashboard v3.6"
            bold: True
            font_size: "15sp"
            color: 0.90, 1, 0.92, 1
            halign: "left"
            valign: "middle"
            size_hint_x: 0.45     # etwas mehr Flex als feste Breite
            text_size: self.size
            shorten: False

        # ---- Dynamischer Zwischenraum ----
        Widget:
            size_hint_x: 0.05

        # ---- Gerät + Bluetooth ----
        Label:
            id: device_label
            markup: True
            text: "[font=FA]\\uf6a9[/font] --"
            font_size: "14sp"
            color: 0.7, 0.95, 1.0, 1
            halign: "right"
            valign: "middle"
            text_size: self.size
            size_hint_x: 0.35     # vorher 0.25, jetzt mehr Platz für lange MACs

        # ---- RSSI + BT LED ----
        BoxLayout:
            id: rssi_box
            orientation: "horizontal"
            size_hint_x: 0.15     # etwas flexibler statt 110 dp
            spacing: dp(6)
            Label:
                id: rssi_icon
                markup: True
                text: "[font=FA]\\uf012[/font]"
                font_size: "13sp"
                color: 0.6, 0.9, 0.6, 1
                size_hint_x: None
                width: dp(18)
            Label:
                id: rssi_value
                text: "-- dBm"
                font_size: "13sp"
                color: 0.7, 1.0, 0.8, 1
                shorten: False
            Widget:
                id: bt_led_placeholder
                size_hint_x: None
                width: dp(22)

        # ---- Uhrzeit ----
        Label:
            id: clocklbl
            text: "00:00:00"
            size_hint_x: 0.1
            font_size: "14sp"
            color: 0.8, 1.0, 0.85, 1
            halign: "right"
            valign: "middle"



<Tile>:
    orientation: "vertical"
    padding: {dp_scaled(6)}
    spacing: {dp_scaled(2)}
    canvas.before:
        Color:
            rgba: 0.07, 0.11, 0.08, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12, 12, 12, 12]

    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: {dp_scaled(32)}
        spacing: {dp_scaled(8)}

        Label:
            text: root.title
            markup: True
            font_size: "{sp_scaled(17)}"
            color: 0.8, 1, 0.85, 1
            halign: "left"
            size_hint_x: 0.6

        Label:
            id: big
            text: root.value_text
            font_size: "{sp_scaled(22)}"
            color: 1, 1, 1, 1
            bold: True
            halign: "right"
            size_hint_x: 0.4

    Graph:
        id: g
        size_hint_y: 1.0
        xmin: 0
        xmax: 60
        ymin: root.ymin
        ymax: root.ymax
        draw_border: False
        background_color: 0.05, 0.07, 0.06, 1
        tick_color: 0.3, 0.8, 0.4, 1
        x_ticks_major: 10
        y_ticks_major: max((root.ymax - root.ymin) / 8.0, 0.5)


<Dashboard>:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: 0.02, 0.05, 0.03, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Header:
        id: header

    GridLayout:
        id: grid
        cols: 3
        rows: 2
        padding: {dp_scaled(10)}
        spacing: {dp_scaled(10)}

        Tile:
            id: tile_t_in
            tile_key: "tile_t_in"
            title: "[font=FA]\\uf2c9[/font]  Temp In"
            ymin: 10
            ymax: 40
            accent: 1, 0.45, 0.45
        Tile:
            id: tile_h_in
            tile_key: "tile_h_in"
            title: "[font=FA]\\uf043[/font]  Hum In"
            ymin: 20
            ymax: 100
            accent: 0.35, 0.70, 1
        Tile:
            id: tile_vpd_in
            tile_key: "tile_vpd_in"
            title: "[font=FA]\\uf06d[/font]  VPD In"
            ymin: 0
            ymax: 2.0
            accent: 0.85, 1.0, 0.45
        Tile:
            id: tile_t_out
            tile_key: "tile_t_out"
            title: "[font=FA]\\uf2c9[/font]  Temp Out"
            ymin: -5
            ymax: 45
            accent: 1.0, 0.70, 0.35
        Tile:
            id: tile_h_out
            tile_key: "tile_h_out"
            title: "[font=FA]\\uf043[/font]  Hum Out"
            ymin: 15
            ymax: 100
            accent: 0.45, 0.95, 1.0
        Tile:
            id: tile_vpd_out
            tile_key: "tile_vpd_out"
            title: "[font=FA]\\uf06d[/font]  VPD Out"
            ymin: 0
            ymax: 2.0
            accent: 0.60, 1.0, 0.60

    BoxLayout:
        id: controlbar
        size_hint_y: None
        height: {dp_scaled(56)}
        spacing: {dp_scaled(8)}
        padding: {dp_scaled(8)}

        Button:
            markup: True
            text: "[font=FA]\\uf06c[/font]  Scatter"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.2, 0.5, 0.3, 1
            on_release: app.on_scatter_pressed()

        Button:
            markup: True
            text: "[font=FA]\\uf013[/font]  Setup"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.3, 0.4, 0.5, 1
            on_release: app.on_setup_pressed()

        Button:
            id: btn_startstop
            markup: True
            text: "[font=FA]\\uf04d[/font]  Stop"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.6, 0.2, 0.2, 1
            on_release: app.on_stop_pressed(self)

        Button:
            markup: True
            text: "[font=FA]\\uf021[/font]  Reset"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.25, 0.45, 0.25, 1
            on_release: app.on_reset_pressed()

Dashboard:
"""

# -------------------------------------------------------
# 🔵 Kleine Status-LED für BT / Polling
# -------------------------------------------------------
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse
from kivy.properties import NumericProperty
from kivy.animation import Animation


class BtLedWidget(BoxLayout):
    """Bluetooth/Polling-LED mit 3 Zuständen und sanftem Fading"""
    a = NumericProperty(1.0)  # Alpha zum Faden
    _fade_anim = None
    _pulse_anim = None

    def __init__(self, chart_mgr=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_x=None, width=dp(20), **kwargs)
        self.chart_mgr = chart_mgr
        self._state = "off"

        with self.canvas:
            self._color = Color(0.4, 0.1, 0.1, 1)  # rot-braun initial
            self._circle = Ellipse(size=(dp(14), dp(14)))

        self.bind(pos=self._update_pos, size=self._update_pos)
        Clock.schedule_interval(self._update_led, 0.8)
        self.bind(a=self._apply_alpha)

    def _update_pos(self, *_):
        self._circle.pos = (
            self.x + dp(3),
            self.y + (self.height - dp(14)) / 2
        )

    # ----------------------------------------------------
    # Farbwechsel mit Fading
    # ----------------------------------------------------
    def _fade_to(self, rgba, duration=0.4):
        """Animiert sanft von aktueller Farbe zu neuer Farbe"""
        if self._fade_anim:
            self._fade_anim.cancel(self)
        old = list(self._color.rgba)
        target = rgba

        def _step(animation, widget, progress):
            new_col = [old[i] + (target[i] - old[i]) * progress for i in range(4)]
            self._color.rgba = new_col

        self._fade_anim = Animation(a=1.0, d=duration)
        self._fade_anim.bind(on_progress=_step)
        self._fade_anim.start(self)

    # ----------------------------------------------------
    # LED-Logik (stabil – Originalzustand)
    # ----------------------------------------------------
    def _update_led(self, *_):
        mgr = self.chart_mgr
        if not mgr:
            return

        running = bool(getattr(mgr, "running", False))
        paused  = bool(getattr(mgr, "_user_paused", False))

        # Prüfen, ob Puffer gefüllt ist
        has_data = False
        try:
            if hasattr(mgr, "buffers"):
                for buf in mgr.buffers.values():
                    if buf and len(buf) > 0:
                        has_data = True
                        break
        except Exception:
            has_data = False

        # Prüfen, ob JSON existiert und gültig ist
        json_ok = False
        try:
            from dashboard_charts import APP_JSON
            if os.path.exists(APP_JSON):
                with open(APP_JSON, "r") as f:
                    content = f.read().strip()
                if content:
                    json_ok = True
        except Exception:
            json_ok = False

        # 🔴 AUS (Poller gestoppt)
        if not running:
            if self._state != "off":
                self._fade_to((0.4, 0.1, 0.1, 1))
                self._stop_pulse()
                self._state = "off"
            return

        # 🟡 PAUSIERT
        if paused:
            if self._state != "paused":
                self._fade_to((1.0, 0.9, 0.1, 1))
                self._stop_pulse()
                self._state = "paused"
            return

        # 🔵 SUCHMODUS – aktiv, aber keine Daten & keine gültige JSON
        if running and not paused and (not has_data or not json_ok):
            if self._state != "search":
                self._fade_to((0.2, 0.45, 1.0, 1))
                self._start_pulse()
                self._state = "search"
            return

        # 🟢 AKTIV (Datenfluss erkannt)
        if running and not paused and has_data and json_ok:
            if self._state != "on":
                self._fade_to((0.0, 1.0, 0.0, 1))
                self._start_pulse()
                self._state = "on"

    # ----------------------------------------------------
    # Pulsanimation (Atmen)
    # ----------------------------------------------------
    def _start_pulse(self):
        self._stop_pulse()
        self._pulse_anim = Animation(a=0.55, d=0.9, t="in_out_quad") + \
                           Animation(a=1.0, d=0.9, t="in_out_quad")
        self._pulse_anim.repeat = True
        self._pulse_anim.start(self)

    def _stop_pulse(self):
        if self._pulse_anim:
            self._pulse_anim.cancel(self)
            self._pulse_anim = None
        self.a = 1.0

    def _apply_alpha(self, *_):
        """Alpha auf die aktuelle LED-Farbe anwenden."""
        r, g, b, _ = self._color.rgba
        self._color.rgba = (r, g, b, self.a)
# -------------------------------------------------------
# Widgets
# -------------------------------------------------------
class Header(BoxLayout):
    led_color = ListProperty([0, 1, 0, 1])
    status_text = StringProperty("📡 Live-Polling aktiv")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            from kivy.app import App
            app = App.get_running_app()
            chart_mgr = getattr(app, "chart_mgr", None)
        except Exception:
            chart_mgr = None

                    
class Tile(BoxLayout):
    title = StringProperty("Title")
    value_text = StringProperty("--")
    ymin = NumericProperty(0)
    ymax = NumericProperty(100)
    accent = ListProperty([0.8, 1.0, 0.6])

    # NEU: eigener Schlüssel für Enlarged
    tile_key = StringProperty("")

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            try:
                from kivy.app import App
                from kivy.uix.modalview import ModalView
                from enlarged_chart_window import EnlargedChartWindow
                app = App.get_running_app()
                popup = ModalView(size_hint=(1, 1), auto_dismiss=False)
                # WICHTIG: start_key aus tile_key, NICHT self.id
                popup.add_widget(EnlargedChartWindow(app.chart_mgr, start_key=self.tile_key))
                popup.open()
                print(f"🔍 Enlarged geöffnet für Tile: {self.tile_key}")
            except Exception as e:
                print(f"⚠️ Enlarged-Open-Fehler ({self.tile_key}): {e}")
        return super().on_touch_down(touch)

class Dashboard(BoxLayout):
    """Dashboard mit Auto-Bridge-Start (einmalig beim Anzeigen)"""
    _bridge_once = False

    def on_kv_post(self, base_widget):
        if platform == "android" and not self._bridge_once:
            self._bridge_once = True
            Clock.schedule_once(self._start_bridge, 1.0)

    def _start_bridge(self, *_):
        """Startet BLE-Bridge automatisch beim ersten Anzeigen."""
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ctx = PythonActivity.mActivity
            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")

            cfg = config.load_config() or {}
            device_id = cfg.get("device_id")

            ret = BleBridgePersistent.start(ctx, "ble_scan.json")
            print(f"📡 Dashboard Bridge-Start → {ret}")

            if not device_id:
                BleBridgePersistent.setActiveMac(None)
                print("🔍 Kein Device-ID → Vollscan aktiv")
            else:
                BleBridgePersistent.setActiveMac(device_id)
                print(f"🎯 Aktive MAC gesetzt: {device_id}")

        except Exception as e:
            print(f"⚠️ Fehler im Dashboard Bridge-Start: {e}")


# -------------------------------------------------------
# Factory
# -------------------------------------------------------
def create_dashboard():
    from kivy.uix.label import Label
    try:
        Builder.unload_file("vivosun_dashboard_final")
        root = Builder.load_string(KV)
        if not isinstance(root, Dashboard):
            return Label(text="⚠️ Fehler im KV-Layout – kein Dashboard",
                         font_size="22sp", color=(1, 0, 0, 1))
        print("✅ Dashboard erfolgreich geladen!")

        # -------------------------------------------------------
        # 💡 BT-LED nachträglich in den Header einsetzen
        # -------------------------------------------------------
        try:
            from kivy.clock import Clock
            def _insert_led(*_):
                from dashboard_gui import BtLedWidget  # <— FIXED IMPORT
                from kivy.app import App
                app = App.get_running_app()
                hdr = root.ids.header
                if hdr and "bt_led_placeholder" in hdr.ids:
                    led = BtLedWidget(getattr(app, "chart_mgr", None))
                    parent = hdr.ids.bt_led_placeholder.parent
                    parent.remove_widget(hdr.ids.bt_led_placeholder)
                    parent.add_widget(led)
                    print("💡 BT-LED erfolgreich in Header eingesetzt.")
                else:
                    print("⚠️ Kein bt_led_placeholder gefunden!")
            Clock.schedule_once(_insert_led, 0.5)
        except Exception as e:
            print(f"⚠️ LED-Insert-Fehler: {e}")

        return root

    except Exception as e:
        import traceback
        print("💥 Fehler beim Laden des KV:\n", traceback.format_exc())
        return Label(text=f"KV Fehler: {e}", font_size="22sp", color=(1, 0, 0, 1))
