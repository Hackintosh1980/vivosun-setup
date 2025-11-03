#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChartManager – Live-Only (Android-robust, Bridge-Autostart, Device-Switch fix,
sauberes Start/Stop/Reset, dicke Linien bleiben)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, json
from kivy.clock import Clock
from kivy_garden.graph import LinePlot
from kivy.utils import platform
import config, utils

# ----------------------------------------------------------
# APP_JSON robust ermitteln (keine harte Paket-ID)
# ----------------------------------------------------------
def _resolve_app_json():
    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            files_dir = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            return os.path.join(files_dir, "ble_scan.json")
        except Exception as e:
            print("⚠️ Konnte filesDir nicht ermitteln, fallback:", e)
            return "/sdcard/Android/data/org.hackintosh1980.dashboard/files/ble_scan.json"
    else:
        return os.path.expanduser("~/vivosun-setup/blebridge_desktop/ble_scan.json")

APP_JSON = _resolve_app_json()
print(f"🗂️ Verwende APP_JSON = {APP_JSON}")


class ChartManager:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.buffers = {}
        self.plots = {}
        self.counter = 0
        self.running = True
        self._poll_event = None
        self._bridge_started = False

        # --- Config laden ---
        self.cfg = config.load_config() or {}
        self.refresh_interval = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window     = int(self.cfg.get("chart_window", 120))
        print(f"🌿 ChartManager init – Live, Poll={self.refresh_interval}s, Window={self.chart_window}")

        # --- Graphs vorbereiten (dicke Linien) ---
        for key in [
            "tile_t_in", "tile_h_in", "tile_vpd_in",
            "tile_t_out", "tile_h_out", "tile_vpd_out"
        ]:
            tile = dashboard.ids.get(key)
            if not tile:
                print(f"⚠️ Tile nicht gefunden: {key}")
                continue
            graph = tile.ids.g
            plot = LinePlot(color=(*tile.accent, 1))
            plot.line_width = 4.0
            graph.add_plot(plot)
            self.plots[key] = plot
            self.buffers[key] = []

            if graph.ymax == graph.ymin:
                graph.ymin = 0
                graph.ymax = 1

        # --- Bridge sicherstellen (Android), dann Poll starten ---
        self._ensure_bridge_started()
        self.start_polling()

    # ----------------------------------------------------------
    # Bridge-Autostart (nur Android; device_id optional setzen)
    # ----------------------------------------------------------
    def _ensure_bridge_started(self):
        if platform != "android" or self._bridge_started:
            return
        try:
            # Nur starten, wenn Live-Mode in config aktiv ist
            live_cfg = config.load_config() or {}
            if live_cfg.get("mode") != "live":
                print("ℹ️ Live-Mode in config nicht aktiv → Bridge-Autostart übersprungen.")
                return

            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ctx = PythonActivity.mActivity
            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")

            ret = BleBridgePersistent.start(ctx, "ble_scan.json")
            print(f"🚀 Bridge.start → {ret}")

            # Aktive MAC setzen, falls Methode existiert
            dev = live_cfg.get("device_id")
            try:
                if dev and hasattr(BleBridgePersistent, "setActiveMac"):
                    BleBridgePersistent.setActiveMac(dev)
                    print(f"🎯 setActiveMac({dev}) OK")
            except Exception as e:
                print("⚠️ setActiveMac fehlgeschlagen:", e)

            self._bridge_started = True

        except Exception as e:
            print("⚠️ Bridge-Autostart-Fehler:", e)

    # ----------------------------------------------------------
    # Polling Lifecycle
    # ----------------------------------------------------------
    def start_polling(self):
        """Startet oder reschedult den Poll-Loop."""
        if hasattr(self, "_poll_event") and self._poll_event:
            Clock.unschedule(self._poll_event)
        self.running = True
        print(f"▶️ Starte Polling (Intervall {self.refresh_interval}s)")
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)

    def stop_polling(self):
        """Stoppt den Poll-Loop."""
        if hasattr(self, "_poll_event") and self._poll_event:
            Clock.unschedule(self._poll_event)
            self._poll_event = None
        self.running = False
        print("⏹ Polling gestoppt.")

    # ----------------------------------------------------------
    # Haupt-Poll
    # ----------------------------------------------------------
    def _poll_json(self, *a):
        if not self.running:
            return
        try:
            # Device-ID dynamisch holen (Umschaltung erlauben)
            device_id = None
            try:
                device_id = getattr(config, "load_device_id", lambda: None)()
            except Exception:
                device_id = None
            if not device_id:
                device_id = self.cfg.get("device_id")

            # Datei prüfen
            if not os.path.exists(APP_JSON):
                print(f"⚠️ JSON fehlt: {APP_JSON}")
                self._set_no_data_labels()
                return

            with open(APP_JSON, "r") as f:
                content = f.read().strip()
            if not content:
                print("⚠️ JSON aktuell leer (Schreibvorgang läuft).")
                self._set_no_data_labels()
                return

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                print("⚠️ JSON noch unvollständig – nächster Poll …")
                return

            if not data or not isinstance(data, list):
                print("⚠️ JSON leer oder ungültig.")
                self._set_no_data_labels()
                return

            if device_id:
                data = [d for d in data if d.get("address") == device_id]
                if not data:
                    print(f"⚠️ Keine Daten für aktives Gerät {device_id}.")
                    self._set_no_data_labels()
                    return

            d = data[0]

            # Werte
            t_int = d.get("temperature_int", 0.0)
            t_ext = d.get("temperature_ext", 0.0)
            h_int = d.get("humidity_int", 0.0)
            h_ext = d.get("humidity_ext", 0.0)
            vpd_in  = utils.calc_vpd(t_int, h_int)
            vpd_out = utils.calc_vpd(t_ext, h_ext)

            values = {
                "tile_t_in":   t_int,
                "tile_h_in":   h_int,
                "tile_vpd_in": vpd_in,
                "tile_t_out":  t_ext,
                "tile_h_out":  h_ext,
                "tile_vpd_out": vpd_out,
            }

            # Charts & Labels updaten
            for key, val in values.items():
                self._append_value(key, val)
                tile = self.dashboard.ids.get(key)
                if tile:
                    tile.ids.big.text = f"{val:.2f}"
                    self._auto_scale_y(tile.ids.g, key)

            # Scatter-Fenster live aktualisieren, falls offen
            try:
                from kivy.app import App
                app = App.get_running_app()
                if hasattr(app, "scatter_window") and app.scatter_window:
                    Clock.schedule_once(
                        lambda dt: app.scatter_window.update_values(t_int, h_int, t_ext, h_ext)
                    )
            except Exception:
                pass

        except Exception as e:
            print("⚠️ Polling-Fehler:", e)
            self._set_no_data_labels()

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _append_value(self, key, val):
        buf = self.buffers.setdefault(key, [])
        self.counter += 1
        buf.append((self.counter, val))
        if len(buf) > self.chart_window:
            buf.pop(0)
        plot = self.plots.get(key)
        if plot:
            plot.points = buf

    def _auto_scale_y(self, graph, key):
        try:
            vals = [v for _, v in self.buffers.get(key, []) if isinstance(v, (int, float))]
            if not vals:
                return
            y_min, y_max = min(vals), max(vals)
            if abs(y_max - y_min) < 1e-6:
                y_max, y_min = y_min + 0.5, y_min - 0.5
            margin = max((y_max - y_min) * 0.2, 0.2)
            graph.ymin = round(y_min - margin, 1)
            graph.ymax = round(y_max + margin, 1)
            if self.counter >= self.chart_window:
                graph.xmin = self.counter - self.chart_window
                graph.xmax = self.counter
            else:
                graph.xmin = 0
                graph.xmax = self.chart_window
        except Exception as e:
            print(f"⚠️ Auto-Scale-Fehler ({key}):", e)

    def _set_no_data_labels(self):
        for key in ["tile_t_in","tile_h_in","tile_vpd_in","tile_t_out","tile_h_out","tile_vpd_out"]:
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"

    # ----------------------------------------------------------
    # Reset & Config-Reload
    # ----------------------------------------------------------
    def reset_data(self):
        """Daten zurücksetzen (Polling bleibt – alias VM/Android sicher)."""
        was_running = self.running
        if was_running and self._poll_event:
            Clock.unschedule(self._poll_event)
            self._poll_event = None

        for key in list(self.buffers.keys()):
            self.buffers[key].clear()
            if key in self.plots:
                self.plots[key].points = []
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"

        self.counter = 0
        print("🧹 Charts & Werte zurückgesetzt")

        if was_running:
            self.start_polling()

    def reload_config(self):
        new_cfg = config.load_config() or {}
        self.refresh_interval = float(new_cfg.get("refresh_interval", self.refresh_interval))
        self.chart_window     = int(new_cfg.get("chart_window", self.chart_window))
        self.cfg.update(new_cfg)
        print(f"♻️ Config neu geladen: Poll={self.refresh_interval}, Window={self.chart_window}")
        if self.running:
            self.start_polling()
