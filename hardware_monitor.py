#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hardware_monitor.py – Watchdog v3 (stabil)
• Löscht JSON nur 1x pro Abbruch, danach wartet auf neue Pakete
• Kein Endlos-Reset, kein Konflikt mit Setup
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, io, json, time
from kivy.clock import Clock
from kivy.utils import platform
from dashboard_charts import APP_JSON

class HardwareMonitor:
    def __init__(self, poll_interval=5.0, stale_seconds=10.0, clear_at_start=True):
        self.poll_interval = float(poll_interval)
        self.stale_seconds = float(stale_seconds)

        self.last_data_time = time.time()
        self.last_packet_counter = None
        self.bt_enabled = True

        self._scheduled = None
        self._running = False
        self._stale_triggered = False  # Marker: JSON wurde schon geleert für aktuellen Abriss
        self._suspend_logged = False

        # Einmaliger Reset beim Start
        if clear_at_start:
            try:
                self.clear_ble_json()
                print("🧹 HardwareMonitor: APP_JSON einmalig beim Start geleert.")
            except Exception as e:
                print("⚠️ HardwareMonitor: Fehler beim Start-Reset:", e)

        self.start()

    # -------------------------------------------------------
    # Scheduler control
    # -------------------------------------------------------
    def start(self):
        if self._running:
            return
        self._scheduled = Clock.schedule_interval(self._loop, self.poll_interval)
        self._running = True
        print(f"▶️ HardwareMonitor gestartet (poll={self.poll_interval}s, stale={self.stale_seconds}s).")

    def stop(self):
        if self._scheduled:
            Clock.unschedule(self._scheduled)
            self._scheduled = None
        self._running = False
        print("⏹ HardwareMonitor gestoppt.")

    # -------------------------------------------------------
    # Hauptloop (mit Einmal-Clear pro Abriss)
    # -------------------------------------------------------
    def _loop(self, *_):
        try:
            self.bt_enabled = self._check_bluetooth_enabled()
            self._check_data_stream()

            # während Setup deaktivieren
            if getattr(self, "suspend_clear", False):
                if not self._suspend_logged:
                    print("🛑 Hardware-Monitor: JSON-Clear während Setup deaktiviert")
                    self._suspend_logged = True
                return
            self._suspend_logged = False

            # Datenabriss prüfen
            now = time.time()
            if (now - self.last_data_time) >= (self.stale_seconds * 2):
                # Wenn noch kein Clear für diesen Abriss durchgeführt wurde → genau 1x leeren
                if not self._stale_triggered:
                    print(f"⚠️ Datenstrom inaktiv >{self.stale_seconds*2:.0f}s → JSON einmalig leeren")
                    self.clear_ble_json()
                    self._stale_triggered = True
            else:
                # Daten wieder aktiv → Flag zurücksetzen
                if self._stale_triggered:
                    print("✅ Hardware-Monitor: neuer Datenstrom erkannt → Clear wieder erlaubt")
                self._stale_triggered = False

        except Exception as e:
            print("⚠️ HardwareMonitor Fehler:", e)

    # -------------------------------------------------------
    # Bluetooth prüfen
    # -------------------------------------------------------
    def _check_bluetooth_enabled(self):
        if platform != "android":
            return True
        try:
            from jnius import autoclass
            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            adapter = BluetoothAdapter.getDefaultAdapter()
            return bool(adapter and adapter.isEnabled())
        except Exception:
            return False

    def is_bluetooth_enabled(self):
        return bool(self.bt_enabled)

    # -------------------------------------------------------
    # Datenstrom prüfen
    # -------------------------------------------------------
    def _check_data_stream(self):
        if getattr(self, "suspend_clear", False):
            return
        try:
            if not os.path.exists(APP_JSON):
                return
            with open(APP_JSON, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                return

            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                return
            d = data[0]
            pkt = d.get("packet_counter") or d.get("pkt") or d.get("counter")

            if pkt is not None:
                try:
                    pkt_val = int(pkt)
                except Exception:
                    pkt_val = None

                if pkt_val is not None and pkt_val != self.last_packet_counter:
                    self.last_packet_counter = pkt_val
                    self.last_data_time = time.time()
                    # sobald wieder Daten kommen → Clear reaktivieren
                    if self._stale_triggered:
                        print("✅ Hardware-Monitor: neue Pakete empfangen, Watchdog zurückgesetzt")
                        self._stale_triggered = False
            else:
                # kein counter, aber Daten vorhanden
                self.last_data_time = time.time()
        except Exception as e:
            print("⚠️ HardwareMonitor _check_data_stream Fehler:", e)

    # -------------------------------------------------------
    # JSON löschen
    # -------------------------------------------------------
    def clear_ble_json(self):
        try:
            os.makedirs(os.path.dirname(APP_JSON), exist_ok=True)
            with io.open(APP_JSON, "w", encoding="utf-8") as f:
                f.write("[]")
            print(f"🧹 APP_JSON geleert: {APP_JSON}")
            self.last_packet_counter = None
        except Exception as e:
            print("⚠️ clear_ble_json Fehler:", e)

    # -------------------------------------------------------
    # Status
    # -------------------------------------------------------
    def status(self):
        return {
            "bt_enabled": self.is_bluetooth_enabled(),
            "data_active": not self.is_data_stale(),
            "last_packet_counter": self.last_packet_counter,
            "last_data_age_s": round(time.time() - self.last_data_time, 1),
        }

    def is_data_stale(self):
        try:
            return (time.time() - float(self.last_data_time)) >= float(self.stale_seconds)
        except Exception:
            return False
