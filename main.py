from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from jnius import autoclass
import json, os, time

Window.clearcolor = (0, 0, 0, 1)

class BridgeApp(App):
    def build(self):
        self.label = Label(
            text="[b]VIVOSUN Live-Bridge[/b]\nStarte...",
            markup=True, font_size="28sp", halign="center", valign="middle",
            color=(0, 1, 1, 1)
        )
        self.last_data = None
        self.last_seen = 0
        self.connected = False
        Clock.schedule_once(self.cycle, 1)
        return self.label

    def cycle(self, *args):
        # alle 3 Sekunden: Scan anstoßen
        Clock.schedule_interval(self.poll_bridge, 3)
        # jede Sekunde Anzeige aktualisieren
        Clock.schedule_interval(self.update_display, 1)

    def poll_bridge(self, *args):
        """Startet kurzen BLE-Scan (2 s)"""
        try:
            ctx = autoclass("org.kivy.android.PythonActivity").mActivity
            BleBridge = autoclass("org.hackintosh1980.blebridge.BleBridge")
            BleBridge.scan(ctx, 2000, "ble_scan.json")
            self.connected = True
            self.last_seen = time.time()
        except Exception:
            self.connected = False

    def read_json(self):
        path = "/data/user/0/org.hackintosh1980.vivosunreader/files/ble_scan.json"
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
                if not data:
                    return None
                return data[0]
        except Exception:
            return None

    def update_display(self, *args):
        d = self.read_json()
        if d:
            self.last_data = d
            self.last_seen = time.time()
            self.connected = True
        elif time.time() - self.last_seen > 10:
            self.connected = False

        # Fallback auf letzte bekannte Werte
        if not self.last_data:
            self.label.text = "[color=#ffaa00]Warte auf Sensordaten...[/color]"
            return

        d = self.last_data
        batt_raw = d.get("battery", 0)
        batt = min(100, round(batt_raw * 100 / 255))

        led = "🟢" if self.connected else "🔴"
        time_str = time.strftime("%H:%M:%S")

        self.label.text = (
            f"[b][color=#00ffaa]VIVOSUN Live-Bridge[/color][/b]\n\n"
            f"[color=#aaaaaa]{d.get('name','?')}[/color] [b]{d.get('address','?')}[/b]\n"
            f"[color=#66ccff]RSSI {d.get('rssi','?')} dBm[/color]   "
            f"[color=#888888]{time_str}[/color]\n\n"
            f"[color=#ff6666]Innen {d.get('temperature_int',0):.1f}°C[/color]   "
            f"[color=#66ccff]Aussen {d.get('temperature_ext',0):.1f}°C[/color]\n"
            f"[color=#99ff99]rLF in {d.get('humidity_int',0):.1f}%[/color]   "
            f"[color=#99ccff]rLF out {d.get('humidity_ext',0):.1f}%[/color]\n\n"
            f"{led}  [color=#ffff66]🔋 {batt}%[/color]"
        )

if __name__ == "__main__":
    BridgeApp().run()
