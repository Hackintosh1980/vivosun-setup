#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vpd_scatter_window_live.py – Reine Live-Version 🌿
UI im Neon-Dashboard-Style, Buttons mit FA-Icons
Kein Random/Timer außer JSON-Poll – echte Sensorwerte via update_values() oder BleBridge JSON.
"""

import os, json
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy_garden.graph import Graph
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.core.text import LabelBase
from kivy.metrics import dp
# ---------------------------------------------------
# Font Awesome Solid (für Icons) registrieren
# ---------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
    print("✅ Font Awesome geladen:", FA_PATH)
else:
    print("⚠️ Font Awesome fehlt (assets/fonts/fa-solid-900.ttf) – Icons fallen auf Standard zurück.")

class VPDScatterWindow(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ---------------------------------------------------
        # Hintergrundbild (nach hinten)
        # ---------------------------------------------------
        self.bg = Image(source="assets/vpd_bg.png", allow_stretch=True, keep_ratio=False)
        self.add_widget(self.bg, index=0)

        # ---------------------------------------------------
        # Header (LED • Titel • LIVE)
        # ---------------------------------------------------
        self.header = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.1),
            pos_hint={"x": 0, "y": 0.9},
            padding=[15, 8],
            spacing=12
        )
        with self.header.canvas.before:
            Color(0, 0, 0, 0.6)
            self.header_bg = Rectangle(size=self.header.size, pos=self.header.pos)
        self.header.bind(size=lambda *_: setattr(self.header_bg, "size", self.header.size))
        self.header.bind(pos=lambda *_: setattr(self.header_bg, "pos", self.header.pos))

        # LED
        self.led_canvas = FloatLayout(size_hint=(None, 1), width=50)
        with self.led_canvas.canvas:
            Color(0, 1, 0, 1)
            self.led_circle = Ellipse(pos=(15, 15), size=(20, 20))
        self.header.add_widget(self.led_canvas)


        # Titel (Icon + Text)
        title_box = BoxLayout(
            orientation="horizontal",
            spacing=6,
            size_hint_x=0.45,      # <-- flexibler Anteil statt fester Breite
            height=dp(24),
            pos_hint={"center_y": 0.5}
        )
        title_box.add_widget(Label(
            text="\uf6c4",
            font_name="FA",
            font_size="18sp",
            color=(0.85, 1.0, 0.9, 1),
            size_hint_x=None,
            width=dp(24)
        ))
        title_box.add_widget(Label(
            text="VPD Scatter",
            font_size="18sp",
            color=(0.95, 1.0, 0.95, 1),
            bold=True,
            halign="left",
            valign="middle",
            text_size=(None, None)
        ))
        self.header.add_widget(title_box)
        self.add_widget(self.header)

        # ---------------------------------------------------
        # Graph – X: 0…35 °C (gewünscht), Y: 30…90 %
        # ---------------------------------------------------
        self.graph = Graph(
            xlabel="Temp (°C)", ylabel="Humidity (%)",
            x_ticks_major=5, y_ticks_major=10,
            x_grid_label=True, y_grid_label=True,
            xmin=0, xmax=35,     # ← runter bis 0 °C
            ymin=30, ymax=90,
            background_color=(0, 0, 0, 0),
            draw_border=False,
            size_hint=(0.7, 0.75),
            pos_hint={"x": 0.05, "y": 0.15},
        )
        self.add_widget(self.graph)

        # Punkte auf Graph-Canvas
        with self.graph.canvas:
            Color(0, 1, 0, 1)        # intern (grün)
            self.p1 = Ellipse(pos=(0, 0), size=(22, 22))
            Color(1, 0.5, 0, 1)      # extern (orange)
            self.p2 = Ellipse(pos=(0, 0), size=(22, 22))

        # ---------------------------------------------------
        # Livewert-Box rechts (kompakt, mit Icons)
        # ---------------------------------------------------
        self.live_box = BoxLayout(
            orientation="vertical",
            size_hint=(0.22, 0.55),
            pos_hint={"x": 0.73, "y": 0.18},
            spacing=8,
            padding=[10, 10]
        )
        with self.live_box.canvas.before:
            Color(0, 0, 0, 0.45)
            self.live_bg = Rectangle(size=self.live_box.size, pos=self.live_box.pos)
        self.live_box.bind(size=lambda *_: setattr(self.live_bg, "size", self.live_box.size))
        self.live_box.bind(pos=lambda *_: setattr(self.live_bg, "pos", self.live_box.pos))

        def row(icon, text, color):
            box = BoxLayout(orientation="horizontal", spacing=6, size_hint_y=None, height="26dp")
            icon_lbl = Label(text=icon, font_name="FA", font_size="16sp",
                             color=color, size_hint_x=None, width=22)
            txt_lbl = Label(text=text, font_size="16sp", color=color)
            box.add_widget(icon_lbl); box.add_widget(txt_lbl)
            return box, txt_lbl

        r1, self.t_in_lbl  = row("\uf2c9", "T_in: --.-°C", (0.8, 1, 0.8, 1))   # thermometer
        r2, self.h_in_lbl  = row("\uf043", "H_in: --.-%",  (0.8, 1, 0.8, 1))   # tint (water)
        r3, self.t_out_lbl = row("\uf2c9", "T_out: --.-°C",(1, 0.9, 0.7, 1))
        r4, self.h_out_lbl = row("\uf043", "H_out: --.-%", (1, 0.9, 0.7, 1))

        for w in (r1, r2, r3, r4):
            self.live_box.add_widget(w)
        self.add_widget(self.live_box)

        # ---------------------------------------------------
        # ---------------------------------------------------
        # Footer mit Icons (FA-Symbol + Standardtext)
        # ---------------------------------------------------
        self.footer = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.1),
            pos_hint={"x": 0, "y": 0},
            spacing=10,
            padding=10
        )
        with self.footer.canvas.before:
            Color(0.05, 0.08, 0.06, 0.85)
            self.footer_bg = Rectangle(size=self.footer.size, pos=self.footer.pos)
        self.footer.bind(size=lambda *_: setattr(self.footer_bg, "size", self.footer.size))
        self.footer.bind(pos=lambda *_: setattr(self.footer_bg, "pos", self.footer.pos))

        # 🔘 Buttons: Icon (FA) + Text (Standard)
        self.btn_pause = Button(
            text='[font=assets/fonts/fa-solid-900.ttf]\uf04c[/font]  Pause',
            markup=True,
            font_size="16sp",
            background_normal="",
            background_color=(0.2, 0.6, 0.2, 1)
        )
        self.btn_close = Button(
            text='[font=assets/fonts/fa-solid-900.ttf]\uf057[/font]  Close',
            markup=True,
            font_size="16sp",
            background_normal="",
            background_color=(0.6, 0.25, 0.25, 1)
        )

        self.footer.add_widget(self.btn_pause)
        self.footer.add_widget(self.btn_close)
        self.add_widget(self.footer)

        # ---------------------------------------------------
        # ---------------------------------------------------
        # JSON-Live-Update (Desktop oder Android)
        # ---------------------------------------------------
        if os.name == "posix" and not os.getenv("ANDROID_PRIVATE"):
            # 💻 Desktop/Linux
            self.json_path = "/home/domi/vivosun-setup/blebridge_desktop/ble_scan.json"
        else:
            # 🤖 Android-App-Verzeichnis
            self.json_path = os.path.join(os.getenv("ANDROID_PRIVATE", "."), "ble_scan.json")

        self.paused = False
        self.btn_pause.bind(on_press=self.toggle_pause)
        self.btn_close.bind(on_press=self.close_self)

        # Poll (keine Simulation)
        Clock.schedule_interval(self._update_from_json, 1.0)

    # ---------------------------------------------------
    # Live-Update aus JSON (BleBridge)
    # ---------------------------------------------------
    def _update_from_json(self, dt):
        if self.paused:
            return
        try:
            if not os.path.exists(self.json_path):
                self.set_led(False); return

            with open(self.json_path, "r") as f:
                content = f.read().strip()
                if not content:
                    self.set_led(False); return

            data = json.loads(content)
            if not data or not isinstance(data, list):
                self.set_led(False); return

            d = data[0]
            t_int = float(d.get("temperature_int", 0.0))
            h_int = float(d.get("humidity_int", 0.0))
            t_ext = float(d.get("temperature_ext", 0.0))
            h_ext = float(d.get("humidity_ext", 0.0))

            # Labels
            self.t_in_lbl.text  = f"T_in: {t_int:.1f}°C"
            self.h_in_lbl.text  = f"H_in: {h_int:.1f}%"
            self.t_out_lbl.text = f"T_out: {t_ext:.1f}°C"
            self.h_out_lbl.text = f"H_out: {h_ext:.1f}%"

            # Punkte positionieren
            self._place_point(self.p1, t_int, h_int)
            self._place_point(self.p2, t_ext, h_ext)

            self.set_led(True)
        except Exception as e:
            print("⚠️ Scatter update error:", e)
            self.set_led(False)

    # Wert → Pixelposition im Graph
    def _place_point(self, ellipse, temp_c, hum_pct):
        gx, gy = self.graph.pos
        gw, gh = self.graph.size

        xr = max(self.graph.xmax - self.graph.xmin, 0.0001)
        yr = max(self.graph.ymax - self.graph.ymin, 0.0001)

        tx = min(max(temp_c, self.graph.xmin), self.graph.xmax)
        hy = min(max(hum_pct, self.graph.ymin), self.graph.ymax)

        x = gx + (tx - self.graph.xmin) / xr * gw
        y = gy + (hy - self.graph.ymin) / yr * gh

        ellipse.pos = (x - ellipse.size[0] / 2.0, y - ellipse.size[1] / 2.0)

    # ---------------------------------------------------
    # Öffentliche API (falls direkte Übergabe aus Dashboard)
    # ---------------------------------------------------
    def update_values(self, t_int, h_int, t_ext, h_ext):
        if self.paused:
            return
        self.t_in_lbl.text  = f"T_in: {t_int:.1f}°C"
        self.h_in_lbl.text  = f"H_in: {h_int:.1f}%"
        self.t_out_lbl.text = f"T_out: {t_ext:.1f}°C"
        self.h_out_lbl.text = f"H_out: {h_ext:.1f}%"
        self._place_point(self.p1, t_int, h_int)
        self._place_point(self.p2, t_ext, h_ext)
        self.set_led(True)

    # ---------------------------------------------------
    # Steuerlogik
    # ---------------------------------------------------
    def toggle_pause(self, *_):
        self.paused = not self.paused
        if self.paused:
            # ▶ Resume – normales Icon + Standardtext
            self.btn_pause.text = (
                '[font=assets/fonts/fa-solid-900.ttf]\uf04b[/font]  Resume'
            )
        else:
            # ⏸ Pause – normales Icon + Standardtext
            self.btn_pause.text = (
                '[font=assets/fonts/fa-solid-900.ttf]\uf04c[/font]  Pause'
            )
        self.btn_pause.markup = True
        self.set_led(not self.paused)

    def set_led(self, active=True):
        with self.led_canvas.canvas:
            Color(0, 1, 0, 1) if active else Color(1, 0, 0, 1)
            self.led_circle = Ellipse(pos=(15, 15), size=(20, 20))

    def close_self(self, *_):
        from kivy.uix.modalview import ModalView
        parent = self.parent
        while parent:
            if isinstance(parent, ModalView):
                parent.dismiss()
                break
            parent = parent.parent


# Einzelstart zum Testen
class ScatterApp(App):
    def build(self):
        return VPDScatterWindow()

if __name__ == "__main__":
    ScatterApp().run()
