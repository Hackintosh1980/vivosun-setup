from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
import json, os, time, statistics, config
from jnius import autoclass

APP_JSON = "/data/user/0/org.hackintosh1980.vivosunreader/files/ble_scan.json"


class DashboardScreen(Screen):
    """Dashboard – zeigt Livewerte aus der BleBridgePersistent und versorgt den Scatter-Screen."""

    def on_enter(self, *a):
        self.file_path = APP_JSON
        self.data_buffer = []
        self._cancel_evt = False
        self.refresh_interval = float(config.get("refresh_interval", 4.0))

        self.build_ui()
        self.status_info("🌿 Starte Dashboard…")
        Clock.schedule_once(self.update_loop, 1)
        self._reader_event = Clock.schedule_interval(self.update_loop, self.refresh_interval)

    def on_leave(self, *a):
        """Nur Loop beenden, Bridge weiterlaufen lassen."""
        self._cancel_evt = True
        if hasattr(self, "_reader_event"):
            Clock.unschedule(self._reader_event)

    # ---------------- UI ----------------
    def build_ui(self):
        self.clear_widgets()
        layout = BoxLayout(orientation="vertical", spacing=15, padding=20)

        self.title = Label(
            text="[b][color=#00ffaa]🌿 VIVOSUN Dashboard[/color][/b]",
            markup=True, font_size="34sp"
        )
        self.info = Label(
            text="[color=#aaaaaa]Warte auf Daten...[/color]",
            markup=True, font_size="28sp"
        )
        self.vpd_label = Label(text="", markup=True, font_size="28sp")
        self.led = Label(
            text="[color=#ff3333]● disconnected[/color]",
            markup=True, font_size="22sp"
        )

        layout.add_widget(self.title)
        layout.add_widget(self.info)
        layout.add_widget(self.vpd_label)
        layout.add_widget(self.led)

        # --- Buttons (mit Delay zum stabilen Screenwechsel)
        btn_row = BoxLayout(size_hint_y=0.17, spacing=10, padding=[0,10])
        self.btn_setup = Button(text="← Setup", font_size="20sp")
        self.btn_vpd = Button(text="📈 VPD-Chart", font_size="20sp")
        self.btn_setup.bind(on_release=self.goto_setup)
        self.btn_vpd.bind(on_release=self.goto_vpd)
        btn_row.add_widget(self.btn_setup)
        btn_row.add_widget(self.btn_vpd)
        layout.add_widget(btn_row)

        self.add_widget(layout)

    # ---------------- LOGIK ----------------
    def update_loop(self, *args):
        if self._cancel_evt:
            return
        data = self.safe_read_json()
        if not data:
            self.status_info("Keine Daten empfangen", warn=True)
            self.led.text = "[color=#ff3333]● disconnected[/color]"
            return

        d = data[0]
        t_int = d.get("temperature_int", 0.0)
        t_ext = d.get("temperature_ext", 0.0)
        h_int = d.get("humidity_int", 0.0)
        h_ext = d.get("humidity_ext", 0.0)
        batt = d.get("battery", "?")
        rssi = d.get("rssi", "?")

        # Glättung über 6 Messungen
        self.data_buffer.append((t_int, t_ext, h_int, h_ext))
        if len(self.data_buffer) > 6:
            self.data_buffer.pop(0)
        avg = lambda i: statistics.mean(v[i] for v in self.data_buffer)
        t_int, t_ext, h_int, h_ext = avg(0), avg(1), avg(2), avg(3)

        # VPD berechnen
        def vpd(temp, rh):
            svp = 0.6108 * pow(10, (7.5 * temp) / (237.3 + temp))
            avp = svp * rh / 100
            return max(0.0, svp - avp)

        vpd_in = vpd(t_int, h_int)
        vpd_out = vpd(t_ext, h_ext)

        # Anzeige
        self.info.text = (
            f"[color=#ff6666][b]Temp In:[/b] {t_int:.1f} °C[/color]   "
            f"[color=#66ccff][b]Temp Ext:[/b] {t_ext:.1f} °C[/color]\n"
            f"[color=#99ff99][b]HUM In:[/b] {h_int:.1f}%[/color]   "
            f"[color=#99ccff][b]HUM Ext:[/b] {h_ext:.1f}%[/color]"
        )
        self.vpd_label.text = (
            f"[color=#ffaa33][b]VPD In:[/b] {vpd_in:.2f} kPa[/color]   "
            f"[color=#ff9966][b]VPD Ext:[/b] {vpd_out:.2f} kPa[/color]\n"
            f"[size=20sp][color=#ffff66] S {batt}%[/color]   "
            f"[color=#66aaff]RSSI {rssi} dBm[/color][/size]"
        )
        self.led.text = "[color=#33ff33]● connected[/color]"

        # --- Live an VPD-Scatter weitergeben ---
        if self.manager and "vpd" in self.manager.screen_names:
            try:
                vpd_screen = self.manager.get_screen("vpd")
                vpd_screen.update_points(vpd_in, vpd_out)
            except Exception as e:
                print("⚠️ Scatter update error:", e)

    # ---------------- HELFER ----------------
    def safe_read_json(self):
        for _ in range(3):
            try:
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r") as f:
                        return json.load(f)
            except Exception:
                time.sleep(0.2)
        return None

    def status_info(self, text, warn=False):
        color = "#ff5555" if warn else "#aaaaaa"
        self.info.text = f"[color={color}]{text}[/color]"

    def goto_setup(self, *args):
        self._cancel_evt = True
        Clock.schedule_once(lambda *_: setattr(self.manager, "current", "setup"), 0.05)

    def goto_vpd(self, *args):
        self._cancel_evt = True
        Clock.schedule_once(lambda *_: setattr(self.manager, "current", "vpd"), 0.05)
