#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SettingsScreen – Neon Style (angepasst, ohne Icon-Buttons unten)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.core.text import LabelBase
import os, config

# 🔤 Font Awesome Solid (nur für Überschrift)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
    print("✅ Font Awesome geladen:", FA_PATH)
else:
    print("⚠️ Font Awesome fehlt:", FA_PATH)


class SettingsScreen(Screen):
    def on_enter(self, *a):
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()
        cfg = config.load_config()

        # 🌿 Scrollbarer Container
        scroll = ScrollView(size_hint=(1, 1))
        root = BoxLayout(
            orientation="vertical",
            spacing=10,
            padding=[15, 15, 15, 15],
            size_hint_y=None
        )
        root.bind(minimum_height=root.setter("height"))

        # 🔹 Titel
        root.add_widget(Label(
            text="[b][color=#00ffaa][font=FA]\uf013[/font]  Einstellungen[/color][/b]",
            markup=True, font_size="26sp",
            size_hint_y=None, height="48dp",
            color=(0.8, 1, 0.9, 1)
        ))

        # Helper für Labels
        def field_label(txt):
            return Label(
                text=f"[color=#aaffaa]{txt}[/color]",
                markup=True,
                size_hint_y=None, height="28dp",
                halign="left", valign="middle"
            )

        # ---------------- Einstellungen ----------------
        root.add_widget(field_label("Betriebsmodus:"))
        self.mode_spinner = Spinner(
            text=cfg.get("mode", "live"), values=["live"],
            size_hint_y=None, height="38dp",
            background_color=(0.1, 0.2, 0.15, 1),
            color=(0.9, 1, 0.9, 1)
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

        # UI-Scale
        root.add_widget(field_label("UI-Skalierung:"))
        scale_val = float(cfg.get("ui_scale", 0.85))
        scale_box = BoxLayout(orientation="horizontal", spacing=10,
                              size_hint_y=None, height="42dp")
        self.scale_slider = Slider(min=0.5, max=1.5, value=scale_val, step=0.05)
        self.scale_label = Label(text=f"{scale_val:.2f}", size_hint_x=None, width=60)
        self.scale_slider.bind(value=lambda _, v: setattr(self.scale_label, "text", f"{v:.2f}"))
        scale_box.add_widget(self.scale_slider)
        scale_box.add_widget(self.scale_label)
        root.add_widget(scale_box)

        # Einheit
        root.add_widget(field_label("Temperatureinheit:"))
        self.unit_spinner = Spinner(
            text=cfg.get("unit", "°C"), values=["°C", "°F"],
            size_hint_y=None, height="38dp",
            background_color=(0.1, 0.2, 0.15, 1),
            color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.unit_spinner)

        # Leaf Offset
        root.add_widget(field_label("Leaf-Offset (°C):"))
        self.leaf_input = TextInput(
            text=str(cfg.get("leaf_offset", 0.0)),
            multiline=False, size_hint_y=None, height="36dp",
            background_color=(0.1, 0.2, 0.15, 1),
            foreground_color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.leaf_input)

        # VPD Offset
        root.add_widget(field_label("VPD-Korrektur (kPa):"))
        self.vpd_input = TextInput(
            text=str(cfg.get("vpd_offset", 0.0)),
            multiline=False, size_hint_y=None, height="36dp",
            background_color=(0.1, 0.2, 0.15, 1),
            foreground_color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.vpd_input)

        # Theme
        root.add_widget(field_label("Theme:"))
        self.theme_spinner = Spinner(
            text=cfg.get("theme", "Dark"), values=["Dark", "Light"],
            size_hint_y=None, height="38dp",
            background_color=(0.1, 0.2, 0.15, 1),
            color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.theme_spinner)

        # ---------------- Buttons ----------------
        btn_row = BoxLayout(size_hint_y=None, height="52dp", spacing=10)
        btn_save = Button(
            text="Speichern",
            font_size="18sp",
            background_normal="", background_color=(0.25, 0.55, 0.25, 1),
            on_release=lambda *_: self.save_settings()
        )
        btn_back = Button(
            text="Zurück",
            font_size="18sp",
            background_normal="", background_color=(0.35, 0.45, 0.55, 1),
            on_release=lambda *_: self.to_setup()
        )
        btn_row.add_widget(btn_save)
        btn_row.add_widget(btn_back)
        root.add_widget(btn_row)

        # Status
        self.status_label = Label(
            text="", markup=True, font_size="15sp",
            size_hint_y=None, height="30dp",
            color=(0.8, 1, 0.8, 1)
        )
        root.add_widget(self.status_label)

        scroll.add_widget(root)
        self.add_widget(scroll)

    # 💾 Speichern
    def save_settings(self):
        try:
            # 1️⃣ Config laden + schreiben
            cfg = config.load_config()
            cfg["mode"] = self.mode_spinner.text
            cfg["refresh_interval"] = round(float(self.poll_slider.value), 2)
            cfg["ui_scale"] = round(float(self.scale_slider.value), 2)
            cfg["unit"] = self.unit_spinner.text
            cfg["leaf_offset"] = float(self.leaf_input.text or 0.0)
            cfg["vpd_offset"] = float(self.vpd_input.text or 0.0)
            cfg["theme"] = self.theme_spinner.text
            config.save_config(cfg)

            self.status_label.text = "[color=#00ffaa]💾 Gespeichert – wird angewendet …[/color]"

            # 2️⃣ Zugriff auf App-Instanz
            from kivy.app import App
            app = App.get_running_app()

            # 3️⃣ ChartManager sofort neu initialisieren
            if hasattr(app, "chart_mgr"):
                app.chart_mgr.reload_config()
                print("♻️ Settings angewendet (ChartManager reload).")

            # 4️⃣ Optional: UI-Scale sofort anwenden
            try:
                import dashboard_gui
                dashboard_gui.UI_SCALE = cfg.get("ui_scale", 1.0)
                print(f"🪄 UI-Scale geändert auf {dashboard_gui.UI_SCALE}")
            except Exception as e:
                print(f"⚠️ UI-Scale Update nicht möglich: {e}")

        except Exception as e:
            self.status_label.text = f"[color=#ff5555]❌ Fehler:[/color] {e}"
    def to_setup(self):
        if self.manager and "setup" in self.manager.screen_names:
            self.manager.current = "setup"
