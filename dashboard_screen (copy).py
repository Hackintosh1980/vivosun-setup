from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock, mainthread
from jnius import autoclass
import threading, json, os, time, statistics, config


class DashboardScreen(Screen):
    def on_enter(self):
        self.file_path = "/data/user/0/org.hackintosh1980.vivosunreader/files/ble_scan.json"
        self.data_buffer = []
        self.refresh_interval = config.get("refresh_interval", 12.0)
        self.build_ui()

        # Polling starten
        Clock.schedule_interval(self.update_loop, self.refresh_interval)

    # ---------------- UI ----------------
    def build_ui(self):
        self.clear_widgets()
        self.layout = BoxLayout(orientation="vertical", spacing=10, padding=20)

        self.title = Label(
            text="[b][color=#00ffaa]🌿 VIVOSUN Dashboard[/color][/b]",
            markup=True, font_size="30sp"
        )
        self.info = Label(
            text="[color=#aaaaaa]Warte auf Daten...[/color]",
            markup=True, font_size="20sp"
        )
        self.vpd_label = Label(text="", markup=True, font_size="22sp")
        self.led = Label(
            text="[color=#ff3333]● disconnected[/color]",
            markup=True, font_size="20sp"
        )

        self.layout.add_widget(self.title)
        self.layout.add_widget(self.info)
        self.layout.add_widget(self.vpd_label)
        self.layout.add_widget(self.led)

        btn_row = BoxLayout(size_hint_y=0.18, spacing=10)
        btn_row.add_widget(Button(text="← Setup", on_release=lambda *_: self.goto_setup()))
        btn_row.add_widget(Button(text="📈 VPD-Chart", on_release=lambda *_: self.goto_vpd()))
        btn_row.add_widget(Button(text="🔄 Aktualisieren", on_release=lambda *_: self.force_update()))
        self.layout.add_widget(btn_row)

        self.add_widget(self.layout)

    # ---------------- BRIDGE & UPDATE ----------------
    def update_loop(self, *args):
        """Startet BLE-Scan im Hintergrundthread, um UI-Freeze zu vermeiden."""
        threading.Thread(target=self.do_scan, daemon=True).start()

    def do_scan(self):
        """Hintergrundscan + Datenauswertung."""
        try:
            ctx = autoclass("org.kivy.android.PythonActivity").mActivity
            BleBridge = autoclass("org.hackintosh1980.blebridge.BleBridge")
            BleBridge.scan(ctx, 4000, "ble_scan.json")
        except Exception as e:
            print("⚠️ Bridge-Aufruf fehlgeschlagen:", e)
            return

        # Kleine Pause, bis JSON geschrieben ist
        time.sleep(0.3)
        data = self.safe_read_json()
        if data:
            self.process_data(data)
        else:
            self.show_disconnected()

    def safe_read_json(self):
        """Liest JSON-Datei robust mit Retry."""
        for _ in range(3):
            try:
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r") as f:
                        return json.load(f)
            except Exception:
                time.sleep(0.4)
        return None

    # ---------------- DATEN & ANZEIGE ----------------
    def process_data(self, data):
        d = data[0]
        t_int = d.get("temperature_int", 0.0)
        t_ext = d.get("temperature_ext", 0.0)
        h_int = d.get("humidity_int", 0.0)
        h_ext = d.get("humidity_ext", 0.0)
        batt = d.get("battery", "?")
        rssi = d.get("rssi", "?")

        # Werte glätten
        self.data_buffer.append((t_int, t_ext, h_int, h_ext))
        if len(self.data_buffer) > 5:
            self.data_buffer.pop(0)
        avg = lambda i: statistics.mean(v[i] for v in self.data_buffer)
        t_int, t_ext, h_int, h_ext = avg(0), avg(1), avg(2), avg(3)

        # VPD berechnen
        svp = lambda T: 0.6108 * pow(10, (7.5 * T) / (237.3 + T))
        def vpd(T, RH):
            return max(0.0, svp(T) - svp(T) * RH / 100)

        vpd_in = vpd(t_int, h_int)
        vpd_out = vpd(t_ext, h_ext)

        # Anzeige im UI-Thread aktualisieren
        self.update_ui(t_int, t_ext, h_int, h_ext, batt, rssi, vpd_in, vpd_out)

    @mainthread
    def update_ui(self, t_int, t_ext, h_int, h_ext, batt, rssi, vpd_in, vpd_out):
        self.info.text = (
            f"[color=#ff6666][b]Innen {t_int:.1f} °C[/b][/color]   "
            f"[color=#66ccff][b]Außen {t_ext:.1f} °C[/b][/color]\n"
            f"[color=#99ff99]rLF in {h_int:.1f}%[/color]   "
            f"[color=#99ccff]rLF out {h_ext:.1f}%[/color]\n"
            f"[color=#ffff66]🔋 {batt}%[/color]   "
            f"[color=#66aaff]RSSI {rssi} dBm[/color]"
        )
        self.vpd_label.text = (
            f"[color=#ffaa33]VPD in {vpd_in:.2f} kPa[/color]   "
            f"[color=#ff9966]VPD out {vpd_out:.2f} kPa[/color]"
        )
        self.led.text = "[color=#33ff33]● connected[/color]"

    @mainthread
    def show_disconnected(self):
        self.led.text = "[color=#ff3333]● disconnected[/color]"
        self.info.text = "[color=#ff7777]Keine Sensordaten[/color]"

    # ---------------- SCREEN SWITCHES ----------------
    def goto_setup(self, *args):
        Clock.unschedule(self.update_loop)
        self.manager.current = "setup"

    def goto_vpd(self, *args):
        Clock.unschedule(self.update_loop)
        self.manager.current = "vpd"

    def force_update(self, *args):
        self.update_loop()
