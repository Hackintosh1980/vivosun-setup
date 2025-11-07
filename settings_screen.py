#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SettingsScreen – Neon Clean Edition 🌿
Einheitliche Config mit Leaf-Offset-Slider, °C/°F-Toggle,
und einem einzigen Speichern-&-Zurück-Button.
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.properties import BooleanProperty
import os, config

# ---------------------------------------------------------
# Font Awesome laden
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
else:
    print("⚠️ Font Awesome fehlt:", FA_PATH)


class SettingsScreen(Screen):
    fahrenheit_mode = BooleanProperty(False)

    def on_enter(self, *a):
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()
        cfg = config.load_config()
        self.fahrenheit_mode = cfg.get("unit", "°C") == "°F"

        scroll = ScrollView(size_hint=(1, 1))
        root = BoxLayout(orientation="vertical", spacing=10,
                         padding=[15, 15, 15, 15], size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        # Titel
        root.add_widget(Label(
            text="[b][color=#00ffaa][font=FA]\uf013[/font] Einstellungen[/color][/b]",
            markup=True, font_size="26sp",
            size_hint_y=None, height="48dp",
            color=(0.8, 1, 0.9, 1)
        ))

        # Helper
        def field_label(txt):
            return Label(text=f"[color=#aaffaa]{txt}[/color]", markup=True,
                         size_hint_y=None, height="28dp", halign="left", valign="middle")

        # Modus
        root.add_widget(field_label("Betriebsmodus:"))
        self.mode_spinner = Spinner(
            text=cfg.get("mode", "live"), values=["live"],
            size_hint_y=None, height="38dp",
            background_color=(0.1, 0.2, 0.15, 1), color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.mode_spinner)

        # Polling
        root.add_widget(field_label("Polling-Intervall (Sek.):"))
        poll_val = float(cfg.get("refresh_interval", 4.0))
        poll_box = BoxLayout(orientation="horizontal", spacing=10,
                             size_hint_y=None, height="42dp")
        self.poll_slider = Slider(min=1, max=15, value=poll_val, step=0.5)
        self.poll_value_lbl = Label(text=f"{poll_val:.1f}s", size_hint_x=None, width=60)
        self.poll_slider.bind(value=lambda _, v: setattr(self.poll_value_lbl, "text", f"{v:.1f}s"))
        poll_box.add_widget(self.poll_slider)
        poll_box.add_widget(self.poll_value_lbl)
        root.add_widget(poll_box)

        # Einheit °C / °F
        root.add_widget(field_label("Temperatureinheit:"))
        self.unit_btn = Button(
            text="°F aktivieren" if not self.fahrenheit_mode else "°C aktivieren",
            font_size="18sp", size_hint_y=None, height="42dp",
            background_normal="", background_color=(0.25, 0.45, 0.35, 1),
            on_release=self.toggle_unit
        )
        root.add_widget(self.unit_btn)

        # Leaf Offset (°C)
        root.add_widget(field_label("Leaf-Offset (°C):"))
        leaf_val = float(cfg.get("leaf_offset", 0.0))
        leaf_box = BoxLayout(orientation="horizontal", spacing=10,
                             size_hint_y=None, height="42dp")
        self.leaf_slider = Slider(min=-5, max=5, value=leaf_val, step=0.1)
        self.leaf_lbl = Label(text=f"{leaf_val:+.1f}°C", size_hint_x=None, width=70)
        self.leaf_slider.bind(value=lambda _, v: setattr(self.leaf_lbl, "text", f"{v:+.1f}°C"))
        leaf_box.add_widget(self.leaf_slider)
        leaf_box.add_widget(self.leaf_lbl)
        root.add_widget(leaf_box)

        # Theme
        root.add_widget(field_label("Theme:"))
        self.theme_spinner = Spinner(
            text=cfg.get("theme", "Dark"), values=["Dark", "Light"],
            size_hint_y=None, height="38dp",
            background_color=(0.1, 0.2, 0.15, 1), color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.theme_spinner)

# ---------------- Buttons ----------------
        btn_row = BoxLayout(size_hint_y=None, height="52dp", spacing=10)

        btn_save = Button(
            text="[font=FA]\uf0c7[/font]  Speichern & Zurück",
            markup=True, font_size="18sp",
            background_normal="", background_color=(0.25, 0.55, 0.25, 1),
            on_release=lambda *_: self.save_and_exit()
        )

        btn_defaults = Button(
            text="[font=FA]\uf0e2[/font]  Standardwerte",
            markup=True, font_size="18sp",
            background_normal="", background_color=(0.45, 0.35, 0.15, 1),
            on_release=lambda *_: self.restore_defaults()
        )

        btn_row.add_widget(btn_save)
        btn_row.add_widget(btn_defaults)
        root.add_widget(btn_row)

        self.status_label = Label(
            text="", markup=True, font_size="15sp",
            size_hint_y=None, height="30dp",
            color=(0.8, 1, 0.8, 1)
        )
        root.add_widget(self.status_label)

        scroll.add_widget(root)
        self.add_widget(scroll)

    
    # ---------------------------------------------------
    # °C ↔ °F Umschaltung
    # ---------------------------------------------------
    def toggle_unit(self, *_):
        self.fahrenheit_mode = not self.fahrenheit_mode
        self.unit_btn.text = "°C aktivieren" if self.fahrenheit_mode else "°F aktivieren"

    # ---------------------------------------------------
    # 💾 Speichern & Zurück
    # ---------------------------------------------------
    def save_and_exit(self):
        try:
            cfg = config.load_config()
            cfg["mode"] = self.mode_spinner.text
            cfg["refresh_interval"] = round(float(self.poll_slider.value), 2)
            cfg["unit"] = "°F" if self.fahrenheit_mode else "°C"
            cfg["leaf_offset"] = round(float(self.leaf_slider.value), 1)
            cfg["theme"] = self.theme_spinner.text
            config.save_config(cfg)

            # Reload sofort aktivieren
            from kivy.app import App
            app = App.get_running_app()
            if hasattr(app, "chart_mgr"):
                app.chart_mgr.reload_config()

            # zurück ins Dashboard
            if self.manager and "dashboard" in self.manager.screen_names:
                self.manager.current = "dashboard"

            self.status_label.text = "[color=#00ffaa]Gespeichert & zurück ins Dashboard[/color]"
        except Exception as e:
            self.status_label.text = f"[color=#ff5555]Fehler:[/color] {e}"


    def restore_defaults(self):
        import config
        cfg = config.DEFAULTS.copy()
        config.save_config(cfg)
        print("↩️ Standardwerte wiederhergestellt:", cfg)
        self.status_label.text = "[color=#ffaa00]↩️ Standardwerte wiederhergestellt[/color]"

        # 💥 Charts neu laden, damit Änderungen sichtbar sind
        try:
            from kivy.app import App
            app = App.get_running_app()
            if hasattr(app, "chart_mgr"):
                app.chart_mgr.reload_config()
                app.chart_mgr.reset_data()
                print("♻️ ChartManager reset nach Default Restore.")
        except Exception as e:
            print("⚠️ ChartManager-Reset-Fehler:", e)

        # 🔙 zurück ins Dashboard
        self.to_setup()

    def to_setup(self):
        if self.manager and "dashboard" in self.manager.screen_names:
            self.manager.current = "dashboard"
        elif self.manager and "setup" in self.manager.screen_names:
            self.manager.current = "setup"
