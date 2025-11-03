#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Ultimate – Main App (First-Run Permission Popup, stabiler UI-Fix)
+ Stabiler MAC-Anzeige-Fix (Android/Desktop)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.utils import platform
from kivy.uix.popup import Popup
from kivy.uix.label import Label
import time, os, io, json

from dashboard_gui import create_dashboard
from dashboard_charts import ChartManager, APP_JSON
from setup_screen import SetupScreen
from vpd_scatter_window_full import VPDScatterWindow
from permission_fix import check_permissions
from settings_screen import SettingsScreen
import config


# -------------------------------------------------------
# Android-UI-Fix
# -------------------------------------------------------
def fix_android_ui():
    def _stabilize(dt):
        if Window.size[0] <= 1:
            Clock.schedule_once(_stabilize, 0.15)
            return
        Window.softinput_mode = "pan"
        Window.fullscreen = True
        Window.size = Window.size
        print("✅ Android-UI stabilisiert (Fullscreen + Softinput)")
    Clock.schedule_once(_stabilize, 0.1)


class DashboardScreen(Screen):
    pass


class VivosunApp(App):
    """Hauptklasse für VIVOSUN Ultimate"""

    def build(self):
        print("🌱 Starte VivosunApp …")
        if platform == "android":
            fix_android_ui()

        # ---------------------------------------------------
        # Config laden / First-Run erkennen
        # ---------------------------------------------------
        try:
            cfg = config.load_config()
        except Exception:
            cfg = {}
        first_run = not cfg or not cfg.get("mode")
        print("🆕 First-Run erkannt!" if first_run else "✅ Config vorhanden.")

        self.sm = ScreenManager(transition=FadeTransition())

        # ---------------------------------------------------
        # Erststart → Setup Screen
        # ---------------------------------------------------
        if first_run:
            self.sm.add_widget(SetupScreen(name="setup"))
            self.sm.current = "setup"
            Clock.schedule_interval(self.update_clock, 1)

            if platform == "android":
                Clock.schedule_once(self._show_permission_hint_safe, 1.0)
                Clock.schedule_once(self._kickstart_bridge_first_run, 1.2)

            return self.sm

        # ---------------------------------------------------
        # Normale Initialisierung
        # ---------------------------------------------------
        dash = DashboardScreen(name="dashboard")
        dash.add_widget(create_dashboard())
        self.sm.add_widget(dash)
        self.sm.add_widget(SetupScreen(name="setup"))
        self.sm.add_widget(SettingsScreen(name="settings"))

        self.chart_mgr = ChartManager(dash.children[0])
        Clock.schedule_interval(self.update_clock, 1)
        Clock.schedule_interval(self.update_header, 1.0)

        if platform == "android":
            fix_android_ui()

        return self.sm

    # -------------------------------------------------------
    # Popup bei fehlenden Berechtigungen
    # -------------------------------------------------------
    def _show_permission_hint_safe(self, *_):
        if check_permissions():
            print("✅ Permissions OK – kein Popup.")
            return

        msg = (
            "⚠️ Bluetooth- oder Standortrechte fehlen.\n\n"
            "Bitte öffne Android-Einstellungen → App-Berechtigungen → "
            "Bluetooth & Standort aktivieren.\n\n"
            "Danach App neu starten, um Geräte zu finden."
        )
        lbl = Label(text=msg, halign="center", valign="middle", text_size=(380, None))
        popup = Popup(
            title="Berechtigungen erforderlich",
            content=lbl,
            size_hint=(0.9, 0.55),
            auto_dismiss=True,
        )
        popup.open()
        print("⚠️ Erststart-Popup angezeigt – User muss Rechte manuell setzen.")

    # -------------------------------------------------------
    # Bridge-Autostart beim First-Run
    # -------------------------------------------------------
    def _kickstart_bridge_first_run(self, *_):
        if platform != "android":
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ctx = PythonActivity.mActivity
            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
            ret = BleBridgePersistent.start(ctx, "ble_scan.json")
            print(f"📡 Bridge gestartet → {ret}")

            try:
                BleBridgePersistent.setActiveMac(None)
                print("🔍 Vollscan aktiv (keine MAC-Filterung)")
            except Exception as e:
                print(f"⚠️ setActiveMac(None) fehlgeschlagen: {e}")

            if not os.path.exists(APP_JSON) or os.path.getsize(APP_JSON) < 2:
                with io.open(APP_JSON, "w", encoding="utf-8") as f:
                    f.write("[]")
                print(f"🆕 Leere JSON angelegt: {APP_JSON}")

        except Exception as e:
            print(f"💥 Fehler beim First-Run Bridge-Start: {e}")

    # -------------------------------------------------------
    # Uhr & Header (inkl. MAC-Anzeige-Fix)
    # -------------------------------------------------------
    def update_clock(self, *_):
        now = time.strftime("%H:%M:%S")
        try:
            dash = self.sm.get_screen("dashboard").children[0]
            dash.ids.header.ids.clocklbl.text = now
        except Exception:
            pass

    def update_header(self, *_):
        """Aktualisiert Bluetooth-Status + MAC-Adresse stabil"""
        try:
            dash = self.sm.get_screen("dashboard").children[0]
            header = dash.ids.header

            # Aktuelle MAC aus ChartManager oder JSON holen
            mac = getattr(self, "current_mac", None)
            if not mac:
                try:
                    if os.path.exists(APP_JSON):
                        with open(APP_JSON, "r") as f:
                            data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            mac = data[0].get("address") or "--"
                except Exception:
                    mac = "--"

            # Fallback aus Config
            if not mac or mac == "--":
                cfg = getattr(self.chart_mgr, "cfg", {}) or {}
                mac = cfg.get("device_id") or "--"

            bt_active = getattr(self.chart_mgr, "_bridge_started", False)
            icon = "\uf294" if bt_active else "\uf293"  # fa-bluetooth vs fa-bluetooth-b
            color = (0.2, 1.0, 0.3, 1) if bt_active else (1.0, 0.4, 0.3, 1)

            header.ids.device_label.text = (
                f"[font=assets/fonts/fa-solid-900.ttf]{icon}[/font] {mac}"
            )
            header.ids.device_label.color = color

        except Exception as e:
            print(f"⚠️ update_header Fehler: {e}")

    # -------------------------------------------------------
    # Buttons
    # -------------------------------------------------------
    def on_scatter_pressed(self):
        from kivy.uix.modalview import ModalView
        popup = ModalView(size_hint=(1, 1), auto_dismiss=False)
        popup.add_widget(VPDScatterWindow())
        popup.open()

    def on_setup_pressed(self):
        self.sm.current = "setup"

    def on_stop_pressed(self, button=None):
        if not hasattr(self, "chart_mgr"):
            return
        running = getattr(self.chart_mgr, "running", True)
        if running:
            self.chart_mgr.stop_polling()
            self.chart_mgr.running = False
            if button:
                button.text = "[font=assets/fonts/fa-solid-900.ttf]\uf04b[/font] Start"
                button.background_color = (0.2, 0.6, 0.2, 1)
        else:
            self.chart_mgr.start_polling()
            self.chart_mgr.running = True
            if button:
                button.text = "[font=assets/fonts/fa-solid-900.ttf]\uf04d[/font] Stop"
                button.background_color = (0.6, 0.2, 0.2, 1)

    def on_reset_pressed(self):
        if hasattr(self, "chart_mgr"):
            self.chart_mgr.reset_data()

    def to_settings(self):
        if "settings" in self.sm.screen_names:
            self.sm.current = "settings"


if __name__ == "__main__":
    VivosunApp().run()
