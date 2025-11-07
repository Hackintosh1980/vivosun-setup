#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Ultimate – Main App (stable + clean watchdog)
© 2025 Dominik Rosenthal (Hackintosh1980)

• Dashboard + Setup + Settings immer aktiv (kein First-Run)
• HardwareMonitor übernimmt alleinige JSON- und Stream-Kontrolle
• Main kümmert sich nur um UI-Updates, MAC/RSSI-Sync und Navigation
"""

import os, json, time
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.utils import platform

from dashboard_gui import create_dashboard
from dashboard_charts import ChartManager, APP_JSON
from setup_screen import SetupScreen
from settings_screen import SettingsScreen
from vpd_scatter_window_full import VPDScatterWindow
from enlarged_chart_window import EnlargedChartWindow
from permission_fix import check_permissions
from hardware_monitor import HardwareMonitor
import config


# -------------------------------------------------------
# Fonts global registrieren (FA)
# -------------------------------------------------------
def register_fonts():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fa_path = os.path.join(base_dir, "assets", "fonts", "fa-solid-900.ttf")
    if os.path.exists(fa_path):
        LabelBase.register(name="FA", fn_regular=fa_path)
        print("✅ Font Awesome global registriert.")
    else:
        print("⚠️ Font fehlt:", fa_path)

register_fonts()


# -------------------------------------------------------
# Android UI stabilisieren
# -------------------------------------------------------
def fix_android_ui():
    def _stabilize(dt):
        if Window.size[0] <= 1:
            Clock.schedule_once(_stabilize, 0.15)
            return
        Window.softinput_mode = "pan"
        Window.fullscreen = True
        Window.size = Window.size
        print("✅ Android UI stabilisiert")
    Clock.schedule_once(_stabilize, 0.1)


class DashboardScreen(Screen):
    pass


# =======================================================
#                      APP
# =======================================================
class VivosunApp(App):
    """Hauptklasse für VIVOSUN Ultimate"""

    current_mac = None
    last_rssi   = None
    bt_active   = False

    # ---------------------------------------------------
    # Build
    # ---------------------------------------------------
    def build(self):
        print("🌱 Starte VivosunApp …")
        if platform == "android":
            fix_android_ui()

        # ScreenManager + Screens
        self.sm = ScreenManager(transition=FadeTransition())
        dash = DashboardScreen(name="dashboard")
        dash.add_widget(create_dashboard())
        self.sm.add_widget(dash)
        self.sm.add_widget(SetupScreen(name="setup"))
        self.sm.add_widget(SettingsScreen(name="settings"))

        # ChartManager + HardwareMonitor
        self.chart_mgr = ChartManager(dash.children[0])
        self.hw = HardwareMonitor(poll_interval=5.0)

        # JSON einmalig beim Start leeren
        try:
            self.hw.clear_ble_json()
        except Exception as e:
            print(f"⚠️ JSON-Reset beim Start fehlgeschlagen: {e}")

        # Intervalle (UI + HW-Sync)
        Clock.schedule_interval(self._safe_update_clock, 1.0)
        Clock.schedule_interval(self._safe_update_header, 1.0)
        Clock.schedule_interval(self._hardware_watchdog_tick, 2.0)

        # Berechtigungen (Android)
        if platform == "android":
            Clock.schedule_once(self._show_permission_hint_safe, 1.0)

        self.sm.current = "dashboard"
        return self.sm

    # ---------------------------------------------------
    # UI-Updates
    # ---------------------------------------------------
    def _safe_update_clock(self, *_):
        try:
            dash = self.sm.get_screen("dashboard")
            if dash.children:
                dash.children[0].ids.header.ids.clocklbl.text = time.strftime("%H:%M:%S")
        except Exception:
            pass

    def _safe_update_header(self, *_):
        """Aktualisiert Device-Icon/MAC im Header (BT + MAC + RSSI)"""
        try:
            if not hasattr(self, "chart_mgr"):
                return
            dash = self.sm.get_screen("dashboard").children[0]
            header = dash.ids.header

            # MAC-Ermittlung
            mac = getattr(self, "current_mac", None)
            if not mac and os.path.exists(APP_JSON):
                try:
                    with open(APP_JSON, "r") as f:
                        data = json.load(f)
                    if isinstance(data, list) and data:
                        mac = data[0].get("address") or data[0].get("mac")
                except Exception:
                    mac = None
            mac = mac or config.load_config().get("device_id") or "--"

            # BT-Status aus Monitor
            try:
                bt_enabled = self.hw.is_bluetooth_enabled()
            except Exception:
                bt_enabled = False

            bridge_flag = bool(getattr(self.chart_mgr, "_bridge_started", False))
            active_flag = bool(getattr(self.chart_mgr, "running", True))
            self.bt_active = bool(bt_enabled or bridge_flag) and active_flag

            icon = "\uf294" if self.bt_active else "\uf293"
            color = (0.3, 1.0, 0.3, 1) if self.bt_active else (1.0, 0.4, 0.3, 1)
            header.ids.device_label.text = f"[font=assets/fonts/fa-solid-900.ttf]{icon}[/font] {mac}"
            header.ids.device_label.color = color

            # RSSI optional
            if hasattr(header.ids, "rssi_value") and isinstance(self.last_rssi, (int, float)):
                header.ids.rssi_value.text = f"{int(self.last_rssi)} dBm"
        except Exception:
            pass

    # ---------------------------------------------------
    # Hardware-Watchdog (UI-Sync only)
    # ---------------------------------------------------
    def _hardware_watchdog_tick(self, *_):
        """
        UI-Synchronisierung:
        • BT-Status refresh
        • MAC/RSSI aus ChartManager-Cache
        Kein JSON-Clear hier! → Nur im HardwareMonitor.
        """
        try:
            self.bt_active = self.hw.is_bluetooth_enabled()
            cache = getattr(self.chart_mgr, "_header_cache", {})
            if isinstance(cache, dict):
                mac = cache.get("mac")
                rssi = cache.get("rssi")
                if mac:
                    self.current_mac = mac
                if isinstance(rssi, (int, float)):
                    self.last_rssi = rssi
        except Exception as e:
            print(f"⚠️ Hardware-Watchdog-Fehler: {e}")

    # ---------------------------------------------------
    # Permissions-Popup
    # ---------------------------------------------------
    def _show_permission_hint_safe(self, *_):
        try:
            if check_permissions():
                print("✅ Permissions OK")
                return
            msg = (
                "⚠️ Bluetooth- oder Standortrechte fehlen.\n\n"
                "Öffne Android → Einstellungen → App-Berechtigungen → "
                "Bluetooth & Standort aktivieren.\n\n"
                "Danach App neu starten."
            )
            lbl = Label(text=msg, halign="center", valign="middle", text_size=(380, None))
            Popup(
                title="Berechtigungen erforderlich",
                content=lbl,
                size_hint=(0.9, 0.55),
                auto_dismiss=True,
            ).open()
            print("⚠️ Berechtigungs-Popup angezeigt")
        except Exception as e:
            print(f"⚠️ Popup-Fehler: {e}")

    # ---------------------------------------------------
    # Navigation + Buttons
    # ---------------------------------------------------
    def on_scatter_pressed(self):
        from kivy.uix.modalview import ModalView
        popup = ModalView(size_hint=(1, 1), auto_dismiss=False)
        popup.add_widget(VPDScatterWindow())
        popup.open()

    def on_enlarged_pressed(self, key):
        try:
            if not hasattr(self, "chart_mgr"):
                print("⚠️ Kein ChartManager aktiv.")
                return
            EnlargedChartWindow(self.chart_mgr, start_key=key).open()
            print(f"🔍 Enlarged geöffnet für Tile: {key}")
        except Exception as e:
            print(f"💥 Enlarged-Open-Fehler: {e}")

    def on_setup_pressed(self):
        self.sm.current = "setup"

    def to_settings(self):
        if "settings" in self.sm.screen_names:
            self.sm.current = "settings"

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

    def on_stop(self):
        try:
            if hasattr(self, "hw"):
                self.hw.stop()
        except Exception:
            pass


if __name__ == "__main__":
    VivosunApp().run()
