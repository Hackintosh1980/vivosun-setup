#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SetupScreen v5.0 – stabile Erstinitialisierung & Geräte-Scan
Android & Desktop-kompatibel
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
from kivy.core.text import LabelBase
import json, os, subprocess, config

# -------------------------------------------------------------
# Font Awesome laden
# -------------------------------------------------------------
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
    print("⚠️ jnius deaktiviert – Android-Bridge deaktiviert.")

# -------------------------------------------------------------
# JSON-Zielpfad bestimmen
# -------------------------------------------------------------
if platform == "android":
    APP_JSON = "/data/user/0/org.hackintosh1980.dashboard/files/ble_scan.json"
else:
    APP_JSON = os.path.join(BASE_DIR, "blebridge_desktop", "ble_scan.json")

print(f"🗂️ Verwende APP_JSON = {APP_JSON}")


# =============================================================
#  CLASS: SetupScreen
# =============================================================
class SetupScreen(Screen):
    """Bridge-Init & Geräteliste (vollautomatisch, stabil bei Erststart)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cancel_evt = False
        self._bridge_started = False

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------
    def on_enter(self, *args):
        self._cancel_evt = False
        self.build_ui()

        # Starte Bridge nach kurzer UI-Initialisierung
        Clock.schedule_once(self.start_bridge, 0.8)

        # Prüfe alle paar Sekunden, bis Geräte vorhanden sind
        Clock.schedule_interval(self.load_device_list, 5)

    def on_leave(self, *args):
        self._cancel_evt = True

    # ---------------------------------------------------------
    # UI-Aufbau
    # ---------------------------------------------------------
    def build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        self.title = Label(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf013[/font] [b][color=#00ffaa]Geräte-Setup[/color][/b]",
            font_size="26sp",
        )
        self.status = Label(
            text="[color=#aaaaaa]Initialisiere Bridge…[/color]",
            markup=True,
            font_size="18sp",
        )

        # Scrollbare Liste
        self.list_container = GridLayout(cols=1, size_hint_y=None, spacing=6, padding=[0, 4, 0, 12])
        self.list_container.bind(minimum_height=self.list_container.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.list_container)

        # Buttons unten
        btn_row = BoxLayout(size_hint=(1, 0.18), spacing=8)
        btn_reload = Button(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf021[/font]  Neu laden",
            font_size="18sp",
            background_normal="",
            background_color=(0.2, 0.4, 0.2, 1),
            on_release=lambda *_: self.load_device_list(force=True),
        )
        btn_dashboard = Button(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf015[/font]  Dashboard",
            font_size="18sp",
            background_normal="",
            background_color=(0.25, 0.45, 0.25, 1),
            on_release=lambda *_: self.to_dashboard(),
        )
        btn_settings = Button(
            markup=True,
            text="[font=assets/fonts/fa-solid-900.ttf]\uf013[/font]  Einstellungen",
            font_size="18sp",
            background_normal="",
            background_color=(0.2, 0.3, 0.5, 1),
            on_release=lambda *_: self.to_settings(),
        )
        btn_row.add_widget(btn_reload)
        btn_row.add_widget(btn_dashboard)
        btn_row.add_widget(btn_settings)

        root.add_widget(self.title)
        root.add_widget(self.status)
        root.add_widget(scroll)
        root.add_widget(btn_row)
        self.add_widget(root)

    # ---------------------------------------------------------
    # Bridge starten (mit Permission-Retry)
    # ---------------------------------------------------------
    def start_bridge(self, *args):
        if self._bridge_started or self._cancel_evt:
            return
        self._bridge_started = True

        try:
            if platform == "android" and autoclass:
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                ctx = PythonActivity.mActivity
                BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")

                def _attempt_start(dt=0):
                    try:
                        ret = BleBridgePersistent.start(ctx, "ble_scan.json")
                        print("📡 Bridge-Start:", ret)
                        if "denied" in str(ret).lower() or "permission" in str(ret).lower():
                            self.status.text = "[color=#ffaa00]Bluetooth-Freigabe nötig – retry…[/color]"
                            Clock.schedule_once(_attempt_start, 2.5)
                        else:
                            self.status.text = "[color=#00ffaa]🌿 Bridge aktiv – suche Geräte…[/color]"
                            print("✅ Bridge läuft, starte Gerätescan")
                            BleBridgePersistent.setActiveMac(None)
                            Clock.schedule_once(self.load_device_list, 2.0)
                    except Exception as e:
                        print("⚠️ Bridge noch blockiert:", e)
                        Clock.schedule_once(_attempt_start, 2.5)

                _attempt_start(0)

            else:
                # Desktop-Modus → keine Bridge, nur JSON nutzen
                print("💻 Desktop erkannt – Bridge deaktiviert, nutze ble_scan.json.")
                if not os.path.exists(APP_JSON):
                    os.makedirs(os.path.dirname(APP_JSON), exist_ok=True)
                    with open(APP_JSON, "w") as f:
                        f.write("[]")
                    print("🆕 Leere JSON erstellt.")
                self.status.text = "[color=#00ffaa]💾 Desktop-Modus aktiv[/color]"
                Clock.schedule_once(self.load_device_list, 1.5)

        except Exception as e:
            print("💥 Fehler beim Start:", e)
            self.status.text = f"[color=#ff5555]❌ Fehler beim Bridge-Start:[/color] {e}"

    # ---------------------------------------------------------
    # Geräte-JSON laden
    # ---------------------------------------------------------
    def load_device_list(self, *args, force=False):
        if self._cancel_evt and not force:
            return

        try:
            if not os.path.exists(APP_JSON):
                self.status.text = "[color=#ffaa00]Warte auf erste Scan-Daten…[/color]"
                return

            with open(APP_JSON, "r") as f:
                raw = f.read().strip()

            if not raw or len(raw) < 3:
                self.status.text = "[color=#ffaa00]Noch keine Geräte erkannt…[/color]"
                return

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self.status.text = "[color=#ffaa00]Scan-Datei unvollständig…[/color]"
                return

            if not isinstance(data, list) or not data:
                self.status.text = "[color=#ffaa00]Suche läuft…[/color]"
                return

            # Liste erstellen
            self.list_container.clear_widgets()
            devices = {}
            for d in data:
                addr = (d.get("address") or d.get("mac") or "").strip()
                name = (d.get("name") or "Unbekannt").strip()
                if addr:
                    devices[addr] = name

            self.status.text = f"[color=#00ffaa]{len(devices)} Gerät(e)[/color] – zum Speichern tippen:"
            for addr, name in sorted(devices.items()):
                btn = Button(
                    text=f"{name}\n[b]{addr}[/b]",
                    markup=True,
                    size_hint_y=None,
                    height="68dp",
                    background_normal="",
                    background_color=(0.15, 0.25, 0.2, 1),
                )
                btn.bind(on_release=lambda _b, a=addr: self.select_device(a))
                self.list_container.add_widget(btn)

        except Exception as e:
            print("⚠️ JSON-Ladefehler:", e)
            self.status.text = f"[color=#ff8888]Fehler:[/color] {e}"

    # ---------------------------------------------------------
    # Gerät speichern
    # ---------------------------------------------------------
    def select_device(self, addr):
        try:
            config.save_device_id(addr)
            self.status.text = f"[color=#00ffaa]✅ Gespeichert:[/color] {addr}"
            print(f"💾 Gerät gespeichert: {addr}")

            if platform == "android" and autoclass:
                BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                BleBridgePersistent.setActiveMac(addr)
                print(f"🎯 Aktive MAC gesetzt: {addr}")

            from kivy.app import App
            app = App.get_running_app()
            if hasattr(app, "chart_mgr"):
                app.chart_mgr.reload_config()

            Clock.schedule_once(lambda *_: self.to_dashboard(), 0.4)

        except Exception as e:
            print("⚠️ Fehler beim Speichern:", e)
            self.status.text = f"[color=#ff5555]Fehler:[/color] {e}"

    # ---------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------
    def to_dashboard(self):
        if self.manager and "dashboard" in self.manager.screen_names:
            self.manager.current = "dashboard"

    def to_settings(self):
        if self.manager and "settings" in self.manager.screen_names:
            self.manager.current = "settings"
