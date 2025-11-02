#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Ultimate – Main App mit BLE-Setup, Dashboard & Live Charts
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

# --- Kivy Core Imports ---
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.utils import platform

# --- Python Standard ---
import time, os

# --- Projektmodule ---
from dashboard_gui import create_dashboard
from dashboard_charts import ChartManager, APP_JSON
from setup_screen import SetupScreen
from vpd_scatter_window_full import VPDScatterWindow
from permission_fix import check_permissions
from settings_screen import SettingsScreen
import config

# --- Standard Desktop-Größe (nur für Tests) ---
Window.size = (1200, 700)


class DashboardScreen(Screen):
    """Haupt-Dashboard-Screen."""
    pass


class VivosunApp(App):
    """Hauptklasse für VIVOSUN Ultimate."""

    def build(self):
        print("🌱 Starte VivosunApp …")
        print("🔍 Starte Berechtigungs- und Bluetooth-Check …")
        check_permissions()

        # --- Android: Fullscreen Fix ---
        if platform == "android":
            try:
                Window.fullscreen = True
                Window.softinput_mode = "pan"
                Clock.schedule_once(lambda dt: setattr(Window, "fullscreen", True), 0.3)
                print("✅ Android-Fullscreen aktiv")
            except Exception as e:
                print(f"⚠️ Fullscreen-Init-Fehler: {e}")

        # --- Config laden ---
        try:
            cfg = config.load_config()
            print(f"⚙️ Config geladen: {cfg}" if cfg else "⚠️ Keine config.json gefunden.")
        except Exception as e:
            cfg = {}
            print(f"⚠️ Fehler beim Laden der Config: {e}")

        # --- ScreenManager ---
        self.sm = ScreenManager(transition=FadeTransition())

        # --- Setup-Screen, falls keine Config ---
        if not cfg or not cfg.get("mode"):
            print("⚠️ Keine Config → starte Setup-Screen")
            setup = SetupScreen(name="setup")
            self.sm.add_widget(setup)
            return self.sm

        # --- Dashboard ---
        dash = DashboardScreen(name="dashboard")
        dash.add_widget(create_dashboard())
        self.sm.add_widget(dash)

        # --- Setup + Settings hinzufügen ---
        setup = SetupScreen(name="setup")
        settings = SettingsScreen(name="settings")
        self.sm.add_widget(setup)
        self.sm.add_widget(settings)

        # --- BLE-Bridge immer starten (Android only) ---
        if platform == "android":
            try:
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                ctx = PythonActivity.mActivity
                BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                ret = BleBridgePersistent.start(ctx, "ble_scan.json")
                print(f"📡 Android Bridge gestartet → {ret}")

                # Device-MAC optional setzen
                try:
                    if cfg.get("device_id"):
                        BleBridgePersistent.setActiveMac(cfg.get("device_id"))
                        print(f"🎯 Aktive MAC gesetzt: {cfg.get('device_id')}")
                except Exception as e:
                    print(f"⚠️ Fehler beim Setzen der aktiven MAC: {e}")

            except Exception as e:
                print(f"💥 Fehler beim Android-Bridge-Start: {e}")
        else:
            print("💻 Desktop erkannt – kein Android-Bridge-Start.")

        # --- ChartManager ---
        self.chart_mgr = ChartManager(dash.children[0])
        print(f"🖥️ Plattform: {platform}")
        print(f"📄 JSON-Pfad: {APP_JSON}")
        print(f"⚙️ ChartManager running={getattr(self.chart_mgr, 'running', None)}")

        # --- Uhrzeit im Header ---
        Clock.schedule_interval(self.update_clock, 1)

        # --- Android-PostInit ---
        if platform == "android":
            Clock.schedule_once(self._android_post_init, 1.0)

        return self.sm

    # -------------------------------------------------------
    def on_stop(self):
        """Desktop: Bridge beenden"""
        if platform != "android":
            try:
                setup = self.sm.get_screen("setup")
                if hasattr(setup, "bridge_proc") and setup.bridge_proc:
                    print("🛑 Beende Desktop-BLE-Bridge …")
                    setup.bridge_proc.terminate()
                    time.sleep(1)
                    setup.bridge_proc.kill()
                    print("✅ Bridge beendet")
            except Exception as e:
                print(f"⚠️ Fehler beim Bridge-Stop: {e}")

    # -------------------------------------------------------
    def _android_post_init(self, *_):
        """UI-Refresh & Permission-Check"""
        try:
            print("📱 Android-PostInit gestartet …")

            # --- Dashboard-Layout neu zeichnen ---
            try:
                dash = self.sm.get_screen("dashboard").children[0]
                dash.do_layout()
                Clock.schedule_once(lambda *_: dash.do_layout(), 0.4)
                Clock.schedule_once(lambda *_: dash.do_layout(), 0.8)
                Clock.schedule_once(lambda *_: dash.do_layout(), 2.0)
                print("✅ Layout-Refresh abgeschlossen")
            except Exception as e:
                print(f"⚠️ Dashboard-Layout nicht verfügbar: {e}")

            # --- Runtime-Permissions prüfen ---
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            ContextCompat = autoclass("androidx.core.content.ContextCompat")
            ActivityCompat = autoclass("androidx.core.app.ActivityCompat")

            permissions = [
                "android.permission.BLUETOOTH",
                "android.permission.BLUETOOTH_ADMIN",
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.ACCESS_COARSE_LOCATION",
            ]

            for p in permissions:
                granted = ContextCompat.checkSelfPermission(activity, p)
                if granted != 0:
                    ActivityCompat.requestPermissions(activity, permissions, 1)
                    print(f"⚠️ Permission angefordert: {p}")
                else:
                    print(f"✅ Permission OK: {p}")

            # --- Fenstergröße hart refreshen ---
            from kivy.core.window import Window
            Window.fullscreen = True
            Window.size = Window.size
            Clock.schedule_once(lambda dt: setattr(Window, "fullscreen", True), 1.0)
            print("✅ UI vollständig initialisiert & Hard-Fullscreen gesetzt")

        except Exception as e:
            print(f"⚠️ Android-Init-Fehler: {e}")

# -------------------------------------------------------
    # -------------------------------------------------------
    def update_clock(self, *_):
        now = time.strftime("%H:%M:%S")
        try:
            dash = self.sm.get_screen("dashboard").children[0]
            header = dash.ids.header
            header.ids.clocklbl.text = now
        except Exception:
            pass

    # -------------------------------------------------------
    def on_scatter_pressed(self):
        """Scatter-Overlay öffnen"""
        from kivy.uix.modalview import ModalView
        popup = ModalView(size_hint=(1, 1), auto_dismiss=False)
        popup.add_widget(VPDScatterWindow())
        popup.open()

    def on_setup_pressed(self):
        self.sm.current = "setup"

    def on_stop_pressed(self, button=None):
        """Start/Stop Polling"""
        if not hasattr(self, "chart_mgr"):
            return

        running = getattr(self.chart_mgr, "running", True)
        if running:
            self.chart_mgr.stop_polling()
            self.chart_mgr.running = False
            if button:
                button.text = "▶️ Start"
        else:
            self.chart_mgr.start_live_poll()
            self.chart_mgr.running = True
            if button:
                button.text = "⏹ Stop"

    def on_reset_pressed(self):
        if hasattr(self.chart_mgr, "reset_data"):
            self.chart_mgr.reset_data()

    def to_settings(self):
        if self.sm and "settings" in self.sm.screen_names:
            self.sm.current = "settings"


# -------------------------------------------------------
# App Start
# -------------------------------------------------------
if __name__ == "__main__":
    VivosunApp().run()
