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
import time

# --- Projektmodule ---
from dashboard_gui import create_dashboard
from dashboard_charts import ChartManager, APP_JSON
from setup_screen import SetupScreen
from kivy.uix.modalview import ModalView
from vpd_scatter_window_full import VPDScatterWindow
from permission_fix import check_permissions
from settings_screen import SettingsScreen
import config

# --- Standard Desktop-Größe (hat auf Android keine Wirkung) ---
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
        # --- Config prüfen ---
        cfg = config.load_config()

        # ScreenManager anlegen
        self.sm = ScreenManager(transition=FadeTransition())

        # --- Wenn keine Config → direkt Setup-Screen ---
        if not cfg or not cfg.get("mode"):
            print("⚠️ Keine Config gefunden → starte Setup-Screen")
            setup = SetupScreen(name="setup")
            self.sm.add_widget(setup)
            return self.sm

        # --- Dashboard-Screen erstellen ---
        dash = DashboardScreen(name="dashboard")
        dash.add_widget(create_dashboard())
        self.sm.add_widget(dash)

        # --- Setup + Settings hinzufügen ---
        setup = SetupScreen(name="setup")
        settings = SettingsScreen(name="settings")
        self.sm.add_widget(setup)
        self.sm.add_widget(settings)

        # --- Chart Manager (nur im Dashboard wirksam)
        self.chart_mgr = ChartManager(dash.children[0])
        print(f"🖥️ Plattform: {platform}")
        print(f"📄 JSON-Pfad (APP_JSON): {APP_JSON}")
        print(f"⚙️ ChartManager running={getattr(self.chart_mgr, 'running', None)}")
        # --- Android: Falls Config vorhanden & Mode=live → Bridge starten ---
        if platform == "android":
            try:
                cfg = config.load_config()
                if cfg.get("mode") == "live" and cfg.get("device_id"):
                    from jnius import autoclass
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    ctx = PythonActivity.mActivity
                    BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                    ret = BleBridgePersistent.start(ctx, "ble_scan.json")
                    print(f"📡 Android Bridge auto-start → {ret}")
            except Exception as e:
                print(f"⚠️ Bridge auto-start Fehler: {e}")
        else:
            print("💻 Desktop-Modus erkannt → keine Bridge gestartet")

        # --- Uhrzeit im Header ---
        Clock.schedule_interval(self.update_clock, 1)

        # --- Android-Specials ---
        if platform == "android":
            Clock.schedule_once(self._android_post_init, 1.0)

        return self.sm
# -------------------------------------------------------
    # Android: Layout-Refresh & Permission-Check
    # -------------------------------------------------------
    def _android_post_init(self, *_):
        """Nach vollständigem Surface-Init ausführen"""
        try:
            print("📱 Android-PostInit gestartet …")

            # Layout-Refresh (behebt zu kleine Fenster beim ersten Start)
            dash = self.sm.get_screen("dashboard").children[0]
            dash.do_layout()
            print("✅ Layout-Refresh abgeschlossen")

            # 👇 Zusätzlicher Refresh-Timer (fix bei Neustart / Resume)
            from kivy.clock import Clock
            Clock.schedule_once(lambda *_: dash.do_layout(), 0.5)
            Clock.schedule_once(lambda *_: dash.do_layout(), 1.0)
            print("🔁 Zweifacher Layout-Refresh geplant")

            # Runtime-Permissions prüfen
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            ContextCompat = autoclass("androidx.core.content.ContextCompat")
            ActivityCompat = autoclass("androidx.core.app.ActivityCompat")

            # Manifest-Strings direkt (Fix für jnius)
            permissions = [
                "android.permission.BLUETOOTH",
                "android.permission.BLUETOOTH_ADMIN",
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.ACCESS_COARSE_LOCATION",
            ]

            for p in permissions:
                granted = ContextCompat.checkSelfPermission(activity, p)
                if granted != 0:
                    print(f"⚠️ Permission fehlt: {p}")
                    ActivityCompat.requestPermissions(activity, permissions, 1)
                else:
                    print(f"✅ Permission OK: {p}")

        except Exception as e:
            print("⚠️ Android-Init-Fehler:", e)


    # -------------------------------------------------------
    # Clock / Header
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
    # Button Actions
    # -------------------------------------------------------
    def on_scatter_pressed(self):
        """Öffnet das Scatter-Fenster als modales Overlay."""
        from kivy.uix.modalview import ModalView
        from vpd_scatter_window_full import VPDScatterWindow

        popup = ModalView(size_hint=(1, 1), auto_dismiss=False)
        popup.add_widget(VPDScatterWindow())
        popup.open()

    def on_setup_pressed(self):
        print("⚙️ Wechsel zum Setup-Screen …")
        self.sm.current = "setup"

    def on_stop_pressed(self, button=None):
        """Start/Stop-Umschaltung für Live-Polling."""
        if not hasattr(self, "chart_mgr"):
            return

        running = getattr(self.chart_mgr, "running", True)

        # --- Android: Bridge-Autostart bei Live-Mode ---
        if platform == "android":
            try:
                cfg = config.load_config()
                if cfg.get("mode") == "live" and cfg.get("device_id"):
                    from jnius import autoclass
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    ctx = PythonActivity.mActivity
                    BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
                    ret = BleBridgePersistent.start(ctx, "ble_scan.json")
                    print(f"📡 Bridge auto-start → {ret}")
            except Exception as e:
                print(f"⚠️ Bridge auto-start failed: {e}")
        if running:
            print("⏹ Live-Polling gestoppt")
            if hasattr(self.chart_mgr, "stop_polling"):
                self.chart_mgr.stop_polling()
            self.chart_mgr.running = False
            if button:
                button.text = "▶️ Start"
                button.background_color = (0.2, 0.6, 0.2, 1)
        else:
            print("▶️ Live-Polling gestartet")
            if hasattr(self.chart_mgr, "start_live_poll"):
                self.chart_mgr.start_live_poll()
            self.chart_mgr.running = True
            if button:
                button.text = "⏹ Stop"
                button.background_color = (0.6, 0.2, 0.2, 1)

    def on_reset_pressed(self):
        print("🔄 Werte zurückgesetzt")
        if hasattr(self.chart_mgr, "reset_data"):
            self.chart_mgr.reset_data()

    def to_settings(self):
        """Wechselt zum Einstellungs-Screen."""
        if self.sm and "settings" in self.sm.screen_names:
            self.sm.current = "settings"


# -------------------------------------------------------
# App Start
# -------------------------------------------------------
if __name__ == "__main__":
    VivosunApp().run()
