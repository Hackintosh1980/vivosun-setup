#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChartManager – Live-Only Version (keine Simulation)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, json
from kivy.clock import Clock
from kivy_garden.graph import LinePlot
from kivy.utils import platform
import config, utils
import os, json

if platform == "android":
    APP_JSON = "/data/user/0/org.hackintosh1980.dashboard/files/ble_scan.json"
else:
    APP_JSON = os.path.join(os.path.dirname(__file__), "ble_scan.json")

print(f"🗂️ Verwende APP_JSON = {APP_JSON}")


class ChartManager:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.buffers = {}
        self.plots = {}
        self.counter = 0
        self.running = True

        # --- Config ---
        self.cfg = config.load_config()
        self.refresh_interval = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window = int(self.cfg.get("chart_window", 120))
        print(f"🌿 ChartManager init – Live-Modus, Poll={self.refresh_interval}s")

        # --- Graphs vorbereiten ---
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

            # Mindestwerte gegen ZeroDivisionError
            if graph.ymax == graph.ymin:
                graph.ymin = 0
                graph.ymax = 1

        # --- Start ---
        print(f"📡 Starte Live-Polling (Plattform: {platform})")
        self.start_live_poll()
    # ----------------------------------------------------------
    # 📡 LIVE POLLING
    # ----------------------------------------------------------
    def start_live_poll(self):
        """Starte Polling für echte Bridge-Daten (Android)."""
        self.running = True
        print("📡 Starte Live-Polling …")
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)

    def _poll_json(self, *a):
        """Liest Echtwerte aus der BleBridge JSON."""
        if not self.running:
            return
        try:
            if not os.path.exists(APP_JSON):
                print(f"⚠️ JSON fehlt: {APP_JSON}")
                self._set_no_data_labels()
                return

            with open(APP_JSON, "r") as f:
                data = json.load(f)
            if not data or not isinstance(data, list):
                print("⚠️ JSON leer oder ungültig.")
                self._set_no_data_labels()
                return

            d = data[0]

            # Werte dekodieren
            t_int = d.get("temperature_int", 0.0)
            t_ext = d.get("temperature_ext", 0.0)
            h_int = d.get("humidity_int", 0.0)
            h_ext = d.get("humidity_ext", 0.0)
            vpd_in = utils.calc_vpd(t_int, h_int)
            vpd_out = utils.calc_vpd(t_ext, h_ext)

            values = {
                "tile_t_in": t_int,
                "tile_h_in": h_int,
                "tile_vpd_in": vpd_in,
                "tile_t_out": t_ext,
                "tile_h_out": h_ext,
                "tile_vpd_out": vpd_out,
            }

            # Charts & Labels updaten
            for key, val in values.items():
                self._append_value(key, val)
                tile = self.dashboard.ids.get(key)
                if tile:
                    tile.ids.big.text = f"{val:.2f}"
                    self._auto_scale_y(tile.ids.g, key)

        except Exception as e:
            print("⚠️ Polling-Fehler:", e)
            self._set_no_data_labels()

    # ----------------------------------------------------------
    # 🧩 Hilfsfunktionen
    # ----------------------------------------------------------
    def _append_value(self, key, val):
        buf = self.buffers[key]
        self.counter += 1
        buf.append((self.counter, val))
        if len(buf) > self.chart_window:
            buf.pop(0)
        if key in self.plots:
            self.plots[key].points = buf

    def _auto_scale_y(self, graph, key):
        """Passt Y-Achse automatisch an aktuelle Werte an + ZeroDivisionError-Schutz."""
        try:
            buf = self.buffers.get(key, [])
            vals = [v for _, v in buf if isinstance(v, (int, float))]
            if not vals:
                return

            y_min = min(vals)
            y_max = max(vals)

            # Schutz gegen flache Kurven
            if abs(y_max - y_min) < 1e-6:
                y_max = y_min + 0.5
                y_min = y_min - 0.5

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
        """Zeigt '--' an, wenn keine Echtwerte verfügbar."""
        for key in [
            "tile_t_in", "tile_h_in", "tile_vpd_in",
            "tile_t_out", "tile_h_out", "tile_vpd_out"
        ]:
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"

    # ----------------------------------------------------------
    # 🧹 Reset / Stop / Config
    # ----------------------------------------------------------
    def stop_polling(self):
        if hasattr(self, "_poll_event"):
            Clock.unschedule(self._poll_event)
        self.running = False
        print("⏹ Polling gestoppt.")

    def reset_data(self):
        for key, buf in self.buffers.items():
            buf.clear()
            if key in self.plots:
                self.plots[key].points = []
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"
        self.counter = 0
        print("🧹 Charts & Werte zurückgesetzt")

    def reload_config(self):
        new_cfg = config.load_config()
        self.refresh_interval = float(new_cfg.get("refresh_interval", self.refresh_interval))
        self.chart_window = int(new_cfg.get("chart_window", self.chart_window))
        print(f"♻️ Config neu geladen: Poll={self.refresh_interval}, Window={self.chart_window}")
