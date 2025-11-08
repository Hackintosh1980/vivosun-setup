#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ble_gui_writer_mac.py – macOS GUI BLE Scanner → ble_scan.json (Dashboard-Format)
- CoreBluetooth (pyobjc), kein Bleak nötig
- schreibt alle 1.5s nach ~/vivosun-setup/blebridge_desktop/ble_scan.json
- ThermoBeacon/VSCTLE Decoder (0x0019, Q4.4, signed), ext_present, packet_counter
- alive/status mit Timeout; stale => Werte -99
- Minimal-GUI: Start/Stop + Statuszeile

© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, sys, time, json, threading
from datetime import datetime, timezone
from collections import defaultdict

# --- Kivy UI ---
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

# --- macOS CoreBluetooth via pyobjc ---
from Foundation import NSObject, NSRunLoop, NSDate
import CoreBluetooth as CB

# ---------------- CONFIG ----------------
OUT_DIR  = os.path.expanduser("~/vivosun-setup/blebridge_desktop")
OUT_FILE = os.path.join(OUT_DIR, "ble_scan.json")
WRITE_INTERVAL = 1.5           # Sekunden
TIMEOUT_MS     = 15000         # 15 s → stale
CID_0019       = 0x0019        # ThermoBeacon/VSCTLE Company ID

# ================= Decoding helpers =================

def ts_iso() -> str:
    # ISO-8601 +0000, Millisekunden
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000"

def le16(lo: int, hi: int) -> int:
    return ((hi & 0xFF) << 8) | (lo & 0xFF)

def q44_to_float_signed(v: int) -> float:
    # signed 16-bit, Q4.4 → /16
    if v & 0x8000:
        v -= 0x10000
    return round(v / 16.0, 2)

def decode_thb_like(msd: bytes):
    """
    Dekodiert Herstellerdaten nach VIVOSUN/THB-Layout:
    [0..1]   : Company ID (0x0019, little endian)
    [2..7]   : MAC/addr bytes (6)
    [8..9]   : ??? (2)
    [10..15] : int temp/hum (2 each)
    [16..21] : ext temp/hum (2 each)
    [22]     : packet counter (1)
    Mindestens 2+6+2+(2*4)+1 = 19 bytes (+ evtl. weitere Felder)
    """
    b = list(msd or b"")
    need = 2 + 6 + 2 + (2 * 4) + 1
    if len(b) < need:
        return None

    cid = le16(b[0], b[1])
    if cid != CID_0019:
        return None

    pos = 2 + 6 + 2
    ti = q44_to_float_signed(le16(b[pos], b[pos+1])); pos += 2
    hi = q44_to_float_signed(le16(b[pos], b[pos+1])); pos += 2
    te = q44_to_float_signed(le16(b[pos], b[pos+1])); pos += 2
    he = q44_to_float_signed(le16(b[pos], b[pos+1])); pos += 2
    pkt = b[pos] & 0xFF

    # Plausibilität + ext_present
    ext_present = not (he <= 0.1 or he > 110.0)
    if not ext_present:
        te = -99.0
        he = -99.0

    # Filter unsinniger interner Werte
    if not (-40.0 <= ti <= 85.0 and 0.0 <= hi <= 110.0):
        return None

    return dict(
        temperature_int=ti,
        humidity_int=hi,
        temperature_ext=te,
        humidity_ext=he,
        packet_counter=pkt,
        ext_present=ext_present
    )

def classify_name(name: str) -> str:
    n = (name or "").lower()
    if "vsctle" in n or "growhub" in n:
        return "controller"
    if "thermobeacon" in n or "thb" in n or "vivosun" in n:
        return "sensor"
    return "unknown"

# ================= Controller / Storage =================

class Store:
    """
    Hält letzten Stand je Gerät (by identifier) und alive/timeout-Status.
    Auf macOS liefert CoreBluetooth keinen klassischen MAC, daher nehmen wir p.identifier().
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.last = {}                 # id → dict (dashboard-format)
        self.last_pkt_time = {}        # id → epoch ms
        self.last_seen_alive = {}      # id → bool

    def update_from_adv(self, identifier: str, name: str, rssi: int, msd: bytes):
        decoded = decode_thb_like(msd)
        dtype = classify_name(name)

        now_iso = ts_iso()
        entry = dict(
            timestamp=now_iso,
            name=name or "(unknown)",
            address=identifier,   # macOS UUID als "address"
            rssi=int(rssi) if isinstance(rssi, (int, float)) else -99,
            type=dtype,
            temperature_int=-99.0,
            humidity_int=-99.0,
            temperature_ext=-99.0,
            humidity_ext=-99.0,
            packet_counter=0,
            ext_present=False,
            alive=True,
            status="active",
        )
        if decoded:
            entry.update(decoded)

        with self.lock:
            self.last[identifier] = entry
            self.last_pkt_time[identifier] = int(time.time() * 1000)
            self.last_seen_alive[identifier] = True

    def apply_timeouts(self):
        now_ms = int(time.time() * 1000)
        changed = False
        with self.lock:
            for dev_id, entry in list(self.last.items()):
                last_ms = self.last_pkt_time.get(dev_id, 0)
                alive = (now_ms - last_ms) < TIMEOUT_MS
                prev_alive = self.last_seen_alive.get(dev_id, True)
                if alive != prev_alive:
                    self.last_seen_alive[dev_id] = alive
                    changed = True
                if not alive:
                    entry["alive"] = False
                    entry["status"] = "stale"
                    entry["temperature_int"] = -99.0
                    entry["humidity_int"] = -99.0
                    entry["temperature_ext"] = -99.0
                    entry["humidity_ext"] = -99.0
                    entry["ext_present"] = False
                else:
                    entry["alive"] = True
                    entry["status"] = "active"
        return changed

    def snapshot(self):
        with self.lock:
            return list(self.last.values())

# ================= CoreBluetooth Delegate =================

class CentralDelegate(NSObject):
    def initWithStore_(self, store):
        self = self.init()
        self.store = store
        return self

    def centralManagerDidUpdateState_(self, manager):
        if manager.state() == CB.CBManagerStatePoweredOn:
            # allow duplicates = True → kontinuierliche Updates
            manager.scanForPeripheralsWithServices_options_(None, {"kCBScanOptionAllowDuplicatesKey": True})
        else:
            print("Bluetooth state:", manager.state())

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(self, m, p, adv, rssi):
        try:
            name = adv.get(CB.CBAdvertisementDataLocalNameKey) or p.name() or "(unknown)"
            msd  = adv.get(CB.CBAdvertisementDataManufacturerDataKey)
            ident = str(p.identifier())
            self.store.update_from_adv(ident, name, int(rssi), bytes(msd) if msd else b"")
        except Exception as e:
            print("discover err:", e, file=sys.stderr)

# ================= Writer Thread =================

class WriterThread(threading.Thread):
    def __init__(self, store: Store, interval: float = WRITE_INTERVAL):
        super().__init__(daemon=True)
        self.store = store
        self.interval = max(0.5, float(interval))
        self.running = threading.Event()
        self.running.set()
        os.makedirs(OUT_DIR, exist_ok=True)

    def run(self):
        while self.running.is_set():
            try:
                # Zeitüberschreitungen anwenden
                self.store.apply_timeouts()
                # Snapshot schreiben
                data = self.store.snapshot()
                tmp = OUT_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, OUT_FILE)
            except Exception as e:
                print("write err:", e, file=sys.stderr)
            time.sleep(self.interval)

    def stop(self):
        self.running.clear()

# ================= GUI =================

class BLEGUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.store = Store()
        self.delegate = None
        self.central = None
        self.scanning = False
        self.writer = None

        # Status
        self.status = Label(text="Bereit", size_hint_y=None, height=30)
        self.add_widget(self.status)

        # Buttons
        row = BoxLayout(size_hint_y=None, height=40, spacing=6, padding=[6,4,6,4])
        self.scan_btn = Button(text="Start Scan", on_release=self.toggle_scan)
        self.stop_btn = Button(text="Stop", on_release=self.stop_all, disabled=True)
        self.path_lbl = Label(text=OUT_FILE, font_size="12sp", halign="left", valign="middle")
        self.path_lbl.text_size = (self.path_lbl.width, None)
        row.add_widget(self.scan_btn)
        row.add_widget(self.stop_btn)
        self.add_widget(row)
        self.add_widget(self.path_lbl)

        # Footer hint
        self.hint = Label(text="Schreibt alle 1.5s → ble_scan.json (Dashboard-Format)", size_hint_y=None, height=24)
        self.add_widget(self.hint)

    def log(self, msg): self.status.text = msg

    def toggle_scan(self, *_):
        if self.scanning:
            self.stop_all()
        else:
            self.start_all()

    def start_all(self):
        self.scanning = True
        self.scan_btn.text = "Neu starten"
        self.stop_btn.disabled = False
        self.log("Bluetooth initialisieren…")

        # CoreBluetooth Start in Thread mit RunLoop
        t = threading.Thread(target=self._scan_thread, daemon=True)
        t.start()

        # Writer starten
        self.writer = WriterThread(self.store, WRITE_INTERVAL)
        self.writer.start()
        self.log("Scan & Writer laufen…")

    def stop_all(self, *_):
        self.scanning = False
        self.stop_btn.disabled = True
        self.log("Stoppe Scan…")
        try:
            if self.central: self.central.stopScan()
        except Exception: pass
        if self.writer:
            self.writer.stop()
            self.writer = None
        self.log("Gestoppt.")

    def _scan_thread(self):
        try:
            self.delegate = CentralDelegate.alloc().initWithStore_(self.store)
            self.central  = CB.CBCentralManager.alloc().initWithDelegate_queue_options_(self.delegate, None, None)
            runloop = NSRunLoop.currentRunLoop()
            while self.scanning:
                runloop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))
        except Exception as e:
            print("scan thread err:", e, file=sys.stderr)
            Clock.schedule_once(lambda dt: self.log(f"Scan-Fehler: {e}"), 0)

class BLEApp(App):
    def build(self):
        Window.clearcolor = get_color_from_hex("#2b2b2b")
        return BLEGUI()

if __name__ == "__main__":
    BLEApp().run()
