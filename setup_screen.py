#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SetupScreen v6.1 – Neon Style Edition ✨ (UI-Scaling ready)
Optisch 100 % abgestimmt auf Dashboard v3.6
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
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
import json, os, config


# -------------------------------------------------------
# 🌿 Globales UI-Scaling
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.72
else:
    UI_SCALE = 1.0

def sp_scaled(v): 
    return f"{int(v * UI_SCALE)}sp"

def dp_scaled(v): 
    return dp(v * UI_SCALE)


# -------------------------------------------------------------
# Font Awesome laden
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    LabelBase.register(name="FA", fn_regular=FA_PATH)
else:
    print("⚠️ Font Awesome fehlt:", FA_PATH)


# -------------------------------------------------------------
# Android-Import
# -------------------------------------------------------------
try:
    from jnius import autoclass
except ModuleNotFoundError:
    autoclass = None


# -------------------------------------------------------------
# JSON-Pfad
# -------------------------------------------------------------
if platform == "android":
    APP_JSON = "/data/user/0/org.hackintosh1980.dashboard/files/ble_scan.json"
else:
    APP_JSON = os.path.join(BASE_DIR, "blebridge_desktop", "ble_scan.json")


# =============================================================
# SetupScreen
# =============================================================
class SetupScreen(Screen):
    """Geräte-Setup im Neon-Dashboard-Style (skalierbar)"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cancel_evt = False
        self._bridge_started = False

    def on_enter(self, *args):
        self._cancel_evt = False
        self.build_ui()
        Clock.schedule_once(self.start_bridge, 0.8)
        Clock.schedule_interval(self.load_device_list, 5)

    def on_leave(self, *args):
        self._cancel_evt = True


    # ---------------------------------------------------------
    # UI-Aufbau mit Scaling
    # ---------------------------------------------------------
    def build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical",
                         spacing=dp_scaled(10),
                         padding=dp_scaled(12))
        with root.canvas.before:
            Color(0.02, 0.05, 0.03, 1)
            self.bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=lambda *_: setattr(self.bg, "size", root.size))
        root.bind(pos=lambda *_: setattr(self.bg, "pos", root.pos))

        # Header
        self.title = Label(
            markup=True,
            text="[b][font=FA]\uf013[/font]  [color=#00ffaa]Geräte-Setup[/color][/b]",
            font_size=sp_scaled(26),
            size_hint_y=None,
            height=dp_scaled(50),
            color=(0.9, 1, 0.9, 1)
        )
        root.add_widget(self.title)

        # Status
        self.status = Label(
            markup=True,
            text="[color=#aaaaaa]Initialisiere Bridge…[/color]",
            font_size=sp_scaled(18),
            size_hint_y=None,
            height=dp_scaled(30),
        )
        root.add_widget(self.status)

        # Scrollbare Geräteliste
        self.list_container = GridLayout(cols=1, size_hint_y=None,
                                         spacing=dp_scaled(6),
                                         padding=[0, dp_scaled(6), 0, dp_scaled(10)])
        self.list_container.bind(minimum_height=self.list_container.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.list_container)
        root.add_widget(scroll)

        # Buttons unten
        btn_row = BoxLayout(size_hint_y=None, height=dp_scaled(56), spacing=dp_scaled(8))

        def neon_btn(icon, text, color, cb):
            return Button(
                markup=True,
                text=f"[font=FA]{icon}[/font]  {text}",
                font_size=sp_scaled(16),
                background_normal="",
                background_color=color,
                on_release=lambda *_: cb(),
            )

        btn_reload = neon_btn("\uf021", "Neu laden", (0.2, 0.6, 0.3, 1),
                              lambda: self.load_device_list(force=True))
        btn_settings = neon_btn("\uf013", "Einstellungen", (0.3, 0.4, 0.6, 1),
                                self.to_settings)
        btn_dashboard = neon_btn("\uf015", "Dashboard", (0.25, 0.45, 0.25, 1),
                                 self.to_dashboard)

        btn_row.add_widget(btn_reload)
        btn_row.add_widget(btn_settings)
        btn_row.add_widget(btn_dashboard)
        root.add_widget(btn_row)

        self.add_widget(root)


    # ---------------------------------------------------------
    # Bridge starten
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
                        if "denied" in str(ret).lower():
                            self.status.text = "[color=#ffaa00]Bluetooth-Freigabe nötig…[/color]"
                            Clock.schedule_once(_attempt_start, 3.0)
                        else:
                            self.status.text = "[color=#00ffaa]🌿 Bridge aktiv – suche Geräte…[/color]"
                            BleBridgePersistent.setActiveMac(None)
                            Clock.schedule_once(self.load_device_list, 2.0)
                    except Exception as e:
                        print("⚠️ Bridge-Start fehlgeschlagen:", e)
                        Clock.schedule_once(_attempt_start, 3.0)

                _attempt_start(0)
            else:
                print("💻 Desktop-Modus aktiv.")
                if not os.path.exists(APP_JSON):
                    os.makedirs(os.path.dirname(APP_JSON), exist_ok=True)
                    with open(APP_JSON, "w") as f:
                        f.write("[]")
                self.status.text = "[color=#00ffaa]💾 Desktop-Modus aktiv[/color]"
                Clock.schedule_once(self.load_device_list, 1.5)

        except Exception as e:
            self.status.text = f"[color=#ff5555]❌ Fehler beim Bridge-Start:[/color] {e}"


   # ---------------------------------------------------------
    # Geräte laden + JSON-Leeren bei "Neu laden"
    # ---------------------------------------------------------
    def load_device_list(self, *args, force=False):
        """
        Lädt Geräteliste aus ble_scan.json.
        Wenn force=True (Neu laden-Button), wird die Datei zuerst geleert.
        """
        if self._cancel_evt and not force:
            return
        try:
            # Wenn der Benutzer aktiv "Neu laden" drückt → Datei leeren
            if force:
                try:
                    if os.path.exists(APP_JSON):
                        with open(APP_JSON, "w") as f:
                            f.write("[]")
                        print(f"🧹 {APP_JSON} geleert.")
                        self.status.text = "[color=#ffaa00]Scan-Datei geleert – Bridge schreibt neu…[/color]"
                        # Bridge reaktivieren (Android)
                        if platform == "android" and autoclass:
                            PythonActivity = autoclass("org.kivy.android.PythonActivity")
                            ctx = PythonActivity.mActivity
                            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                            BleBridgePersistent.setActiveMac(None)
                            BleBridgePersistent.start(ctx, "ble_scan.json")
                            print("🔁 Bridge-Neustart nach Reset.")
                        else:
                            # Desktop: einfach neu einlesen
                            print("💻 Desktop-Datei wird neu erstellt.")
                    else:
                        os.makedirs(os.path.dirname(APP_JSON), exist_ok=True)
                        with open(APP_JSON, "w") as f:
                            f.write("[]")
                        print(f"🆕 Neue Scan-Datei erstellt: {APP_JSON}")
                except Exception as e:
                    print("⚠️ Fehler beim Leeren:", e)

            # Danach Liste ganz normal neu laden
            if not os.path.exists(APP_JSON):
                self.status.text = "[color=#ffaa00]Noch keine Bridge-Daten…[/color]"
                return

            with open(APP_JSON, "r") as f:
                raw = f.read().strip()
            if not raw:
                self.status.text = "[color=#ffaa00]Warte auf Scan-Daten…[/color]"
                return

            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                self.status.text = "[color=#ffaa00]Suche läuft…[/color]"
                return

            # Geräteliste neu zeichnen
            self.list_container.clear_widgets()
            devices = {d.get("address", ""): d.get("name", "Unbekannt")
                       for d in data if d.get("address")}
            self.status.text = f"[color=#00ffaa]{len(devices)} Gerät(e) gefunden[/color]"

            for addr, name in devices.items():
                btn = Button(
                    text=f"[b]{name}[/b]\n{addr}",
                    markup=True,
                    size_hint_y=None,
                    height=dp_scaled(64),
                    font_size=sp_scaled(15),
                    background_normal="",
                    background_color=(0.1, 0.2, 0.15, 1),
                )
                btn.bind(on_release=lambda _b, a=addr: self.select_device(a))
                self.list_container.add_widget(btn)

        except Exception as e:
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
            if hasattr(app, "chart_mgr") and hasattr(app.chart_mgr, "reload_config"):
                app.chart_mgr.reload_config()
            else:
                print("ℹ️ ChartManager noch nicht aktiv – kein reload nötig.")

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
