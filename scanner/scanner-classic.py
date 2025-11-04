#!/usr/bin/env python3
# -------------------------------------------------------------
#  bt_classic_scanner.py – macOS Classic Bluetooth Scanner (IOBluetooth)
# -------------------------------------------------------------
# - scannt via IOBluetoothDeviceInquiry (Classic BT, kein BLE)
# - GUI identisch zu deinem BLE-Tool (Kivy)
# - Save Results → Snapshot (JSON) auf Desktop
# - Start/Stop Dump → dekodierte JSON-Lines (Desktop)
# - Start/Stop Raw  → Roh-Einträge (Desktop)
# -------------------------------------------------------------

import os, sys, json, threading, time
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
# PyObjC-Bridge fürs Classic-Bluetooth-Framework
# pip install pyobjc-core pyobjc pyobjc-framework-IOBluetooth
from IOBluetooth import IOBluetoothDeviceInquiry

# ---------------- CONFIG ----------------
KEEP_LAST = 200
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
HIGHLIGHT_NAME = ""  # optional: z.B. "JBL", "Magic Keyboard"

# ---- CoD Mapping (Class of Device) Hilfen (heuristisch/kompakt) ----
# IOBluetoothDevice.classOfDevice() -> int (24-bit)
# bits 8..12 = Major Device Class, bits 2..7 = Minor (klassifiziert hier grob)
MAJOR_CLASS_MAP = {
    0x00: "Misc",
    0x01: "Computer",
    0x02: "Phone",
    0x03: "LAN/Net",
    0x04: "Audio/Video",
    0x05: "Peripheral",
    0x06: "Imaging",
    0x07: "Wearable",
    0x08: "Toy",
    0x09: "Health",
    0x1F: "Uncategorized",
}

def class_of_device_info(cod: int):
    major = (cod >> 8) & 0x1F
    minor = (cod >> 2) & 0x3F
    return {
        "cod_hex": f"0x{cod:06X}",
        "major": MAJOR_CLASS_MAP.get(major, f"Major:{major}"),
        "minor_bits": minor
    }

# --------------- Controller -------------
class ScanController:
    def __init__(self, keep_last=KEEP_LAST):
        self.keep_last = keep_last
        self.history = deque(maxlen=keep_last)
        self.lock = threading.Lock()
        # Decoded dump (jsonl)
        self.dump_file = None
        self.dump_path = None
        self.dump_enabled = False
        # Raw dump (jsonl)
        self.raw_file = None
        self.raw_path = None
        self.raw_enabled = False

    def record(self, entry: dict):
        # Dedupe nach Adresse + Zeitsekunde (Classic liefert oft ohne Counter)
        addr = entry.get("address") or entry.get("identifier")
        sig = f"{addr}_{entry.get('ts')}"
        with self.lock:
            if any(h.get("_sig") == sig for h in self.history):
                return
            entry = dict(entry)
            entry["_sig"] = sig
            self.history.append(entry)
            if self.dump_enabled and self.dump_file:
                self.dump_file.write(json.dumps({k: v for k, v in entry.items() if k != "_sig"}) + "\n")
                self.dump_file.flush()

    def start_dump(self, prefix="btclassic_dump"):
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

    def start_raw(self, prefix="btclassic_rawdump"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DESKTOP, f"{prefix}_{ts}.jsonl")
        try:
            f = open(path, "a", encoding="utf8")
            self.raw_file = f; self.raw_path = path; self.raw_enabled = True
            return path
        except Exception as e:
            print("raw start err:", e); return None

    def stop_raw(self):
        with self.lock:
            if self.raw_file:
                self.raw_file.close()
            p = self.raw_path
            self.raw_file = None; self.raw_path = None; self.raw_enabled = False
            return p

    def get_snapshot(self):
        with self.lock:
            return [dict({k: v for k, v in e.items() if k != "_sig"}) for e in self.history]

# --------------- Inquiry Delegate -------------
class InquiryDelegate(NSObject):
    def initWithGui_(self, gui):
        self = self.init()
        if self is None: return None
        self.gui = gui
        self.controller = gui.controller
        return self

    # Wird pro gefundenem Gerät aufgerufen
    def deviceFound_(self, device):
        try:
            # Basisdaten
            name = device.name() or "(unknown)"
            # Adresse
            try:
                addr = device.addressString()
            except Exception:
                # ältere Bridges
                addr = str(device.getAddressString()) if hasattr(device, "getAddressString") else "(unknown)"
            # RSSI
            rssi = None
            try:
                # Manche Geräte liefern -0..-127, manchmal 127 = unbekannt
                rssi = int(device.RSSI())
                if rssi == 127:  # Apple-Konvention "unknown"
                    rssi = None
            except Exception:
                rssi = None

            # Class of Device
            cod = 0
            try:
                cod = int(device.classOfDevice())
            except Exception:
                try:
                    cod = int(device.getClassOfDevice())
                except Exception:
                    cod = 0
            cod_info = class_of_device_info(cod)

            ts = time.strftime("%H:%M:%S")
            entry = {
                "ts": ts,
                "name": name,
                "address": addr,
                "rssi": rssi if rssi is not None else "",
                "class_of_device": cod_info,
                "source": "bt-classic",
            }

            # RAW dump (so "roh" wie Classic hergibt)
            if self.controller.raw_enabled and self.controller.raw_file:
                raw_entry = {
                    "ts": ts, "name": name, "address": addr,
                    "rssi": rssi if rssi is not None else "",
                    "cod_hex": cod_info["cod_hex"],
                    "major": cod_info["major"],
                    "minor_bits": cod_info["minor_bits"]
                }
                self.controller.raw_file.write(json.dumps(raw_entry) + "\n")
                self.controller.raw_file.flush()

            self.controller.record(entry)
            Clock.schedule_once(lambda dt: self.gui.update_row(entry), 0)

        except Exception as e:
            print("deviceFound err:", e, file=sys.stderr)

    # Inquiry beendet (entweder normal oder mit Fehler/Abbruch)
    def inquiryComplete_error_aborted_(self, inquiry, error, aborted):
        # Wir lassen die GUI den Status setzen
        Clock.schedule_once(lambda dt: self.gui.on_inquiry_done(int(error), bool(aborted)), 0)

# --------------- GUI -------------------
class ClassicGUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.controller = ScanController()
        self.inquiry = None
        self.delegate = None
        self.scanning = False

        self.status = Label(text="Bereit (Classic BT)", size_hint_y=None, height=28)
        self.add_widget(self.status)

        row = BoxLayout(size_hint_y=None, height=38)
        self.scan_btn = Button(text="Start Scan", on_release=self.toggle_scan)
        self.save_btn = Button(text="Save Results", on_release=self.save_snapshot)
        self.dump_btn = Button(text="Start Dump", on_release=self.toggle_dump)
        self.raw_btn  = Button(text="Start Raw",  on_release=self.toggle_raw)
        self.clear_btn = Button(text="Clear", on_release=self.clear_list)
        for b in (self.scan_btn, self.save_btn, self.dump_btn, self.raw_btn, self.clear_btn):
            row.add_widget(b)
        self.add_widget(row)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=4, padding=4)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.scroll.add_widget(self.grid)
        self.add_widget(self.scroll)

        self.device_widgets = {}

    def log(self, msg): self.status.text = msg

    # ---------- Scan control ----------
    def toggle_scan(self, *a):
        if self.scanning: self.stop_scan()
        else: self.start_scan()

    def start_scan(self):
        if self.scanning: return
        self.scanning = True
        self.scan_btn.text = "Stop Scan"
        self.log("Inquiry initialisieren…")

        self.delegate = InquiryDelegate.alloc().initWithGui_(self)
        self.inquiry = IOBluetoothDeviceInquiry.alloc().init()
        self.inquiry.setDelegate_(self.delegate)
        # Optional: neue Namen aktualisieren, klassisch alle finden (GIAC)
        try:
            self.inquiry.setInquiryLength_(10)  # Sekunden (macOS default 10)
        except Exception:
            pass
        try:
            self.inquiry.setUpdateNewDeviceNames_(True)
        except Exception:
            pass
        try:
            self.inquiry.start()
        except Exception as e:
            self.log(f"Start fehlgeschlagen: {e}")
            self.scanning = False
            self.scan_btn.text = "Start Scan"
            return

        # Runloop pumpen in separatem Thread
        t = threading.Thread(target=self._loop_thread, daemon=True)
        t.start()
        self.log("Classic-BT Scan läuft…")

    def _loop_thread(self):
        runloop = NSRunLoop.currentRunLoop()
        while self.scanning:
            runloop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))
        # stop handled in stop_scan()

    def stop_scan(self):
        if not self.scanning: return
        self.scanning = False
        self.scan_btn.text = "Start Scan"
        try:
            if self.inquiry:
                self.inquiry.stop()
        except Exception:
            pass
        self.log("Scan gestoppt")

    def on_inquiry_done(self, error_code: int, aborted: bool):
        # Wird vom Delegate gemeldet
        if aborted:
            self.log("Scan abgebrochen")
        elif error_code != 0:
            self.log(f"Scan beendet mit Fehler: {error_code}")
        else:
            self.log("Scan abgeschlossen")
        # Für kontinuierlichen Scan ggf. sofort neu starten:
        if self.scanning:
            # Neu starten
            try:
                self.inquiry.start()
                self.log("Classic-BT Scan läuft…")
            except Exception as e:
                self.log(f"Neustart fehlgeschlagen: {e}")
                self.scanning = False
                self.scan_btn.text = "Start Scan"

    # ---------- UI update ----------
    def update_row(self, entry: dict):
        name = entry.get("name", "(unknown)")
        key = entry.get("address", name)
        lbl = self.device_widgets.get(key)
        if lbl is None:
            lbl = Label(size_hint_y=None, height=28, halign="left", valign="middle")
            lbl.text_size = (self.width - 20, None)
            self.grid.add_widget(lbl)
            self.device_widgets[key] = lbl

        cod = entry.get("class_of_device", {})
        major = cod.get("major", "")
        line = f"[{entry.get('ts')}] {name} RSSI {entry.get('rssi')}"
        line += f" | Addr {entry.get('address')} | Class {major}"
        lbl.text = line

        if HIGHLIGHT_NAME and HIGHLIGHT_NAME.lower() in str(name).lower():
            self.flash_alert(name)

    def flash_alert(self, name):
        def reset_color(dt): Window.clearcolor = get_color_from_hex("#2b2b2b")
        def blink_once(dt):
            Window.clearcolor = get_color_from_hex("#003300")
            Clock.schedule_once(reset_color, 0.25)
        Clock.schedule_once(blink_once, 0)
        self.log(f"!!! Classic-Gerät: {name} !!!")

    # ---------- Actions ----------
    def save_snapshot(self, *a):
        snap = self.controller.get_snapshot()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DESKTOP, f"btclassic_snapshot_{ts}.json")
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

    def toggle_raw(self, *a):
        if not self.controller.raw_enabled:
            p = self.controller.start_raw()
            if p:
                self.raw_btn.text = "Stop Raw"
                self.log(f"Raw-Dump läuft → {p}")
            else:
                self.log("Raw start failed")
        else:
            p = self.controller.stop_raw()
            self.raw_btn.text = "Start Raw"
            self.log(f"Raw-Dump gestoppt → {p if p else '(unknown)'}")

    def clear_list(self, *a):
        self.grid.clear_widgets()
        self.device_widgets.clear()
        with self.controller.lock:
            self.controller.history.clear()
        self.log("Liste geleert")

# --------------- App -------------------
class ClassicBTApp(App):
    def build(self):
        Window.clearcolor = get_color_from_hex("#2b2b2b")
        return ClassicGUI()

if __name__ == "__main__":
    ClassicBTApp().run()
