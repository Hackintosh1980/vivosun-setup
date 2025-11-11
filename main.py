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
    chart_mgr = None
    btn_dashboard = None
    btn_enlarged = None
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

       
        # Intervalle (UI + HW-Sync)
        Clock.schedule_interval(self._safe_update_clock, 1.0)
        Clock.schedule_interval(self._safe_update_header, 1.0)

        # Berechtigungen (Android)
        if platform == "android":
            Clock.schedule_once(self._show_permission_hint_safe, 1.0)

        self.sm.current = "dashboard"
        return self.sm

    # ---------------------------------------------------
    # UI-Updates
    # ---------------------------------------------------
    

    def update_startstop_ui(self, running: bool):
        """Synchronisiert Start/Stop-Button-Text + Farbe in allen UIs."""
        btns = [self.btn_dashboard, self.btn_enlarged]
        for b in btns:
            if not b:
                continue
            if running:
                b.text = "[font=FA]\\uf04d[/font] Stop"
                b.background_color = (0.6, 0.2, 0.2, 1)
            else:
                b.text = "[font=FA]\\uf04b[/font] Start"
                b.background_color = (0.2, 0.6, 0.2, 1)


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

            
            bridge_flag = bool(getattr(self.chart_mgr, "_bridge_started", False))
            active_flag = bool(getattr(self.chart_mgr, "running", True))
            self.bt_active = bridge_flag and active_flag

            icon = "\uf294" if self.bt_active else "\uf293"
            color = (0.3, 1.0, 0.3, 1) if self.bt_active else (1.0, 0.4, 0.3, 1)
            header.ids.device_label.text = f"[font=assets/fonts/fa-solid-900.ttf]{icon}[/font] {mac}"
            header.ids.device_label.color = color

            # RSSI optional
            if hasattr(header.ids, "rssi_value") and isinstance(self.last_rssi, (int, float)):
                header.ids.rssi_value.text = f"{int(self.last_rssi)} dBm"
        except Exception:
            pass
# --- Auto-Start bei Erstlauf (MAC sichtbar, aber noch kein Start) ---
        try:
            cfg_path = os.path.join(os.getcwd(), "config.json")
            if mac not in ("--", None) and not os.path.exists(cfg_path):
                cfg = {"device_id": mac, "unit": "°C", "autostart": True}
                with open(cfg_path, "w") as f:
                    json.dump(cfg, f, indent=2)
                self.current_mac = mac
                if hasattr(self, "chart_mgr") and self.chart_mgr:
                    if hasattr(self.chart_mgr, "load_config"):
                        self.chart_mgr.load_config(cfg)
                    if hasattr(self.chart_mgr, "user_start"):
                        self.chart_mgr.user_start()
                    print(f"🚀 Auto-Start ausgelöst für erstes Gerät: {mac}")
        except Exception as e:
            print("⚠️ Auto-Start im Header fehlgeschlagen:", e)
    

    # ---------------------------------------------------
    # Permissions-Popup (auto-dismiss everywhere)
    # ---------------------------------------------------
    def _show_permission_hint_safe(self, *_):
        try:
            if check_permissions():
                print("✅ Permissions OK")
                return

            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.label import Label

            box = BoxLayout(orientation="vertical", spacing=18, padding=[20, 20, 20, 20])

            # ⚠️ Icon + Text
            icon_lbl = Label(
                text="[font=FA]\uf071[/font]",
                markup=True,
                font_name="FA",
                font_size="52sp",
                color=(1, 0.85, 0.3, 1),
                size_hint_y=None,
                height="68dp"
            )

            msg = (
                "[b][color=#ffdd66]Bluetooth / Standort Berechtigung fehlt[/color][/b]\n\n"
                "Bitte öffne:\n"
                "[i]Android → Einstellungen → App-Berechtigungen[/i]\n"
                "und aktiviere [b]Bluetooth[/b] & [b]Standort[/b].\n\n"
                "Danach App neu starten."
            )

            text_lbl = Label(
                text=msg,
                markup=True,
                halign="center",
                valign="middle",
                color=(0.9, 1, 0.9, 1),
                text_size=(380, None)
            )

            box.add_widget(icon_lbl)
            box.add_widget(text_lbl)

            # 🌿 Popup-Design
            popup = Popup(
                title="[b]Berechtigungen erforderlich[/b]",
                title_align="center",
                title_size="20sp",
                title_color=(0.9, 1, 0.9, 1),
                separator_color=(0.3, 0.6, 0.3, 1),
                content=box,
                size_hint=(0.88, 0.55),
                background="atlas://data/images/defaulttheme/button_pressed",
                background_color=(0.05, 0.1, 0.05, 0.95),
                auto_dismiss=True,   # 💚 Klick irgendwo → Popup schließt sich
            )

            popup.open()
            print("⚠️ Permissions-Popup angezeigt (auto-dismiss)")
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
            # ✅ nutzt ChartManager-API, nicht manuell toggeln
            self.chart_mgr.user_stop()
            self.chart_mgr.running = False
            if button:
                button.text = "[font=FA]\uf04b[/font] Start"
                button.background_color = (0.2, 0.6, 0.2, 1)
            print("⏸️ Manuell pausiert – Charts bleiben sichtbar.")
        else:
            self.chart_mgr.user_start()
            self.chart_mgr.running = True
            if button:
                button.text = "[font=FA]\uf04d[/font] Stop"
                button.background_color = (0.6, 0.2, 0.2, 1)
            print("▶️ Manuell fortgesetzt.")

        # 🔄 UI-Sync für Dashboard + Enlarged
        try:
            self.update_startstop_ui(self.chart_mgr.running)
        except Exception as e:
            print("⚠️ UI-Sync-Fehler:", e)
            

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
