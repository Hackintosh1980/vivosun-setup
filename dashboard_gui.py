#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Dashboard FINAL v3.5 – Neon (NoFooter Edition)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, sys
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.utils import platform
from kivy_garden.graph import Graph, MeshLinePlot

# -------------------------------------------------------
# 🌿 Globales UI-Scaling
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.7    # größere Touch-Flächen
else:
    UI_SCALE = 1.0    # Desktop kompakter

def sp_scaled(v): return f"{int(v * UI_SCALE)}sp"
def dp_scaled(v): return dp(v * UI_SCALE)

# -------------------------------------------------------
# 🌱 Font-Setup
# -------------------------------------------------------
if getattr(sys, "_MEIPASS", None):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

font_candidates = [os.path.join(BASE_DIR, "assets", "fonts", "VivosunEmoji.ttf")]
if platform == "android":
    font_candidates += ["/system/fonts/NotoColorEmoji.ttf"]
else:
    font_candidates += ["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"]

for f in font_candidates:
    if os.path.exists(f):
        LabelBase.register(name="VivosunEmoji", fn_regular=f)
        print("✅ Emoji-Font geladen:", f)
        break
else:
    print("⚠️ Kein Emoji-Font gefunden – Standardfont aktiv.")

# -------------------------------------------------------
# 🧩 KV-Layout
# -------------------------------------------------------
KV = f"""
<Header>:
    size_hint_y: None
    height: dp(18)
    padding: dp(8)
    spacing: dp(8)
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
            text: "🌱  Thermo Dashboard v3.5"
            bold: True
            font_size: "12sp"
            color: 0.90, 1, 0.92, 1
            halign: "left"
            valign: "middle"

        # ---- Spacer ----
        Widget:

        # ---- Uhrzeit ----
        Label:
            id: clocklbl
            text: "00:00:00"
            size_hint_x: None
            width: self.texture_size[0] + dp(12)
            font_size: "12sp"
            color: 0.80, 1.00, 0.85, 1
            halign: "right"
            valign: "middle"

        # ---- LED ----
        Widget:
            size_hint_x: None
            width: dp(24)
            canvas:
                Color:
                    rgba: app.chart_mgr.dashboard.ids.footer.led_color if hasattr(app, 'chart_mgr') else (0,1,0,1)
                Ellipse:
                    pos: self.x, self.center_y - dp(6)
                    size: dp(12), dp(12)

<Tile>:
    orientation: "vertical"
    padding: {dp_scaled(6)}
    spacing: {dp_scaled(4)}
    canvas.before:
        Color:
            rgba: 0.07, 0.11, 0.08, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12, 12, 12, 12]

    Label:
        text: root.title
        font_size: "{sp_scaled(14)}"
        color: 0.8, 1, 0.85, 1
        size_hint_y: None
        height: {dp_scaled(22)}

    Label:
        id: big
        text: root.value_text
        font_size: "{sp_scaled(22)}"
        color: 1, 1, 1, 1
        bold: True
        size_hint_y: None
        height: {dp_scaled(28)}

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
        # --- Crash-sicher: verhindert ZeroDivisionError ---
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
        led_color: 0,1,0,1
        status_text: "🟢 Simulation aktiv"

    GridLayout:
        id: grid
        cols: 3
        rows: 2
        padding: {dp_scaled(10)}
        spacing: {dp_scaled(10)}

        Tile:
            id: tile_t_in
            title: "🌡 Temp In"
            ymin: 10
            ymax: 40
            accent: 1, 0.45, 0.45
        Tile:
            id: tile_h_in
            title: "💧 Hum In"
            ymin: 20
            ymax: 100
            accent: 0.35, 0.70, 1
        Tile:
            id: tile_vpd_in
            title: "🌿 VPD In"
            ymin: 0
            ymax: 2.0
            accent: 0.85, 1.0, 0.45
        Tile:
            id: tile_t_out
            title: "🌡 Temp Out"
            ymin: -5
            ymax: 45
            accent: 1.0, 0.70, 0.35
        Tile:
            id: tile_h_out
            title: "💧 Hum Out"
            ymin: 15
            ymax: 100
            accent: 0.45, 0.95, 1.0
        Tile:
            id: tile_vpd_out
            title: "🌿 VPD Out"
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
            text: "🌿 Scatter"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.2, 0.5, 0.3, 1
            on_release: app.on_scatter_pressed()
        Button:
            text: "⚙️ Setup"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.3, 0.4, 0.5, 1
            on_release: app.on_setup_pressed()
        Button:
            id: btn_startstop
            text: "⏹ Stop"
            font_size: "{sp_scaled(16)}"
            background_normal: ""
            background_color: 0.6, 0.2, 0.2, 1
            on_release: app.on_stop_pressed(self)

        Button:
            text: "🔄 Reset"
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
    status_text = StringProperty("🟢 Simulation aktiv")

class Tile(BoxLayout):
    title = StringProperty("Title")
    value_text = StringProperty("--")
    ymin = NumericProperty(0)
    ymax = NumericProperty(100)
    accent = ListProperty([0.8, 1.0, 0.6])

class Dashboard(BoxLayout):
    pass

# -------------------------------------------------------
# Factory
# -------------------------------------------------------
def create_dashboard():
    from kivy.uix.label import Label
    try:
        Builder.unload_file("vivosun_dashboard_final")
        root = Builder.load_string(KV)
        if not isinstance(root, Dashboard):
            print("❌ KV-Rückgabe war None oder kein Dashboard-Objekt!")
            return Label(text="⚠️ Fehler im KV-Layout – kein Dashboard",
                         font_size="22sp", color=(1, 0, 0, 1))
        print("✅ Dashboard erfolgreich geladen!")
        return root
    except Exception as e:
        import traceback
        print("💥 Fehler beim Laden des KV:\n", traceback.format_exc())
        return Label(text=f"KV Fehler: {e}", font_size="22sp", color=(1, 0, 0, 1))
