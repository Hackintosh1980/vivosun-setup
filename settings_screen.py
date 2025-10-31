#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SettingsScreen – skalierbare, scrollbar-fähige Konfiguration
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
import config


class SettingsScreen(Screen):
    def on_enter(self, *a):
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()
        cfg = config.load_config()

        # Scrollbarer Container
        scroll = ScrollView(size_hint=(1, 1))
        root = BoxLayout(orientation="vertical", spacing=10, padding=[15, 15, 15, 15],
                         size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        # ---------------- Titel ----------------
        root.add_widget(Label(
            text="[b][color=#00ffaa]⚙️ Einstellungen[/color][/b]",
            markup=True, font_size="24sp",
            size_hint_y=None, height="44dp"
        ))

        # ---------------- Mode ----------------
        root.add_widget(Label(text="Betriebsmodus:", size_hint_y=None, height="28dp"))
        self.mode_spinner = Spinner(
            text=cfg.get("mode", "simulation"),
            values=["simulation", "live"],
            size_hint_y=None, height="38dp"
        )
        root.add_widget(self.mode_spinner)

        # ---------------- Polling ----------------
        root.add_widget(Label(text="Polling-Intervall (Sek.):", size_hint_y=None, height="28dp"))
        poll_val = float(cfg.get("refresh_interval", 4.0))
        poll_box = BoxLayout(orientation="horizontal", spacing=10,
                             size_hint_y=None, height="42dp")
        self.poll_slider = Slider(min=1, max=15, value=poll_val, step=0.5)
        self.poll_value_lbl = Label(text=f"{poll_val:.1f}s", size_hint_x=None, width=60)
        self.poll_slider.bind(value=lambda _, v: setattr(self.poll_value_lbl, "text", f"{v:.1f}s"))
        poll_box.add_widget(self.poll_slider)
        poll_box.add_widget(self.poll_value_lbl)
        root.add_widget(poll_box)

        # ---------------- UI-Scale ----------------
        root.add_widget(Label(text="UI-Skalierung:", size_hint_y=None, height="28dp"))
        scale_val = float(cfg.get("ui_scale", 0.85))
        scale_box = BoxLayout(orientation="horizontal", spacing=10,
                              size_hint_y=None, height="42dp")
        self.scale_slider = Slider(min=0.5, max=1.5, value=scale_val, step=0.05)
        self.scale_label = Label(text=f"{scale_val:.2f}", size_hint_x=None, width=60)
        self.scale_slider.bind(value=lambda _, v: setattr(self.scale_label, "text", f"{v:.2f}"))
        scale_box.add_widget(self.scale_slider)
        scale_box.add_widget(self.scale_label)
        root.add_widget(scale_box)

        # ---------------- Einheit °C / °F ----------------
        root.add_widget(Label(text="Temperatureinheit:", size_hint_y=None, height="28dp"))
        self.unit_spinner = Spinner(
            text=cfg.get("unit", "°C"),
            values=["°C", "°F"],
            size_hint_y=None, height="38dp"
        )
        root.add_widget(self.unit_spinner)

        # ---------------- Leaf-Offset ----------------
        root.add_widget(Label(text="Leaf-Offset (°C):", size_hint_y=None, height="28dp"))
        self.leaf_input = TextInput(
            text=str(cfg.get("leaf_offset", 0.0)),
            multiline=False, size_hint_y=None, height="36dp"
        )
        root.add_widget(self.leaf_input)

        # ---------------- VPD-Offset ----------------
        root.add_widget(Label(text="VPD-Korrektur (kPa):", size_hint_y=None, height="28dp"))
        self.vpd_input = TextInput(
            text=str(cfg.get("vpd_offset", 0.0)),
            multiline=False, size_hint_y=None, height="36dp"
        )
        root.add_widget(self.vpd_input)

        # ---------------- Theme ----------------
        root.add_widget(Label(text="Theme:", size_hint_y=None, height="28dp"))
        self.theme_spinner = Spinner(
            text=cfg.get("theme", "Dark"),
            values=["Dark", "Light"],
            size_hint_y=None, height="38dp"
        )
        root.add_widget(self.theme_spinner)

        # ---------------- Buttons ----------------
        btn_row = BoxLayout(size_hint_y=None, height="50dp", spacing=10)
        btn_save = Button(text="Speichern", on_release=lambda *_: self.save_settings())
        btn_back = Button(text="Zurück", on_release=lambda *_: self.to_setup())
        btn_row.add_widget(btn_save)
        btn_row.add_widget(btn_back)
        root.add_widget(btn_row)

        # ---------------- Status ----------------
        self.status_label = Label(text="", markup=True, font_size="15sp",
                                  size_hint_y=None, height="30dp")
        root.add_widget(self.status_label)

        scroll.add_widget(root)
        self.add_widget(scroll)

    # --------------------------------------------------
    # 💾 Speichern
    # --------------------------------------------------
    def save_settings(self):
        try:
            cfg = config.load_config()
            cfg["mode"] = self.mode_spinner.text
            cfg["refresh_interval"] = round(float(self.poll_slider.value), 2)
            cfg["ui_scale"] = round(float(self.scale_slider.value), 2)
            cfg["unit"] = self.unit_spinner.text
            cfg["leaf_offset"] = float(self.leaf_input.text or 0.0)
            cfg["vpd_offset"] = float(self.vpd_input.text or 0.0)
            cfg["theme"] = self.theme_spinner.text

            config.save_config(cfg)
            self.status_label.text = "[color=#00ffaa]💾 Gespeichert![/color]"

            from dashboard_charts import ChartManager
            Clock.schedule_once(lambda *_: ChartManager.reload_config, 0.1)

        except Exception as e:
            self.status_label.text = f"[color=#ff5555]❌ Fehler:[/color] {e}"

    def to_setup(self):
        if self.manager and "setup" in self.manager.screen_names:
            self.manager.current = "setup"
