# main.py — VIVOSUN Setup (Grid)
# Live-Scanner mit hübschen Tiles, Auswahl speichert nach config.json

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, DictProperty
import os, json, time

from jnius import autoclass, PythonJavaClass, java_method, cast

Window.clearcolor = (0, 0, 0, 1)


# ---------- Android BLE Helpers ----------

BluetoothManager = autoclass("android.bluetooth.BluetoothManager")
BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
BluetoothLeScanner = autoclass("android.bluetooth.le.BluetoothLeScanner")
ScanResult = autoclass("android.bluetooth.le.ScanResult")
PythonActivity = autoclass("org.kivy.android.PythonActivity")

class PyScanCallback(PythonJavaClass):
    __javainterfaces__ = ['android/bluetooth/le/ScanCallback']
    __javacontext__ = 'app'

    def __init__(self, on_result):
        super().__init__()
        self.on_result = on_result

    @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
    def onScanResult(self, callbackType, result):
        try:
            dev = result.getDevice()
            name = dev.getName() or ""
            addr = dev.getAddress() or ""
            rssi = result.getRssi()
            # nur ThermoBeacon / VIVOSUN etc. aber „alles zeigen“ = locker lassen:
            if name == "" or not any(x in name.lower() for x in ['thermo', 'vivo', 'beacon']):
                # trotzdem anzeigen? → Kommentar rausnehmen, wenn ALLES gelistet werden soll
                pass
            self.on_result(addr, name, rssi)
        except Exception:
            pass

    @java_method('(Ljava/util/List;)V')
    def onBatchScanResults(self, results):
        try:
            it = results.iterator()
            while it.hasNext():
                r = cast(ScanResult, it.next())
                self.onScanResult(0, r)
        except Exception:
            pass

    @java_method('(I)V')
    def onScanFailed(self, errorCode):
        # ignorieren; UI zeigt Status separat
        pass


class BleLiveScanner:
    def __init__(self):
        self.ctx = PythonActivity.mActivity
        bm = cast(BluetoothManager, self.ctx.getSystemService(self.ctx.BLUETOOTH_SERVICE))
        self.adapter = bm.getAdapter()
        self.scanner = self.adapter.getBluetoothLeScanner() if self.adapter else None
        self.cb = PyScanCallback(self._on_result)
        self.devices = {}  # addr -> {name, rssi, ts}

    def _on_result(self, addr, name, rssi):
        now = time.time()
        self.devices[addr] = {"name": name or "(unbekannt)", "rssi": int(rssi), "ts": now}

    def start(self):
        if self.scanner:
            try:
                self.scanner.startScan(self.cb)
                return True
            except Exception:
                return False
        return False

    def stop(self):
        if self.scanner:
            try:
                self.scanner.stopScan(self.cb)
            except Exception:
                pass

    def snapshot(self, max_age=8.0):
        # veraltete Einträge entfernen
        now = time.time()
        stale = [a for a, d in self.devices.items() if now - d["ts"] > max_age]
        for a in stale:
            self.devices.pop(a, None)
        # sortiere nach RSSI desc
        items = sorted(self.devices.items(), key=lambda kv: kv[1]["rssi"], reverse=True)
        return items


# ---------- UI ----------

class Header(BoxLayout):
    status = StringProperty("Scan läuft …")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = 'vertical'
        self.padding = dp(12)
        self.spacing = dp(8)
        title = Label(text="[b]VIVOSUN Setup[/b]", markup=True, font_size=dp(28),
                      color=(0,1,0.7,1), size_hint_y=None, height=dp(36))
        subtitle = Label(text=self.status, markup=True, font_size=dp(14),
                         color=(0.6,0.9,1,1), size_hint_y=None, height=dp(22))
        self.subtitle = subtitle
        self.add_widget(title)
        self.add_widget(subtitle)

    def set_status(self, txt):
        self.subtitle.text = txt


class DeviceTile(Button):
    addr = StringProperty("")
    name = StringProperty("")
    rssi = StringProperty("")

    def __init__(self, on_pick, **kw):
        super().__init__(**kw)
        self.on_pick = on_pick
        self.size_hint_y = None
        self.height = dp(88)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0.1, 0.14, 0.16, 1)
        self.color = (1,1,1,1)
        self.markup = True
        self.font_size = dp(16)
        self.padding = dp(12)
        self.halign = 'left'
        self.valign = 'middle'
        self.text = ""
        self.bind(on_release=self._choose)

    def refresh(self):
        self.text = (
            f"[b]{self.name}[/b]\n"
            f"[color=#88ccff]{self.addr}[/color]   "
            f"[color=#99ff99]RSSI {self.rssi} dBm[/color]"
        )

    def _choose(self, *a):
        self.on_pick(self.addr, self.name)


class DeviceGrid(GridLayout):
    def __init__(self, on_pick, **kw):
        super().__init__(**kw)
        self.on_pick = on_pick
        self.cols = 1
        self.spacing = dp(8)
        self.padding = dp(12)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        self.tiles = {}  # addr -> tile

    def update(self, items):
        current = set(self.tiles.keys())
        seen = set(a for a, _ in items)

        # remove gone
        for addr in current - seen:
            tile = self.tiles.pop(addr)
            self.remove_widget(tile)

        # add/update
        for addr, info in items:
            name = info["name"] or "(unbekannt)"
            rssi = info["rssi"]
            if addr not in self.tiles:
                t = DeviceTile(self.on_pick)
                t.addr = addr
                t.name = name
                t.rssi = str(rssi)
                t.refresh()
                self.tiles[addr] = t
                self.add_widget(t)
            else:
                t = self.tiles[addr]
                changed = False
                if t.name != name:
                    t.name = name; changed = True
                if t.rssi != str(rssi):
                    t.rssi = str(rssi); changed = True
                if changed:
                    t.refresh()


# ---------- App ----------

class SetupApp(App):
    devices = DictProperty({})
    CONFIG_NAME = "config.json"

    def build(self):
        root = BoxLayout(orientation='vertical')
        self.header = Header()
        root.add_widget(self.header)

        self.grid = DeviceGrid(self.on_pick)
        scroll = ScrollView(size_hint=(1,1))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)

        self.scanner = BleLiveScanner()

        ok = self.scanner.start()
        self.header.set_status("[color=#aaffaa]Scan gestartet[/color]" if ok else "[color=#ff7777]Scan fehlgeschlagen[/color]")

        Clock.schedule_interval(self.refresh, 1.0)
        return root

    def on_stop(self):
        self.scanner.stop()

    def refresh(self, dt):
        items = self.scanner.snapshot(max_age=8.0)
        self.grid.update(items)
        self.header.set_status(f"[color=#a0d8ff]{len(items)} Gerät(e) gefunden[/color]")

    def on_pick(self, addr, name):
        # Speichern in /data/user/0/<package>/files/config.json (user_data_dir)
        data = {
            "device_address": addr,
            "device_name": name,
            "saved_ts": int(time.time())
        }
        try:
            path = os.path.join(self.user_data_dir, self.CONFIG_NAME)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.header.set_status(f"[color=#99ff99]Gespeichert:[/color] {name} • {addr}")
        except Exception as e:
            self.header.set_status(f"[color=#ff7777]Save-Fehler:[/color] {e}")

if __name__ == "__main__":
    SetupApp().run()
