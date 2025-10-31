#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vpd_scatter_window_live.py – Reine Live-Version 🌿
Für Integration in Vivosun Ultimate Dashboard auf Android.
Kein Random- oder Timer-Loop mehr – echte Sensorwerte via update_values().
"""

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy_garden.graph import Graph
from kivy.graphics import Color, Ellipse, Rectangle


class VPDScatterWindow(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ---------------------------------------------------
        # Hintergrundbild (nach hinten)
        # ---------------------------------------------------
        self.bg = Image(source="assets/vpd_bg.png",
                        allow_stretch=True, keep_ratio=False)
        self.add_widget(self.bg, index=0)

        # ---------------------------------------------------
        # Header (LED + Titel + Live)
        # ---------------------------------------------------
        self.header = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.1),
            pos_hint={"x": 0, "y": 0.9},
            padding=[15, 8],
            spacing=15
        )

        with self.header.canvas.before:
            Color(0, 0, 0, 0.6)
            self.header_bg = Rectangle(size=self.header.size, pos=self.header.pos)
        self.header.bind(size=lambda *_: setattr(self.header_bg, "size", self.header.size))
        self.header.bind(pos=lambda *_: setattr(self.header_bg, "pos", self.header.pos))

        # LED-Kreis
        self.led_canvas = FloatLayout(size_hint=(None, 1), width=50)
        with self.led_canvas.canvas:
            Color(0, 1, 0, 1)
            self.led_circle = Ellipse(pos=(15, 15), size=(20, 20))
        self.header.add_widget(self.led_canvas)

        self.title = Label(
            text="🌿 VPD Scatter",
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="left"
        )
        self.header.add_widget(self.title)

        self.live_label = Label(
            text="[b]LIVE[/b]",
            markup=True,
            font_size="18sp",
            color=(1, 0.8, 0, 1)
        )
        self.header.add_widget(self.live_label)

        self.add_widget(self.header)

        # ---------------------------------------------------
        # Graph (leer, bereit für Livepunkte)
        # ---------------------------------------------------
        self.graph = Graph(
            xlabel="Temp (°C)",
            ylabel="Humidity (%)",
            x_ticks_major=5,
            y_ticks_major=10,
            x_grid_label=True,
            y_grid_label=True,
            xmin=15, xmax=35,
            ymin=30, ymax=90,
            background_color=(0, 0, 0, 0),
            draw_border=False,
            size_hint=(0.7, 0.75),
            pos_hint={"x": 0.05, "y": 0.15},
        )
        self.add_widget(self.graph)

        with self.graph.canvas:
            Color(0, 1, 0, 1)
            self.p1 = Ellipse(pos=(0, 0), size=(22, 22))
            Color(1, 0.5, 0, 1)
            self.p2 = Ellipse(pos=(0, 0), size=(22, 22))

        # ---------------------------------------------------
        # Livewert-Box
        # ---------------------------------------------------
        self.live_box = BoxLayout(
            orientation="vertical",
            size_hint=(0.25, 0.75),
            pos_hint={"x": 0.75, "y": 0.15},
            padding=10,
            spacing=6
        )

        with self.live_box.canvas.before:
            Color(0, 0, 0, 0.5)
            self.live_bg = Rectangle(size=self.live_box.size, pos=self.live_box.pos)
        self.live_box.bind(size=lambda *_: setattr(self.live_bg, "size", self.live_box.size))
        self.live_box.bind(pos=lambda *_: setattr(self.live_bg, "pos", self.live_box.pos))

        self.lbl_t1 = Label(text="Internal Temp: --.-°C", font_size="18sp", color=(0.8, 1, 0.8, 1))
        self.lbl_h1 = Label(text="Internal Hum: --.-%", font_size="18sp", color=(0.8, 1, 0.8, 1))
        self.lbl_t2 = Label(text="External Temp: --.-°C", font_size="18sp", color=(1, 0.9, 0.7, 1))
        self.lbl_h2 = Label(text="External Hum: --.-%", font_size="18sp", color=(1, 0.9, 0.7, 1))

        for w in [self.lbl_t1, self.lbl_h1, self.lbl_t2, self.lbl_h2]:
            self.live_box.add_widget(w)

        self.add_widget(self.live_box)
        


        # ---------------------------------------------------
        # 🧠 Live-Update aus BLE-Bridge-JSON
        # ---------------------------------------------------
        from kivy.clock import Clock
        import os, json

        self.json_path = os.path.join(
            os.getenv("ANDROID_PRIVATE", "."),  # Android-kompatibler Pfad
            "ble_scan.json"  # oder dein Dateiname, z.B. ble_data.json
        )

        def _update_from_json(dt):
            try:
                if not os.path.exists(self.json_path):
                    return
                with open(self.json_path, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return
                    data = json.loads(content)
                    if not data or not isinstance(data, list):
                        return

                d = data[0]  # nur ersten Eintrag
                t_int = d.get("temperature_int", 0)
                h_int = d.get("humidity_int", 0)
                t_ext = d.get("temperature_ext", 0)
                h_ext = d.get("humidity_ext", 0)

                # Labels aktualisieren
                self.lbl_t1.text = f"Internal Temp: {t_int:.1f}°C"
                self.lbl_h1.text = f"Internal Hum: {h_int:.1f}%"
                self.lbl_t2.text = f"External Temp: {t_ext:.1f}°C"
                self.lbl_h2.text = f"External Hum: {h_ext:.1f}%"

                # Ellipsen-Positionen berechnen (Normierung auf Graph-Koordinaten)
                gx, gy = self.graph.pos
                gw, gh = self.graph.size

                def _map(x, in_min, in_max, out_min, out_max):
                    return out_min + (x - in_min) * (out_max - out_min) / (in_max - in_min)

                # interne Messung (grün)
                x1 = _map(t_int, self.graph.xmin, self.graph.xmax, gx, gx + gw)
                y1 = _map(h_int, self.graph.ymin, self.graph.ymax, gy, gy + gh)
                self.p1.pos = (x1 - self.p1.size[0] / 2, y1 - self.p1.size[1] / 2)

                # externe Messung (orange)
                x2 = _map(t_ext, self.graph.xmin, self.graph.xmax, gx, gx + gw)
                y2 = _map(h_ext, self.graph.ymin, self.graph.ymax, gy, gy + gh)
                self.p2.pos = (x2 - self.p2.size[0] / 2, y2 - self.p2.size[1] / 2)

            except Exception as e:
                print("⚠️ Scatter update error:", e)

        # jede Sekunde aktualisieren
        Clock.schedule_interval(_update_from_json, 1.0)
        # ---------------------------------------------------
        # Footer mit Buttons
        # ---------------------------------------------------
        self.footer = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.1),
            pos_hint={"x": 0, "y": 0},
            spacing=10,
            padding=10
        )
        self.btn_pause = Button(text="⏸ Pause", background_color=(0.2, 0.6, 0.2, 1))
        self.btn_close = Button(text="❌ Close", background_color=(0.8, 0.1, 0.1, 1))
        self.footer.add_widget(self.btn_pause)
        self.footer.add_widget(self.btn_close)
        self.add_widget(self.footer)

        # Bindings
        self.paused = False
        self.btn_pause.bind(on_press=self.toggle_pause)
        self.btn_close.bind(on_press=self.close_self)

    # ---------------------------------------------------
    # Öffentliche Methode: Update mit echten Daten
    # ---------------------------------------------------
    def update_values(self, t_int, h_int, t_ext, h_ext):
        """Aktualisiert Punkte und Werte anhand echter Sensordaten."""
        if self.paused:
            return

        # Punkte umrechnen (°C / % → Koordinaten)
        xscale = self.graph.width / (self.graph.xmax - self.graph.xmin)
        yscale = self.graph.height / (self.graph.ymax - self.graph.ymin)
        gx, gy = self.graph.pos

        self.p1.pos = (gx + (t_int - self.graph.xmin) * xscale - 11,
                       gy + (h_int - self.graph.ymin) * yscale - 11)
        self.p2.pos = (gx + (t_ext - self.graph.xmin) * xscale - 11,
                       gy + (h_ext - self.graph.ymin) * yscale - 11)

        # Labels
        self.lbl_t1.text = f"Internal Temp: {t_int:.1f}°C"
        self.lbl_h1.text = f"Internal Hum: {h_int:.1f}%"
        self.lbl_t2.text = f"External Temp: {t_ext:.1f}°C"
        self.lbl_h2.text = f"External Hum: {h_ext:.1f}%"

    # ---------------------------------------------------
    # Steuerlogik
    # ---------------------------------------------------
    def toggle_pause(self, *args):
        self.paused = not self.paused
        self.btn_pause.text = "▶ Resume" if self.paused else "⏸ Pause"
        self.set_led(not self.paused)

    def set_led(self, active=True):
        with self.led_canvas.canvas:
            Color(0, 1, 0, 1) if active else Color(1, 0, 0, 1)
            self.led_circle = Ellipse(pos=(15, 15), size=(20, 20))

    def close_self(self, *args):
        """Schließt nur das ModalView (nicht die App)."""
        from kivy.uix.modalview import ModalView
        parent = self.parent
        while parent:
            if isinstance(parent, ModalView):
                parent.dismiss()
                break
            parent = parent.parent


class ScatterApp(App):
    def build(self):
        return VPDScatterWindow()


if __name__ == "__main__":
    ScatterApp().run()
