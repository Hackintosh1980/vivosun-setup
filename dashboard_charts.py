#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChartManager – Live + Simulation + Auto-Scaling aggressiv
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, random, json
from kivy.clock import Clock
from kivy_garden.graph import MeshLinePlot, LinePlot
from kivy.utils import platform
import config, utils

APP_JSON = "/data/user/0/org.hackintosh1980.dashboard/files/ble_scan.json"


class ChartManager:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.buffers = {}
        self.plots = {}
        self.counter = 0
        self.running = True

        # --- Config ---
        self.cfg = config.load_config()
        self.mode = self.cfg.get("mode", "simulation")
        self.refresh_interval = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window = int(self.cfg.get("chart_window", 120))
        print(f"🌿 ChartManager init – Modus={self.mode}, Poll={self.refresh_interval}s")

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
            # Mindestwerte verhindern ZeroDivisionError
            if graph.ymax == graph.ymin:
                graph.ymin = 0
                graph.ymax = 1


        # --- Start ---
        cfg_mode = (self.mode or "").strip().lower()
        print(f"🔍 Starte Initialisierung – erkannter Modus: {cfg_mode}, Plattform: {platform}")

        # Nur starten, wenn Modus eindeutig gesetzt ist
        if cfg_mode == "simulation" and platform != "android":
                print("🧪 Desktop erkannt – starte Simulation.")
                self.start_simulation()
        elif cfg_mode == "live" and platform == "android":
                print("📡 Android erkannt – starte Live-Polling.")
                self.start_live_poll()
        else:
                print("⏸ Kein gültiger Modus – keine Simulation, kein Poll aktiv.")
                self.running = False


# ----------------------------------------------------------
    # 🔁 SIMULATION
    # ----------------------------------------------------------
    def _simulate_values(self, *a):
        if not self.running:
            return
        self.counter += 1
        vals = {}
        for key in self.plots.keys():
            if "t_in" in key:
                vals[key] = 24 + random.uniform(-1, 1)
            elif "t_out" in key:
                vals[key] = 18 + random.uniform(-2, 2)
            elif "h_in" in key or "h_out" in key:
                vals[key] = 60 + random.uniform(-10, 10)
            elif "vpd" in key:
                vals[key] = random.uniform(0.8, 1.6)
        for key, val in vals.items():
            self._append_value(key, val)

        # GUI aktualisieren
        try:
            self.dashboard.ids.tile_t_in.ids.big.text = f"{vals['tile_t_in']:.1f}"
            self.dashboard.ids.tile_h_in.ids.big.text = f"{vals['tile_h_in']:.1f}"
            self.dashboard.ids.tile_vpd_in.ids.big.text = f"{vals['tile_vpd_in']:.2f}"
        except Exception:
            pass

    def start_simulation(self):
        """Startet Dummy-Simulation (nur Desktop)."""
        try:
            # Erst alles stoppen
            self.stop_simulation()
            self.running = True

            # Event nur EINMAL planen
            self._sim_event = Clock.schedule_interval(self._simulate_values, 2.0)
            print("🧪 Simulation gestartet (Loop aktiv).")

        except Exception as e:
            print("⚠️ start_simulation Fehler:", e)
    # ----------------------------------------------------------
    # 📡 LIVE POLLING
    # ----------------------------------------------------------
    def start_live_poll(self):
        """Starte Polling für echte Bridge-Daten."""
        # Simulation darf hier nicht aktiv sein
        self.stop_simulation()
        self.running = True

        if platform != "android":
            print("⚠️ Live Poll deaktiviert – kein Android.")
            return

        print("📡 Starte Live-Polling …")
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)

    def _poll_json(self, *a):
        """Liest Echtwerte aus der BleBridge JSON."""
        if not self.running:
            return
        try:
            if not os.path.exists(APP_JSON):
                print("⚠️ Keine JSON-Datei gefunden:", APP_JSON)
                return

            with open(APP_JSON, "r") as f:
                data = json.load(f)
            if not data:
                print("⚠️ JSON leer.")
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


    # ----------------------------------------------------------
    # 🧩 Gemeinsame
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

            # 👉 Schutz gegen flache oder konstante Kurven
            if abs(y_max - y_min) < 1e-6:
                y_max = y_min + 0.5
                y_min = y_min - 0.5

            # Dynamische Margin für „atmende“ Kurve
            margin = max((y_max - y_min) * 0.2, 0.2)
            graph.ymin = round(y_min - margin, 1)
            graph.ymax = round(y_max + margin, 1)

            # 👉 X-Achse sauber verschieben ohne Sprung
            if self.counter >= self.chart_window:
                graph.xmin = self.counter - self.chart_window
                graph.xmax = self.counter
            else:
                graph.xmin = 0
                graph.xmax = self.chart_window

        except Exception as e:
            print(f"⚠️ Auto-Scale-Fehler ({key}):", e)



    # ----------------------------------------------------------
    # 🧹 Reset / Stop / Config
    # ----------------------------------------------------------
    def stop_simulation(self):
        if hasattr(self, "_sim_event"):
            Clock.unschedule(self._sim_event)
        if hasattr(self, "_poll_event"):
            Clock.unschedule(self._poll_event)
        self.running = False
        print("⏹ Loop gestoppt.")

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
