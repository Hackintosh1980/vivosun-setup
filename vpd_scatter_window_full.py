#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vpd_scatter_window_live.py – Live-Version 🌿 v3.9
Einheitlich mit Dashboard (°C/°F) + Sensor-Erkennung.
© 2025 Dominik Rosenthal (Hackintosh1980)
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
from utils import calc_vpd, convert_temperature
import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
else:
    print("⚠️ Font fehlt:", FA_PATH)

class VPDScatterWindow(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.paused = False
        self.ext_present = True  # dynamisch
        self._build_ui()
        self._bind_json_poll()

    # ---------------------------------------------------
    # UI-Aufbau
    # ---------------------------------------------------
    def _build_ui(self):
        self.bg = Image(source="assets/vpd_bg.png", fit_mode="fill")
        self.add_widget(self.bg, index=0)

        # Header
        self.header = BoxLayout(orientation="horizontal", size_hint=(1, 0.1),
                                pos_hint={"x": 0, "y": 0.9}, padding=[15, 8], spacing=12)
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

        # Titel
        title_box = BoxLayout(orientation="horizontal", spacing=6, size_hint_x=0.45)
        title_box.add_widget(Label(text="\uf6c4", font_name="FA", font_size="18sp",
                                   color=(0.85, 1.0, 0.9, 1),
                                   size_hint_x=None, width=dp(24)))
        title_box.add_widget(Label(text="VPD Scatter", font_size="18sp",
                                   color=(0.95, 1.0, 0.95, 1),
                                   bold=True, halign="left"))
        self.header.add_widget(title_box)
        self.add_widget(self.header)

        # Graph
        unit = self._get_unit_symbol()
        self.graph = Graph(
            xlabel=f"Temp ({unit})", ylabel="Humidity (%)",
            x_ticks_major=5, y_ticks_major=10,
            xmin=0, xmax=35, ymin=30, ymax=90,
            background_color=(0, 0, 0, 0), draw_border=False,
            size_hint=(0.7, 0.75), pos_hint={"x": 0.05, "y": 0.15},
        )
        self.add_widget(self.graph)

        with self.graph.canvas:
            Color(0, 1, 0, 1)   # intern
            self.p1 = Ellipse(pos=(0, 0), size=(22, 22))
            Color(1, 0.6, 0, 1) # extern
            self.p2 = Ellipse(pos=(0, 0), size=(22, 22))

        # Livewerte rechts
        self.live_box = BoxLayout(orientation="vertical", size_hint=(0.22, 0.55),
                                  pos_hint={"x": 0.73, "y": 0.18}, spacing=8, padding=[10, 10])
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

        r1, self.t_in_lbl  = row("\uf2c9", "T_in: --.-°C", (0.8, 1, 0.8, 1))
        r2, self.h_in_lbl  = row("\uf043", "H_in: --.-%", (0.8, 1, 0.8, 1))
        r3, self.t_out_lbl = row("\uf2c9", "T_out: --.-°C", (1, 0.9, 0.7, 1))
        r4, self.h_out_lbl = row("\uf043", "H_out: --.-%", (1, 0.9, 0.7, 1))
        r5, self.vpd_in_lbl  = row("\uf06d", "VPD_in: --.-kPa", (0.8, 1, 0.8, 1))
        r6, self.vpd_out_lbl = row("\uf06d", "VPD_out: --.-kPa", (1, 0.9, 0.7, 1))
        for w in (r1, r2, r3, r4, r5, r6):
            self.live_box.add_widget(w)
        self.add_widget(self.live_box)

        # Footer
        self.footer = BoxLayout(orientation="horizontal", size_hint=(1, 0.1),
                                pos_hint={"x": 0, "y": 0}, spacing=10, padding=10)
        with self.footer.canvas.before:
            Color(0.05, 0.08, 0.06, 0.85)
            self.footer_bg = Rectangle(size=self.footer.size, pos=self.footer.pos)
        self.footer.bind(size=lambda *_: setattr(self.footer_bg, "size", self.footer.size))
        self.footer.bind(pos=lambda *_: setattr(self.footer_bg, "pos", self.footer.pos))
        self.btn_pause = Button(text='[font=assets/fonts/fa-solid-900.ttf]\uf04c[/font]  Pause',
                                markup=True, font_size="16sp",
                                background_normal="", background_color=(0.2, 0.6, 0.2, 1))
        self.btn_close = Button(text='[font=assets/fonts/fa-solid-900.ttf]\uf057[/font]  Close',
                                markup=True, font_size="16sp",
                                background_normal="", background_color=(0.6, 0.25, 0.25, 1))
        self.footer.add_widget(self.btn_pause); self.footer.add_widget(self.btn_close)
        self.add_widget(self.footer)

        self.btn_pause.bind(on_press=self.toggle_pause)
        self.btn_close.bind(on_press=self.close_self)

    # ---------------------------------------------------
    # Einheiten aus config.json
    # ---------------------------------------------------
    def _get_unit_symbol(self):
        try:
            cfg = config.load_config()
            return "°F" if cfg.get("unit", "°C") == "°F" else "°C"
        except Exception:
            return "°C"

    # ---------------------------------------------------
    # JSON Update
    # ---------------------------------------------------
    def _bind_json_poll(self):
        if os.name == "posix" and not os.getenv("ANDROID_PRIVATE"):
            self.json_path = "/home/domi/vivosun-setup/blebridge_desktop/ble_scan.json"
        else:
            self.json_path = os.path.join(os.getenv("ANDROID_PRIVATE", "."), "ble_scan.json")
        Clock.schedule_interval(self._update_from_json, 1.0)

    # ---------------------------------------------------
    # Live-Update – bevorzugt aus ChartManager, sonst JSON
    # ---------------------------------------------------
    def _update_from_json(self, dt):
        if self.paused:
            return
        try:
            # 🌿 1️⃣ Versuch: Livewerte direkt vom ChartManager nehmen
            from kivy.app import App
            app = App.get_running_app()
            chart_mgr = getattr(app, "chart_mgr", None)

            if chart_mgr and hasattr(chart_mgr, "buffers"):
                ext_present = bool(getattr(chart_mgr, "ext_present", True))
                self.ext_present = ext_present

                def _last(key):
                    buf = chart_mgr.buffers.get(key, [])
                    return buf[-1][1] if buf else -99.0

                t_int = _last("tile_t_in")
                h_int = _last("tile_h_in")
                t_ext = _last("tile_t_out")
                h_ext = _last("tile_h_out")

                # Einheit aus config übernehmen
                unit = self._get_unit_symbol()

                # ⚙️ Keine erneute Konvertierung – Werte aus ChartManager sind schon in °C oder °F
                # t_int / t_ext werden 1:1 übernommen

                # --- Externen Sensor erkennen ---
                self.ext_present = not (t_ext <= -90 or h_ext <= 0)

                # --- Interner Sensor ---
                vpd_in = calc_vpd(t_int, h_int)
                self.t_in_lbl.text  = f"T_in: {t_int:.1f}{unit}"
                self.h_in_lbl.text  = f"H_in: {h_int:.1f}%"
                self.vpd_in_lbl.text  = f"VPD_in: {vpd_in:.2f} kPa"

                # --- Externer Sensor ---
                if not self.ext_present:
                    self.t_out_lbl.text = "T_out: --"
                    self.h_out_lbl.text = "H_out: --"
                    self.vpd_out_lbl.text = "VPD_out: --"
                    self.p2.pos = (-999, -999)
                else:
                    vpd_out = calc_vpd(t_ext, h_ext)
                    self.t_out_lbl.text = f"T_out: {t_ext:.1f}{unit}"
                    self.h_out_lbl.text = f"H_out: {h_ext:.1f}%"
                    self.vpd_out_lbl.text = f"VPD_out: {vpd_out:.2f} kPa"
                    self._place_point(self.p2, t_ext, h_ext)

                # --- Punkte zeichnen ---
                self._place_point(self.p1, t_int, h_int)
                self.set_led(True)
                return  # ✅ fertig – keine JSON mehr nötig

            # 🌿 2️⃣ Fallback: JSON direkt lesen (wenn kein ChartManager aktiv)
            if not os.path.exists(self.json_path):
                return self.set_led(False)
            with open(self.json_path, "r") as f:
                content = f.read().strip()
            if not content:
                return self.set_led(False)

            data = json.loads(content)
            if not data or not isinstance(data, list):
                return self.set_led(False)
            d = data[0]

            # --- Sensorwerte ---
            t_int, h_int = float(d.get("temperature_int", 0.0)), float(d.get("humidity_int", 0.0))
            t_ext, h_ext = float(d.get("temperature_ext", -99.0)), float(d.get("humidity_ext", -99.0))
            unit = self._get_unit_symbol()
            if unit == "°F":
                from utils import convert_temperature
                t_int = convert_temperature(t_int, "F")
                t_ext = convert_temperature(t_ext, "F")

            # --- Externen Sensor erkennen ---
            self.ext_present = not (t_ext <= -90 or h_ext <= 0)
            if not self.ext_present:
                self.t_out_lbl.text = "T_out: --"
                self.h_out_lbl.text = "H_out: --"
                self.vpd_out_lbl.text = "VPD_out: --"
                self.p2.pos = (-999, -999)
            else:
                vpd_out = calc_vpd(t_ext, h_ext)
                self.t_out_lbl.text = f"T_out: {t_ext:.1f}{unit}"
                self.h_out_lbl.text = f"H_out: {h_ext:.1f}%"
                self.vpd_out_lbl.text = f"VPD_out: {vpd_out:.2f} kPa"
                self._place_point(self.p2, t_ext, h_ext)

            # --- Interner Sensor ---
            vpd_in = calc_vpd(t_int, h_int)
            self.t_in_lbl.text  = f"T_in: {t_int:.1f}{unit}"
            self.h_in_lbl.text  = f"H_in: {h_int:.1f}%"
            self.vpd_in_lbl.text  = f"VPD_in: {vpd_in:.2f} kPa"

            # --- Punkte zeichnen ---
            self._place_point(self.p1, t_int, h_int)
            self.set_led(True)

        except Exception as e:
            print("⚠️ Scatter update error:", e)
            self.set_led(False)
    # ---------------------------------------------------
    # Punktpositionen
    # ---------------------------------------------------
    def _place_point(self, ellipse, temp, hum):
        gx, gy = self.graph.pos
        gw, gh = self.graph.size
        xr = max(self.graph.xmax - self.graph.xmin, 0.0001)
        yr = max(self.graph.ymax - self.graph.ymin, 0.0001)
        tx = min(max(temp, self.graph.xmin), self.graph.xmax)
        hy = min(max(hum, self.graph.ymin), self.graph.ymax)
        x = gx + (tx - self.graph.xmin) / xr * gw
        y = gy + (hy - self.graph.ymin) / yr * gh
        ellipse.pos = (x - ellipse.size[0] / 2, y - ellipse.size[1] / 2)

    # ---------------------------------------------------
    # Steuerung / LED / Close
    # ---------------------------------------------------
    def toggle_pause(self, *_):
        self.paused = not self.paused
        self.btn_pause.text = (
            '[font=assets/fonts/fa-solid-900.ttf]\uf04b[/font]  Resume'
            if self.paused else
            '[font=assets/fonts/fa-solid-900.ttf]\uf04c[/font]  Pause'
        )
        self.set_led(not self.paused)

    def set_led(self, active=True):
        with self.led_canvas.canvas:
            Color(0, 1, 0, 1) if active else Color(1, 0, 0, 1)
            self.led_circle = Ellipse(pos=(15, 15), size=(20, 20))

    def close_self(self, *_):
        from kivy.uix.modalview import ModalView
        parent = self.parent
        while parent and not isinstance(parent, ModalView):
            parent = parent.parent
        if parent:
            parent.dismiss()
