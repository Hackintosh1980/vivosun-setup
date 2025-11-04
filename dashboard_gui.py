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
import config


# -------------------------------------------------------
# 🌿 Globales UI-Scaling
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.7
else:
    UI_SCALE = 1.0

def sp_scaled(v): return f"{int(v * UI_SCALE)}sp"
def dp_scaled(v): return dp(v * UI_SCALE)


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
    padding: [dp(12), dp(8), dp(12), dp(8)]  # ⬅️ Extra links/rechts Padding
    spacing: dp(10)
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
            text: "[font=FA]\\uf013[/font]  Thermo Dashboard v3.6"
            bold: True
            font_size: "13sp"
            color: 0.90, 1, 0.92, 1
            halign: "left"
            valign: "middle"
            size_hint_x: None
            width: dp(220)  # ⬅️ Mehr Platz, verhindert Abschneiden
            text_size: self.size
            shorten: False

        Widget:  # ⬅️ flexibler Spacer, schiebt Rest nach rechts

        # ---- Gerät + Bluetooth ----
        Label:
            id: device_label
            markup: True
            text: "[font=FA]\\uf293[/font] --"
            font_size: "12sp"
            color: 0.7, 0.95, 1.0, 1
            size_hint_x: None
            width: dp(180)
            halign: "right"
            valign: "middle"
            text_size: self.size

        # ---- RSSI ----
        BoxLayout:
            id: rssi_box
            orientation: "horizontal"
            size_hint_x: None
            width: dp(80)
            spacing: dp(3)
            Label:
                id: rssi_icon
                markup: True
                text: "[font=FA]\\uf012[/font]"
                font_size: "12sp"
                color: 0.6, 0.9, 0.6, 1
                size_hint_x: None
                width: dp(14)
            Label:
                id: rssi_value
                text: "-- dBm"
                font_size: "11sp"
                color: 0.7, 1.0, 0.8, 1

        # ---- Uhrzeit ----
        Label:
            id: clocklbl
            text: "00:00:00"
            size_hint_x: None
            width: dp(80)
            font_size: "12sp"
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
        height: {dp_scaled(22)}
        spacing: {dp_scaled(6)}

        Label:
            text: root.title
            markup: True
            font_size: "{sp_scaled(14)}"
            color: 0.8, 1, 0.85, 1
            halign: "left"
            size_hint_x: 0.6

        Label:
            id: big
            text: root.value_text
            font_size: "{sp_scaled(16)}"
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
            title: "[font=FA]\\uf2c9[/font]  Temp In"
            ymin: 10
            ymax: 40
            accent: 1, 0.45, 0.45
        Tile:
            id: tile_h_in
            title: "[font=FA]\\uf043[/font]  Hum In"
            ymin: 20
            ymax: 100
            accent: 0.35, 0.70, 1
        Tile:
            id: tile_vpd_in
            title: "[font=FA]\\uf06d[/font]  VPD In"
            ymin: 0
            ymax: 2.0
            accent: 0.85, 1.0, 0.45
        Tile:
            id: tile_t_out
            title: "[font=FA]\\uf2c9[/font]  Temp Out"
            ymin: -5
            ymax: 45
            accent: 1.0, 0.70, 0.35
        Tile:
            id: tile_h_out
            title: "[font=FA]\\uf043[/font]  Hum Out"
            ymin: 15
            ymax: 100
            accent: 0.45, 0.95, 1.0
        Tile:
            id: tile_vpd_out
            title: "[font=FA]\\uf06d[/font]  VPD Out"
            ymin: 0
            ymax: 2.0
            accent: 0.60, 1.0, 0.60

    # ---- Controlbar ----
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
# Widgets
# -------------------------------------------------------
class Header(BoxLayout):
    led_color = ListProperty([0, 1, 0, 1])
    status_text = StringProperty("📡 Live-Polling aktiv")


class Tile(BoxLayout):
    title = StringProperty("Title")
    value_text = StringProperty("--")
    ymin = NumericProperty(0)
    ymax = NumericProperty(100)
    accent = ListProperty([0.8, 1.0, 0.6])


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
        return root
    except Exception as e:
        import traceback
        print("💥 Fehler beim Laden des KV:\n", traceback.format_exc())
        return Label(text=f"KV Fehler: {e}", font_size="22sp", color=(1, 0, 0, 1))
