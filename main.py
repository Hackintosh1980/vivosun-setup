#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Ultimate – Main App (stable entry + clean first-run)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.utils import platform
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.core.text import LabelBase
import os, io, json, time

from dashboard_gui import create_dashboard
from enlarged_chart_window import EnlargedChartWindow
from dashboard_charts import ChartManager, APP_JSON
from setup_screen import SetupScreen
from vpd_scatter_window_full import VPDScatterWindow
from permission_fix import check_permissions
from settings_screen import SettingsScreen
import config


def register_fonts():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fa_path = os.path.join(base_dir, "assets", "fonts", "fa-solid-900.ttf")
    if os.path.exists(fa_path):
        LabelBase.register(name="FA", fn_regular=fa_path)
        print("✅ Font Awesome global registriert.")
    else:
        print("⚠️ Font fehlt:", fa_path)

# direkt beim Start aufrufen
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


class VivosunApp(App):
    """Hauptklasse für VIVOSUN Ultimate"""

    def build(self):
        print("🌱 Starte VivosunApp …")
        if platform == "android":
            fix_android_ui()

        # Config prüfen
        try:
            cfg = config.load_config()
        except Exception:
            cfg = {}
        first_run = not cfg or not cfg.get("mode")
        print("🆕 First-Run erkannt!" if first_run else "✅ Config vorhanden.")

        # ScreenManager
        self.sm = ScreenManager(transition=FadeTransition())

        # ---------------------------------------------------
        # Erststart → nur Setup anzeigen
        # ---------------------------------------------------
        if first_run:
            self.sm.add_widget(SetupScreen(name="setup"))
            self.sm.current = "setup"

            # Timer nur zur Uhr (kein Header)
            Clock.schedule_interval(self._safe_update_clock, 1)

            if platform == "android":
                Clock.schedule_once(self._show_permission_hint_safe, 1.0)
                Clock.schedule_once(self._kickstart_bridge_first_run, 1.2)

            return self.sm

        # ---------------------------------------------------
        # Normalstart → Dashboard + Setup + Settings
        # ---------------------------------------------------
        dash = DashboardScreen(name="dashboard")
        dash.add_widget(create_dashboard())
        self.sm.add_widget(dash)
        self.sm.add_widget(SetupScreen(name="setup"))
        self.sm.add_widget(SettingsScreen(name="settings"))

        # ChartManager
        self.chart_mgr = ChartManager(dash.children[0])

        # Clock-Events
        Clock.schedule_interval(self._safe_update_clock, 1)
        Clock.schedule_interval(self._safe_update_header, 1.0)

        return self.sm

    # -------------------------------------------------------
    # Permissions-Popup
    # -------------------------------------------------------
    def _show_permission_hint_safe(self, *_):
        try:
            if check_permissions():
                print("✅ Permissions OK")
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
            print("⚠️ Berechtigungs-Popup angezeigt")
        except Exception as e:
            print(f"⚠️ Popup-Fehler: {e}")

    # -------------------------------------------------------
    # Bridge-Start beim First-Run
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
            print(f"📡 Bridge gestartet: {ret}")

            try:
                BleBridgePersistent.setActiveMac(None)
                print("🔍 Vollscan aktiv")
            except Exception as e:
                print(f"⚠️ setActiveMac(None) fehlgeschlagen: {e}")

            if not os.path.exists(APP_JSON) or os.path.getsize(APP_JSON) < 2:
                with io.open(APP_JSON, "w", encoding="utf-8") as f:
                    f.write("[]")
                print(f"🆕 Leere JSON erstellt: {APP_JSON}")

        except Exception as e:
            print(f"💥 Fehler beim First-Run Bridge-Start: {e}")

    # -------------------------------------------------------
    # Sichere Updates (Header + Uhr)
    # -------------------------------------------------------
    def _safe_update_clock(self, *_):
        try:
            dash = self.sm.get_screen("dashboard")
            if not dash.children:
                return
            dash.children[0].ids.header.ids.clocklbl.text = time.strftime("%H:%M:%S")
        except Exception:
            pass

    def _safe_update_header(self, *_):
        try:
            if not hasattr(self, "chart_mgr"):
                return
            dash = self.sm.get_screen("dashboard").children[0]
            header = dash.ids.header

            mac = getattr(self, "current_mac", None)
            if not mac and os.path.exists(APP_JSON):
                with open(APP_JSON, "r") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    mac = data[0].get("address", "--")
            mac = mac or "--"

            bt_active = getattr(self.chart_mgr, "_bridge_started", False)
            icon = "\uf294" if bt_active else "\uf293"
            color = (0.3, 1.0, 0.3, 1) if bt_active else (1.0, 0.4, 0.3, 1)

            header.ids.device_label.text = f"[font=assets/fonts/fa-solid-900.ttf]{icon}[/font] {mac}"
            header.ids.device_label.color = color
        except Exception:
            pass

    # -------------------------------------------------------
    # Buttons
    # -------------------------------------------------------
    def on_scatter_pressed(self):
        from kivy.uix.modalview import ModalView
        popup = ModalView(size_hint=(1, 1), auto_dismiss=False)
        popup.add_widget(VPDScatterWindow())
        popup.open()

    # -------------------------------------------------------
    # Enlarged Charts öffnen
    # -------------------------------------------------------
    def on_enlarged_pressed(self, key):
        """Öffnet die Großansicht eines Charts (Tile-Tap)."""
        try:
            from enlarged_chart_window import EnlargedChartWindow
            if not hasattr(self, "chart_mgr"):
                print("⚠️ Kein ChartManager aktiv.")
                return
            popup = EnlargedChartWindow(self.chart_mgr, start_key=key)
            popup.open()
            print(f"🔍 Enlarged geöffnet für {key}")
        except Exception as e:
            print(f"💥 Enlarged open error: {e}")

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
