#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SetupScreen – Geräte-Scan + Konfiguration + Reload
Optisch an Dashboard angepasst
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform
import json, os, time, config
from kivy.core.text import LabelBase
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")

if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
    print("✅ Font Awesome geladen:", FA_PATH)
else:
    print("❌ Font Awesome fehlt:", FA_PATH)
# -------------------------------------------------------------
# Android-sicherer Import
# -------------------------------------------------------------
try:
    from jnius import autoclass
except ModuleNotFoundError:
    autoclass = None
    print("⚠️ jnius deaktiviert – BLE-Bridge läuft nur auf Android.")

# -------------------------------------------------------------
# BLE-JSON Pfad (Android & Desktop)
# -------------------------------------------------------------
if platform == "android":
    APP_JSON = "/data/user/0/org.hackintosh1980.dashboard/files/ble_scan.json"
else:
    APP_JSON = os.path.join(os.path.dirname(__file__), "ble_scan.json")


class SetupScreen(Screen):
    """
    Geräte-Setup – startet dauerhafte BleBridgePersistent,
    listet gefundene Geräte, speichert Auswahl in config.json.
    """

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------
    def on_enter(self, *args):
        self._cancel_evt = False
        self._bridge_started = False
        self.build_ui()
        Clock.schedule_once(self.start_bridge_once, 0.5)

    def on_leave(self, *args):
        """Nur Scan-Loop stoppen, Bridge weiterlaufen lassen."""
        self._cancel_evt = True

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    def build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        # Titelzeile mit FA-Symbol
        self.title = Label(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf013[/font]  [b][color=#00ffaa]Geräte-Setup[/color][/b]",
            font_size="26sp"
        )
        self.status = Label(
            text="[color=#aaaaaa]Initialisiere Bridge…[/color]",
            markup=True,
            font_size="18sp"
        )

        # Scrollbare Geräteliste
        self.list_container = GridLayout(
            cols=1,
            size_hint_y=None,
            spacing=6,
            padding=[0, 4, 0, 12]
        )
        self.list_container.bind(minimum_height=self.list_container.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.list_container)

        # Button-Reihe mit FA Icons
        btn_row = BoxLayout(size_hint=(1, 0.18), spacing=8)

        btn_reload = Button(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf021[/font]  Neu laden",
            font_size="18sp",
            background_normal="",
            background_color=(0.2, 0.4, 0.2, 1),
            on_release=lambda *_: self.load_device_list()
        )

        btn_settings = Button(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf013[/font]  Einstellungen",
            font_size="18sp",
            background_normal="",
            background_color=(0.2, 0.3, 0.5, 1),
            on_release=lambda *_: self.to_settings()
        )

        btn_dashboard = Button(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf015[/font]  Dashboard",
            font_size="18sp",
            background_normal="",
            background_color=(0.25, 0.45, 0.25, 1),
            on_release=lambda *_: self.to_dashboard()
        )

        btn_row.add_widget(btn_reload)
        btn_row.add_widget(btn_settings)
        btn_row.add_widget(btn_dashboard)

        # Layout zusammenbauen
        root.add_widget(self.title)
        root.add_widget(self.status)
        root.add_widget(scroll)
        root.add_widget(btn_row)
        self.add_widget(root)

    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # BLE-Bridge starten
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # BLE-Bridge starten
    # ---------------------------------------------------------
    def start_bridge_once(self, *args):
        """Startet BleBridgePersistent (Android) oder nativen BlueZ-Scan (Desktop)."""
        if self._bridge_started or self._cancel_evt:
            return
        self._bridge_started = True
        try:
            if autoclass and platform == "android":
                ctx = autoclass("org.kivy.android.PythonActivity").mActivity
                BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                ret = BleBridgePersistent.start(ctx, "ble_scan.json")
                print("BleBridgePersistent.start() →", ret)
                self.status.text = "[color=#00ffaa]🌿 Bridge aktiv – Scan läuft dauerhaft[/color]"
            else:
                print("💻 Desktop erkannt – starte nativen BlueZ-Scan via Bleak")
                script_path = os.path.join(os.path.dirname(__file__), "ble_scan_linux.py")
                if not os.path.exists(script_path):
                    self.status.text = f"[color=#ff8888]❌ ble_scan_linux.py fehlt:[/color] {script_path}"
                    return

                try:
                    import subprocess
                    # Starte den nativen BlueZ/Bleak-Scan (schreibt ble_scan.json)
                    subprocess.Popen(["python3", script_path])
                    self.status.text = "[color=#00ffaa]🌿 BlueZ-Scan gestartet – suche Geräte...[/color]"
                except Exception as err:
                    print("⚠️ BlueZ-Scan-Fehler:", err)
                    self.status.text = f"[color=#ff5555]❌ Startfehler:[/color] {err}"

            # Erstes Laden & regelmäßiger Reload
            Clock.schedule_once(self.load_device_list, 3)
            Clock.schedule_interval(self.load_device_list, 10)
        except Exception as e:
            self.status.text = f"[color=#ff5555]❌ Bridge-Startfehler:[/color] {e}"

    # JSON lesen + Liste erzeugen
    # ---------------------------------------------------------
    def load_device_list(self, *args):
        """Liest aktuelle JSON-Datei und zeigt erkannte Geräte."""
        if self._cancel_evt:
            return
        try:
            if not os.path.exists(APP_JSON):
                self.status.text = "[color=#ffaa00]Noch keine JSON-Daten...[/color]"
                return

            with open(APP_JSON, "r") as f:
                data = json.load(f)

            if not data:
                self.status.text = "[color=#ffaa00]Keine Geräte erkannt...[/color]"
                return

            self.list_container.clear_widgets()
            devices = {}

            for d in data:
                name = (d.get("name") or "").strip()
                addr = (d.get("address") or "").strip()
                if not addr:
                    continue
                lname = name.lower()
                if any(x in lname for x in ["thermo", "vivosun", "beacon"]):
                    devices[addr] = name or "ThermoBeacon"

            if not devices:
                self.status.text = "[color=#ffaa00]Noch keine passenden Geräte...[/color]"
                return

            self.status.text = f"[color=#00ffaa]{len(devices)} Gerät(e)[/color] – zum Speichern tippen:"
            for addr, name in sorted(devices.items()):
                btn = Button(
                    text=f"{name}\n[b]{addr}[/b]",
                    markup=True, size_hint_y=None, height="68dp",
                    background_normal="", background_color=(0.15, 0.25, 0.2, 1)
                )
                btn.bind(on_release=lambda _b, a=addr: self.select_device(a))
                self.list_container.add_widget(btn)

        except Exception as e:
            self.status.text = f"[color=#ff8888]Fehler beim Lesen:[/color] {e}"

    # ---------------------------------------------------------
    # Auswahl speichern + Wechsel
    # ---------------------------------------------------------
    def select_device(self, addr):
        """Speichert Device-ID, startet Bridge (falls Android) und wechselt ins Dashboard."""
        try:
            config.save_device_id(addr)
            self.status.text = f"[color=#00ffaa]✅ Gespeichert:[/color] {addr}"

            # --- 🔥 Android: Bridge direkt starten ---
            from kivy.utils import platform
            if platform == "android":
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                ctx = PythonActivity.mActivity
                BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                ret = BleBridgePersistent.start(ctx, "ble_scan.json")
                print(f"📡 Bridge sofort gestartet → {ret}")

                # Dashboard-Charts sofort aktivieren
                from kivy.app import App
                app = App.get_running_app()
                if hasattr(app, "chart_mgr"):
                    app.chart_mgr.start_live_poll()
                    print("✅ Live-Poll nach Gerätespeicherung aktiviert")

            # --- Wechsel ins Dashboard ---
            if self.manager and "dashboard" in self.manager.screen_names:
                Clock.schedule_once(lambda *_: self.to_dashboard(), 0.3)

        except Exception as e:
            self.status.text = f"[color=#ff8888]Fehler beim Speichern:[/color] {e}"
            print(f"⚠️ Fehler in select_device: {e}")


    # ---------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------
    def to_dashboard(self):
        if self.manager and "dashboard" in self.manager.screen_names:
            self.manager.current = "dashboard"

    def to_settings(self):
        if self.manager and "settings" in self.manager.screen_names:
            self.manager.current = "settings"
