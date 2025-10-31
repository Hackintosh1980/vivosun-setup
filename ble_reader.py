#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ble_reader.py – Bridge-gesteuerter BLE-Scan + Parser
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, json, time
from kivy.clock import Clock
from kivy.utils import platform

# --- jnius Import nur unter Android aktiv ---
if platform == "android":
    from jnius import autoclass, cast


# --------------------------------------------------
# 🌿 Hauptklasse für Bridge + Parser + Callback
# --------------------------------------------------
class BleReader:
    def __init__(self, update_callback=None, scan_interval=5.0):
        """
        update_callback: Funktion, die bei neuen Daten aufgerufen wird
                         → def cb(data: dict): ...
        scan_interval:   Zeit in Sekunden zwischen Scans
        """
        self.update_callback = update_callback
        self.scan_interval = scan_interval
        self.running = False
        self._event = None
        self.ctx = None

    # --------------------------------------------------
    def start(self):
        """Starte den zyklischen BLE-Scan."""
        if self.running:
            print("⚠️ BleReader läuft bereits.")
            return

        print("📡 Starte BLE-Reader-Daemon …")
        self.running = True

        if platform == "android":
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self.ctx = PythonActivity.mActivity
        else:
            self.ctx = None

        self._event = Clock.schedule_interval(self._scan_once, self.scan_interval)

    # --------------------------------------------------
    def stop(self):
        """Stoppe den Reader."""
        if self._event:
            self._event.cancel()
        self.running = False
        print("🛑 BLE-Reader gestoppt.")

    # --------------------------------------------------
    def _scan_once(self, *_):
        """Ein Scan-Zyklus (Android Bridge oder Dummy)."""
        if platform != "android":
            # 🧪 Desktop-Dummy
            dummy = {
                "mac": "A4:C1:38:FA:CE:01",
                "temp": 22.4 + (time.time() % 5) / 2,
                "hum": 55.0 + (time.time() % 10) / 3,
                "battery": 91,
                "rssi": -65,
            }
            print(f"💻 Dummy BLE-Update: {dummy}")
            if self.update_callback:
                self.update_callback(dummy)
            return

        try:
            BleBridge = autoclass("org.hackintosh1980.blebridge.BleBridge")
            ret = BleBridge.scan(self.ctx, 3500)
            print(f"📡 Bridge-Rückgabe: {ret}")
            if ret.startswith("OK:"):
                path = ret.split("OK:")[1].strip()
                self._read_json(path)
            else:
                print(f"⚠️ Scan-Fehler: {ret}")
        except Exception as e:
            print("💥 Fehler beim Bridge-Aufruf:", e)

    # --------------------------------------------------
    def _read_json(self, path):
        """JSON-Datei der Bridge auslesen und dekodieren."""
        if not os.path.exists(path):
            print(f"⚠️ JSON nicht gefunden: {path}")
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            # erwartet Liste von Devices
            for entry in data.get("devices", []):
                parsed = self._parse_device(entry)
                if parsed and self.update_callback:
                    self.update_callback(parsed)
        except Exception as e:
            print("💥 Fehler beim Lesen der JSON:", e)

    # --------------------------------------------------
    def _parse_device(self, entry):
        """Dekodiere HEX-Daten vom Herstellerbereich."""
        try:
            mac = entry.get("mac")
            rssi = entry.get("rssi", 0)
            manuf = entry.get("manufacturer_data", "")
            if not manuf:
                return None

            # Beispiel-Dekodierung (ThermoBeacon)
            hexdata = bytes.fromhex(manuf)
            if len(hexdata) < 10:
                return None

            temp_raw = int.from_bytes(hexdata[4:6], "little", signed=True)
            hum_raw = int.from_bytes(hexdata[6:8], "little")
            batt = hexdata[8]

            temp = round(temp_raw / 100, 1)
            hum = round(hum_raw / 100, 1)

            return {
                "mac": mac,
                "temp": temp,
                "hum": hum,
                "battery": batt,
                "rssi": rssi,
            }
        except Exception as e:
            print("💥 Parser-Fehler:", e)
            return None
