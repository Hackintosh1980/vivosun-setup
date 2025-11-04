#!/usr/bin/env python3
# ble_gui_mac_dump.py — macOS BLE Scanner & Analyzer mit Kivy GUI
#
# - scannt per CoreBluetooth (pyobjc)
# - zeigt Geräte mit Name, RSSI, Typ, Temp/Feuchte (ThermoBeacon, 1 oder 2 Sensoren)
# - Save Results → speichert Snapshot (JSON)
# - Start/Stop Dump → schreibt JSON-Lines auf Desktop
# - hebt Controller „vsctlee42a“ farbig hervor

import os, sys, time, json, threading
from collections import deque
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from Foundation import NSObject, NSRunLoop, NSDate
import CoreBluetooth as CB

# ---------------- CONFIG ----------------
CID_THERMO = 0x0019
KEEP_LAST = 50
HIGHLIGHT_NAME = "vsctlee42a"
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")

# --------------- Decoder ----------------
def le16(lo, hi): return ((hi & 0xFF) << 8) | (lo & 0xFF)

def decode_thermobeacon_msd(msd_bytes):
    b = list(msd_bytes)
    if len(b) < 2 + 6 + 2 + (2 * 4) + 1:
        return None
    cid = le16(b[0], b[1])
    if cid != CID_THERMO:
        return None

    pos = 2 + 6 + 2
    readings = []
    while pos + (2 * 4) + 1 <= len(b):
        ti = le16(b[pos], b[pos + 1]) / 16; pos += 2
        hi = le16(b[pos], b[pos + 1]) / 16; pos += 2
        te = le16(b[pos], b[pos + 1]) / 16; pos += 2
        he = le16(b[pos], b[pos + 1]) / 16; pos += 2
        pkt = b[pos] & 0xFF; pos += 1
        if not (-40 <= ti <= 85 and -40 <= te <= 85 and 0 <= hi <= 110 and 0 <= he <= 110):
            break
        readings.append(dict(
            temperature_int=ti, humidity_int=hi,
            temperature_ext=te, humidity_ext=he,
            packet_counter=pkt
        ))
    if not readings:
        return None
    if len(readings) == 2:
        return {"sensor_a": readings[0], "sensor_b": readings[1], "source": "thermobeacon2"}
    d = readings[0]
    d["source"] = "thermobeacon1"
    return d

# --------------- Controller -------------
class ScanController:
    def __init__(self, keep_last=KEEP_LAST):
        self.keep_last = keep_last
        self.history = deque(maxlen=keep_last)
        self.lock = threading.Lock()
        self.dump_file = None
        self.dump_path = None
        self.dump_enabled = False

    def record(self, entry):
        sig = None
        if "identifier" in entry:
            if "sensor_a" in entry:
                pkt = entry["sensor_a"].get("packet_counter", 0)
            else:
                pkt = entry.get("packet_counter", 0)
            sig = f"{entry['identifier']}_p{pkt}"
        with self.lock:
            if sig and any(h.get("_sig") == sig for h in self.history):
                return
            entry["_sig"] = sig
            self.history.append(entry.copy())
            if self.dump_enabled and self.dump_file:
                self.dump_file.write(json.dumps({k: v for k, v in entry.items() if k != "_sig"}) + "\n")
                self.dump_file.flush()

    def get_snapshot(self):
        with self.lock:
            return [dict({k: v for k, v in e.items() if k != "_sig"}) for e in self.history]

    def start_dump(self, prefix="ble_dump"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DESKTOP, f"{prefix}_{ts}.jsonl")
        try:
            f = open(path, "a", encoding="utf8")
            self.dump_file = f; self.dump_path = path; self.dump_enabled = True
            return path
        except Exception as e:
            print("dump start err:", e); return None

    def stop_dump(self):
        with self.lock:
            if self.dump_file:
                self.dump_file.close()
            p = self.dump_path
            self.dump_file = None; self.dump_path = None; self.dump_enabled = False
            return p

# --------------- CoreBluetooth Delegate -------------
class CentralDelegate(NSObject):
    def initWithController_(self, controller):
        self = self.init(); self.controller = controller; return self

    def centralManagerDidUpdateState_(self, manager):
        if manager.state() == CB.CBManagerStatePoweredOn:
            manager.scanForPeripheralsWithServices_options_(None, {"kCBScanOptionAllowDuplicatesKey": True})
        else:
            print("Bluetooth state:", manager.state())

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(self, m, p, adv, rssi):
        try:
            name = adv.get(CB.CBAdvertisementDataLocalNameKey) or p.name() or "(unknown)"
            mdata = adv.get(CB.CBAdvertisementDataManufacturerDataKey)
            entry = {
                "ts": time.strftime("%H:%M:%S"),
                "identifier": str(p.identifier()),
                "name": name,
                "rssi": int(rssi)
            }
            if mdata:
                b = bytes(mdata)
                entry["manufacturer_data_hex"] = b.hex()
                dec = decode_thermobeacon_msd(b)
                if dec:
                    entry.update(dec)
                else:
                    entry["source"] = "manufacturer"
            else:
                entry["source"] = "adv"
            self.controller.record(entry)
            Clock.schedule_once(lambda dt: self.controller.ui_update_callback(entry), 0)
        except Exception as e:
            print("discover err:", e, file=sys.stderr)

# --------------- GUI -------------------
class BLEGUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.controller = ScanController()
        self.delegate = None
        self.central = None
        self.scanning = False

        self.status = Label(text="Bereit", size_hint_y=None, height=28)
        self.add_widget(self.status)

        row = BoxLayout(size_hint_y=None, height=38)
        self.scan_btn = Button(text="Start Scan", on_release=self.toggle_scan)
        self.save_btn = Button(text="Save Results", on_release=self.save_snapshot)
        self.dump_btn = Button(text="Start Dump", on_release=self.toggle_dump)
        self.clear_btn = Button(text="Clear", on_release=self.clear_list)
        for b in (self.scan_btn, self.save_btn, self.dump_btn, self.clear_btn):
            row.add_widget(b)
        self.add_widget(row)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=4, padding=4)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.scroll.add_widget(self.grid)
        self.add_widget(self.scroll)

        self.device_widgets = {}
        self.controller.ui_update_callback = self.handle_new_entry

    def log(self, msg): self.status.text = msg

    def toggle_scan(self, *a):
        if self.scanning: self.stop_scan()
        else: self.start_scan()

    def start_scan(self):
        self.scanning = True
        self.scan_btn.text = "Stop Scan"
        self.log("Bluetooth initialisieren…")
        t = threading.Thread(target=self._scan_thread, daemon=True)
        t.start()

    def stop_scan(self):
        self.scanning = False
        self.scan_btn.text = "Start Scan"
        self.log("Scan gestoppt")
        try:
            if self.central: self.central.stopScan()
        except Exception: pass

    def _scan_thread(self):
        self.delegate = CentralDelegate.alloc().initWithController_(self.controller)
        self.central = CB.CBCentralManager.alloc().initWithDelegate_queue_options_(self.delegate, None, None)
        runloop = NSRunLoop.currentRunLoop()
        self.log("Scan läuft…")
        while self.scanning:
            runloop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))
        try: self.central.stopScan()
        except Exception: pass
        self.log("Scan beendet")

    def handle_new_entry(self, entry):
        name = entry.get("name", "(unknown)")
        key = entry.get("identifier", name)
        lbl = self.device_widgets.get(key)
        if lbl is None:
            lbl = Label(size_hint_y=None, height=28, halign="left", valign="middle")
            lbl.text_size = (self.width - 20, None)
            self.grid.add_widget(lbl)
            self.device_widgets[key] = lbl

        line = f"[{entry.get('ts')}] {name} RSSI {entry.get('rssi')}"
        src = entry.get("source")
        if src and src.startswith("thermobeacon"):
            if "sensor_a" in entry:
                a = entry["sensor_a"]
                line += f" | A:{a['temperature_int']:.1f}/{a['humidity_int']:.1f}%"
                if "sensor_b" in entry:
                    b = entry["sensor_b"]
                    line += f"  B:{b['temperature_int']:.1f}/{b['humidity_int']:.1f}%"
            else:
                line += f" | Ti={entry['temperature_int']:.1f}°C Hi={entry['humidity_int']:.1f}%"
        else:
            line += f" | {entry.get('source')}"
        lbl.text = line

        if HIGHLIGHT_NAME.lower() in name.lower():
            self.flash_alert(name)

    def flash_alert(self, name):
        self.log(f"!!! Controller gefunden: {name} !!!")
        def reset_color(dt): Window.clearcolor = get_color_from_hex("#2b2b2b")
        def blink_once(dt):
            Window.clearcolor = get_color_from_hex("#330000")
            Clock.schedule_once(reset_color, 0.25)
        Clock.schedule_once(blink_once, 0)

    def save_snapshot(self, *a):
        snap = self.controller.get_snapshot()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DESKTOP, f"ble_snapshot_{ts}.json")
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            self.log(f"Saved → {path}")
        except Exception as e:
            self.log(f"Save failed: {e}")

    def toggle_dump(self, *a):
        if not self.controller.dump_enabled:
            p = self.controller.start_dump()
            if p:
                self.dump_btn.text = "Stop Dump"
                self.log(f"Dump läuft → {p}")
            else:
                self.log("Dump start failed")
        else:
            p = self.controller.stop_dump()
            self.dump_btn.text = "Start Dump"
            self.log(f"Dump gestoppt → {p if p else '(unknown)'}")

    def clear_list(self, *a):
        self.grid.clear_widgets()
        self.device_widgets.clear()
        with self.controller.lock:
            self.controller.history.clear()
        self.log("Liste geleert")

# --------------- App -------------------
class BLEApp(App):
    def build(self):
        Window.clearcolor = get_color_from_hex("#2b2b2b")
        return BLEGUI()

if __name__ == "__main__":
    BLEApp().run()
